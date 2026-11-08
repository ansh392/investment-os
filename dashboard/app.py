from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment_os.config import settings
from investment_os.core.evidence import EvidenceKind
from investment_os.models.valuation import (
    DCFInputs,
    dcf_sensitivity_table,
    dcf_valuation,
    reverse_dcf_implied_growth,
)
from investment_os.models.workspace import OperatingAssumptions, ValuationNotApplicable, value_bridge_table
from investment_os.pipeline import DEFAULT_OUTPUT_DIR, ResearchBundle, available_bundles, build_bundle, load_bundle
from investment_os.private.lbo import LBOInputs, run_lbo, solve_max_debt_for_dscr, solve_max_purchase_price
from investment_os.research.ic_memo import build_memo, memo_to_html, recommendation_for, validate_citations
from investment_os.research.thesis_lab import contradictory_findings, run_thesis_lab
from investment_os.research.workflow import ValuationPackage, run_valuation
from investment_os.signals.altdata import abnormal_event_study, load_dataset, run_altdata_lab

OUTPUTS = Path(os.getenv("INVESTMENT_OS_OUTPUTS", DEFAULT_OUTPUT_DIR))
SAMPLE = ROOT / "sample_data"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRID, AXIS, MUTED, INK = "#e1e0d9", "#c3c2b7", "#898781", "#52514e"
PAGES = ["Company Research", "Reverse DCF", "Thesis Lab", "Alternative Data Lab", "Private Markets", "IC Memo"]
DEFAULT_THESIS = "The market underestimates this company's ability to grow revenue and convert earnings into free cash flow."
STATUS_MARK = {"supported": "▲ Supported", "contradicted": "▼ Contradicted", "mixed": "◆ Mixed", "inconclusive": "○ Inconclusive"}

st.set_page_config(page_title="Investment OS", layout="wide", page_icon="📈")
st.markdown(
    """<style>
    .block-container{padding-top:2.2rem;max-width:1320px}
    [data-testid="stMetricValue"]{font-size:1.45rem}
    h1{font-size:1.75rem!important;letter-spacing:-.01em}
    h2{font-size:1.2rem!important}h3{font-size:1rem!important}
    .tag{display:inline-block;padding:1px 8px;border-radius:4px;background:#eef2f8;color:#1c5cab;font-size:12px;margin-right:6px}
    .verdict{padding:14px 18px;border-left:4px solid #1f4e8c;background:#f4f6fa;border-radius:4px;font-weight:600;margin:6px 0 12px}
    </style>""",
    unsafe_allow_html=True,
)


def style(fig: go.Figure, *, title: str, height: int = 300, y_format: str | None = None) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=INK), x=0, xanchor="left"), height=height, margin=dict(l=8, r=8, t=44, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="system-ui, Segoe UI, sans-serif", color=INK, size=12),
        hovermode="x unified", showlegend=False, bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor=AXIS, tickfont=dict(color=MUTED), tickformat=y_format)
    return fig


def bars(x, y, *, title: str, color: str = BLUE, y_format: str | None = None, hover: str = "%{y:,.1f}") -> go.Figure:
    return style(go.Figure(go.Bar(x=x, y=y, marker_color=color, marker_cornerradius=4, hovertemplate=hover + "<extra></extra>")), title=title, y_format=y_format)


def line(x, y, *, title: str, color: str = BLUE, y_format: str | None = None, hover: str = "%{y:,.2f}") -> go.Figure:
    return style(go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2), hovertemplate=hover + "<extra></extra>")), title=title, y_format=y_format)


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def table(df: pd.DataFrame, **kw) -> None:
    st.dataframe(df, width="stretch", hide_index=True, **kw)


def usd(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value) / 1e9:,.{digits}f}B"


def pct(value, digits: int = 1) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.{digits}%}"


@st.cache_resource(show_spinner=False)
def bundle_for(ticker: str, stamp: float) -> ResearchBundle:
    return load_bundle(ticker, root=OUTPUTS)


def current_bundle(ticker: str) -> ResearchBundle:
    return bundle_for(ticker, (OUTPUTS / ticker / "manifest.json").stat().st_mtime)


def scenario_table(defaults: dict[str, OperatingAssumptions]) -> pd.DataFrame:
    return pd.DataFrame([
        {"scenario": k, "growth_start": a.revenue_growth[0], "growth_end": a.revenue_growth[-1], "ebit_margin": a.ebit_margin[0], "probability": a.probability}
        for k, a in defaults.items()
    ])


def scenarios_from_table(frame: pd.DataFrame, template: dict[str, OperatingAssumptions], wacc: float, tg: float) -> dict[str, OperatingAssumptions]:
    out = {}
    for row in frame.to_dict("records"):
        t = template[row["scenario"]]
        years = len(t.revenue_growth)
        out[row["scenario"]] = OperatingAssumptions(
            name=row["scenario"], revenue_growth=tuple(float(x) for x in np.linspace(row["growth_start"], row["growth_end"], years)),
            ebit_margin=(float(row["ebit_margin"]),) * years, tax_rate=t.tax_rate, dna_pct_revenue=t.dna_pct_revenue,
            capex_pct_revenue=t.capex_pct_revenue, nwc_pct_delta_revenue=t.nwc_pct_delta_revenue, wacc=wacc, terminal_growth=tg, probability=float(row["probability"]),
        )
    return out


def valuation_for(bundle: ResearchBundle) -> tuple[ValuationPackage | None, str | None]:
    """Valuation using the analyst's saved inputs, shared by every page."""
    saved = st.session_state.get(f"val:{bundle.ticker}", {})
    wacc, tg = saved.get("wacc", 0.09), saved.get("tg", 0.025)
    try:
        base = run_valuation(bundle, wacc=wacc, terminal_growth=tg)
        edited = saved.get("table")
        if edited is None:
            return base, None
        scenarios = scenarios_from_table(edited, {k: r.assumptions for k, r in base.results.items()}, wacc, tg)
        return run_valuation(bundle, wacc=wacc, terminal_growth=tg, scenarios=scenarios), None
    except (ValuationNotApplicable, ValueError) as exc:
        return None, str(exc)


def thesis_for(bundle: ResearchBundle, valuation: ValuationPackage | None):
    saved = st.session_state.get(f"thesis:{bundle.ticker}", {})
    return run_thesis_lab(saved.get("hypothesis", DEFAULT_THESIS), bundle, valuation, extra_claims=saved.get("extra", ()))


def page_company(b: ResearchBundle) -> None:
    m = b.market
    st.title(f"{b.name} ({b.ticker})")
    st.markdown(f'<span class="tag">CIK {b.cik}</span><span class="tag">SIC {b.sic} · {b.sic_description}</span><span class="tag">Retrieved {b.retrieved_at}</span>', unsafe_allow_html=True)
    cols = st.columns(6)
    cols[0].metric(f"Price ({m.get('price_date', 'n/a')})", f"${m['price']:,.2f}" if m.get("price") else "n/a")
    cols[1].metric("Market cap", usd(m.get("market_cap")))
    cols[2].metric("Enterprise value", usd(m.get("enterprise_value")))
    cols[3].metric("TTM revenue", usd(b.ttm.get("revenue")))
    cols[4].metric("TTM FCF", usd(b.ttm.get("fcf")))
    cols[5].metric("Evidence items", f"{len(b.ledger):,}")
    if b.warnings:
        with st.expander(f"⚠ {len(b.warnings)} data warning(s): nothing below was guessed", expanded=b.is_financial):
            for w in b.warnings:
                st.markdown(f"- {w}")

    a = b.annual
    if not a.empty:
        labels = [f"FY{y}" for y in a["fiscal_year"]]
        c1, c2 = st.columns(2)
        with c1:
            show(bars(labels, a["revenue"] / 1e9, title="Revenue (USD billions)", hover="$%{y:,.1f}B"))
        with c2:
            show(bars(labels, a["fcf"] / 1e9, title="Free cash flow (USD billions)", color=AQUA, hover="$%{y:,.1f}B"))
    if not b.prices.empty:
        show(line(b.prices["date"], b.prices["close"], title="Share price (USD, split-adjusted close)", hover="$%{y:,.2f}"))

    t1, t2, t3, t4 = st.tabs(["Financial history", "Filings", "Audit trail", "Earnings event study"])
    with t1:
        basis = st.radio("Periodicity", ["Annual", "Quarterly"], horizontal=True, key="hist_basis")
        frame = a if basis == "Annual" else b.quarterly
        columns = ["fiscal_year", "fiscal_period", "period_end", "revenue", "operating_income", "net_income", "cfo", "capex", "fcf", "cash", "debt", "total_assets", "total_liabilities"]
        if not frame.empty:
            view = frame[columns].iloc[::-1].copy()
            view[columns[3:]] = view[columns[3:]] / 1e6
            table(view, column_config={c: st.column_config.NumberColumn(format="%,.0f") for c in columns[3:]})
            st.caption("USD millions. Blank means not reliably available. FCF = CFO - capex. Debt excludes operating leases.")
    with t2:
        forms = b.filings[b.filings["form"].isin(["10-K", "10-Q", "10-K/A", "10-Q/A", "8-K"])].head(60)
        table(forms[["filed", "form", "report_date", "accession", "url"]], column_config={"url": st.column_config.LinkColumn("Document", display_text="Open on SEC")})
    with t3:
        st.caption("Trace any number back to its XBRL tag, filing, and derivation method.")
        kinds = st.multiselect("Evidence type", [k.value for k in EvidenceKind], default=["reported", "derived"])
        ledger = pd.DataFrame([i for i in b.ledger.as_list() if i["kind"] in kinds])
        if not ledger.empty:
            table(ledger[["id", "kind", "claim", "value", "unit", "period", "form", "filed", "source", "notes"]], height=380, column_config={"source": st.column_config.LinkColumn("Source", display_text="Open")})
        if b.notes:
            with st.expander("XBRL tag-resolution notes"):
                for n in b.notes:
                    st.markdown(f"- {n}")
    with t4:
        spy_path = SAMPLE / "spy_close.csv"
        filings = b.filings[b.filings["form"].isin(["10-K", "10-Q"])]
        if b.prices.empty or filings.empty:
            st.info("Prices and periodic filings are both required.")
        else:
            returns = b.prices.set_index("date")["adj_close"].pct_change().dropna()
            benchmark = load_dataset(spy_path).pct_change().dropna() if spy_path.exists() else None
            study = abnormal_event_study(returns, list(filings["filed"]), benchmark=benchmark)
            table(study, column_config={"mean_car": st.column_config.NumberColumn("Mean abnormal return", format="percent"), "win_rate": st.column_config.NumberColumn("Win rate", format="percent"), "t_stat": st.column_config.NumberColumn("t-stat", format="%.2f")})
            st.caption(f"Sessions after each 10-K/10-Q filing date, {'net of SPY' if benchmark is not None else 'raw returns'}. Filing date is a proxy for the earnings date; overlapping windows are dropped.")


def football_field(v: ValuationPackage, price: float) -> go.Figure:
    labels, values = [], []
    for name, r in v.results.items():
        labels.append(f"DCF {name}")
        values.append(r.implied_price)
    labels.append("DCF weighted")
    values.append(v.weighted_price)
    if not v.comps_implied.empty:
        for row in v.comps_implied.dropna(subset=["implied_price"]).itertuples():
            labels.append(f"Comps {row.method}")
            values.append(row.implied_price)
    fig = go.Figure(go.Scatter(
        x=values, y=labels, mode="markers+text", marker=dict(size=12, color=BLUE, line=dict(color="#fcfcfb", width=2)),
        text=[f"${x:,.0f}" for x in values], textposition="top center", cliponaxis=False, hovertemplate="%{y}: $%{x:,.2f}<extra></extra>",
    ))
    fig.add_vline(x=price, line=dict(color=ORANGE, width=2), annotation_text=f"Price ${price:,.2f}", annotation_position="top")
    style(fig, title="Value per share by method (USD)", height=340)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    return fig


def page_valuation(b: ResearchBundle) -> None:
    st.title(f"Reverse DCF & Valuation: {b.ticker}")
    t_exp, t_manual = st.tabs(["Company workspace", "Manual DCF (illustrative)"])
    with t_exp:
        v, error = valuation_for(b)
        if v is None:
            st.warning(f"Valuation not applicable: {error}")
        else:
            key = f"val:{b.ticker}"
            saved = st.session_state.setdefault(key, {})
            c1, c2 = st.columns(2)
            wacc = c1.slider("WACC (placeholder until overridden)", 0.05, 0.16, saved.get("wacc", 0.09), 0.0025, format="%.2f")
            tg = c2.slider("Terminal growth", 0.0, 0.04, saved.get("tg", 0.025), 0.0025, format="%.3f")
            if (wacc, tg) != (saved.get("wacc", 0.09), saved.get("tg", 0.025)):
                saved.update(wacc=wacc, tg=tg)
                st.rerun()

            x = v.expectations
            price = b.market["price"]
            cols = st.columns(5)
            cols[0].metric("Share price", f"${price:,.2f}")
            cols[1].metric("Weighted DCF", f"${v.weighted_price:,.2f}", f"{v.upside:+.0%} vs price")
            cols[2].metric("Implied revenue CAGR", pct(x["implied_revenue_cagr"]))
            cols[3].metric("Implied EBIT margin", pct(x["implied_ebit_margin"]))
            cols[4].metric("Implied FCFF CAGR", pct(x["implied_fcff_cagr"]))
            for note in x["notes"]:
                st.info(note)
            for warning in v.warnings:
                st.caption(f"⚠ {warning}")
            show(football_field(v, price))

            st.subheader("Bull / base / bear assumptions")
            st.caption("Defaults are mechanical anchors from reported history and are recorded as `assumed`. Edit any cell.")
            edited = st.data_editor(scenario_table({k: r.assumptions for k, r in v.results.items()}), hide_index=True, width="stretch", disabled=["scenario"], key=f"editor:{b.ticker}")
            if abs(edited["probability"].sum() - 1) > 1e-6:
                st.error("Probabilities must sum to 100%; the previous valid scenarios are still in use.")
            elif not edited.equals(scenario_table({k: r.assumptions for k, r in v.results.items()})):
                saved["table"] = edited
                st.rerun()

            pick = st.radio("Bridge scenario", list(v.results), index=1, horizontal=True)
            result = v.results[pick]
            st.subheader("Assumptions → FCF → equity value")
            bridge = result.bridge.copy()
            money = ["revenue", "ebit", "taxes", "nopat", "dna", "capex", "delta_nwc", "fcff"]
            bridge[money] = bridge[money] / 1e6
            table(bridge, column_config={**{c: st.column_config.NumberColumn(format="%,.0f") for c in money}, "growth": st.column_config.NumberColumn(format="percent"), "ebit_margin": st.column_config.NumberColumn(format="percent")})
            st.caption(f"USD millions. Base revenue: {v.base.revenue_basis}.")
            c1, c2 = st.columns(2)
            with c1:
                wf = value_bridge_table(result)
                wf["display"] = [f"${x:,.2f}" if "per share" in l else (f"{x / 1e6:,.1f}M" if "Shares" in l else usd(x)) for l, x in zip(wf["line"], wf["value"])]
                table(wf[["line", "display"]])
            with c2:
                st.markdown("**Sensitivity: value per share**")
                sens = v.sensitivity.copy()
                table(sens, column_config={"wacc": st.column_config.NumberColumn(format="percent"), **{c: st.column_config.NumberColumn(format="$%.2f") for c in sens.columns if c != "wacc"}})

            st.subheader("Comparable companies")
            if v.comps.empty:
                st.info("No peers in this bundle. Add them: `python scripts/research_company.py TICKER --peers A,B,C`.")
            else:
                show_cols = ["ticker", "enterprise_value", "market_cap", "ev_revenue", "ev_ebitda", "pe", "fcf_yield", "source"]
                peers = v.comps[show_cols].copy()
                peers[["enterprise_value", "market_cap"]] = peers[["enterprise_value", "market_cap"]] / 1e9
                table(peers, column_config={"source": st.column_config.LinkColumn("Source", display_text="EDGAR"), "enterprise_value": st.column_config.NumberColumn("EV ($B)", format="%.1f"), "market_cap": st.column_config.NumberColumn("Mkt cap ($B)", format="%.1f"), "ev_revenue": st.column_config.NumberColumn(format="%.1fx"), "ev_ebitda": st.column_config.NumberColumn(format="%.1fx"), "pe": st.column_config.NumberColumn(format="%.1fx"), "fcf_yield": st.column_config.NumberColumn(format="percent")})
                implied = v.comps_implied.copy()
                implied["target_metric"] = implied["target_metric"] / 1e9
                table(implied, column_config={"peer_median": st.column_config.NumberColumn("Peer median", format="%.1fx"), "target_metric": st.column_config.NumberColumn("Target metric ($B)", format="%.2f"), "implied_price": st.column_config.NumberColumn("Implied price", format="$%.2f")})
    with t_manual:
        st.caption("Free-form calculator. All inputs below are illustrative and unconnected to any company.")
        c1, c2, c3, c4 = st.columns(4)
        start = c1.number_input("Starting FCFF", value=2_400_000_000.0, step=100_000_000.0)
        growth = c2.slider("Forecast FCFF CAGR", -0.10, 0.50, 0.08, 0.01)
        wacc_m = c3.slider("Discount rate", 0.04, 0.18, 0.09, 0.005)
        tg_m = c4.slider("Terminal growth rate", 0.00, 0.05, 0.025, 0.005)
        years = st.slider("Forecast years", 3, 10, 5)
        c1, c2, c3 = st.columns(3)
        net_debt = c1.number_input("Net debt", value=8_000_000_000.0, step=100_000_000.0)
        shares = c2.number_input("Shares outstanding", value=300_000_000.0, step=10_000_000.0)
        market_ev = c3.number_input("Current market enterprise value", value=45_000_000_000.0, step=1_000_000_000.0)
        fcff = tuple(start * ((1 + growth) ** i) for i in range(1, years + 1))
        try:
            dcf = dcf_valuation(DCFInputs(fcff, wacc_m, tg_m, net_debt, shares))
            implied = reverse_dcf_implied_growth(market_enterprise_value=market_ev, starting_fcff=start, years=years, wacc=wacc_m, terminal_growth=tg_m)
            m1, m2, m3 = st.columns(3)
            m1.metric("DCF implied price", f"${dcf['implied_price']:,.2f}")
            m2.metric("Modeled EV", usd(dcf["enterprise_value"]))
            m3.metric("Market-implied FCFF CAGR", pct(implied))
            sens = dcf_sensitivity_table(fcff=fcff, net_debt=net_debt, shares_outstanding=shares, wacc_values=[wacc_m + d for d in (-0.01, -0.005, 0, 0.005, 0.01)], terminal_growth_values=[max(0.0, tg_m + d) for d in (-0.01, -0.005, 0, 0.005, 0.01)])
            table(sens)
        except ValueError as exc:
            st.error(str(exc))


def page_thesis(b: ResearchBundle) -> None:
    st.title(f"Thesis Lab: {b.ticker}")
    st.caption("Deterministic: every finding is computed from filings and cites evidence. No LLM is needed.")
    v, error = valuation_for(b)
    if v is None:
        st.warning(f"Valuation not applicable, so expectation tests are skipped: {error}")
    key = f"thesis:{b.ticker}"
    saved = st.session_state.setdefault(key, {})
    hypothesis = st.text_area("Investment hypothesis", saved.get("hypothesis", DEFAULT_THESIS), height=80)
    extra = st.text_area("Additional claims, one per line (these need your own sourced evidence)", "\n".join(saved.get("extra", ())), height=68)
    saved.update(hypothesis=hypothesis, extra=tuple(x.strip() for x in extra.splitlines() if x.strip()))
    report = thesis_for(b, v)
    ledger = v.ledger if v else b.ledger

    if settings.anthropic_api_key and st.button("Sharpen claim wording with Claude"):
        from investment_os.research.agent import AnthropicResearchAgent

        try:
            report, rejected = AnthropicResearchAgent().reword_claims(report, ledger)
            for item in rejected:
                st.caption(f"Rejected: {item}")
        except Exception as exc:  # optional layer must never break the deterministic page
            st.error(f"Claude call failed; deterministic claims are unchanged. {exc}")

    counts = report.status_counts()
    cols = st.columns(4)
    for col, name in zip(cols, counts):
        col.metric(STATUS_MARK[name], counts[name])

    st.subheader("What is priced in")
    if report.priced_in:
        for f in report.priced_in:
            st.markdown(f"- {f.text}. `{' '.join(f.evidence)}`")
    else:
        st.info("Market-implied expectations are unavailable for this company.")

    st.subheader("Claims")
    for c in report.claims:
        with st.expander(f"{c.id} · {STATUS_MARK[c.status]} · {c.statement}", expanded=True):
            left, right = st.columns(2)
            with left:
                st.markdown("**Supporting evidence**")
                for f in c.supporting:
                    st.markdown(f"- {f.text}  \n`{' '.join(f.evidence)}`")
                if not c.supporting:
                    st.caption("None found among tested metrics.")
            with right:
                st.markdown("**Contradictory evidence**")
                for f in c.contradicting:
                    st.markdown(f"- {f.text}  \n`{' '.join(f.evidence)}`")
                if not c.contradicting:
                    st.caption("None found among tested metrics.")
            st.markdown("**Evidence required:** " + "; ".join(c.evidence_required))
            st.markdown("**Falsified if:** " + " ".join(c.falsified_if))
            for q in c.open_questions:
                st.caption(f"Open: {q}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Catalysts")
        st.caption("Judgment, not reported facts.")
        for x in report.catalysts:
            st.markdown(f"- {x}")
    with c2:
        st.subheader(f"Unanswered diligence ({report.sector})")
        for x in report.diligence:
            st.markdown(f"- {x}")


def dataset_options(b: ResearchBundle) -> dict[str, dict]:
    opts = {}
    if (SAMPLE / "ung_etf_close.csv").exists():
        opts["REAL: UNG natural-gas ETF vs VST"] = {"signal": SAMPLE / "ung_etf_close.csv", "price": SAMPLE / "vst_close.csv", "transform": "pct_change", "synthetic": False}
        opts["REAL: XLU utilities ETF vs VST"] = {"signal": SAMPLE / "xlu_close.csv", "price": SAMPLE / "vst_close.csv", "transform": "pct_change", "synthetic": False}
    for name, label in (("informative", "planted signal"), ("noise", "pure noise"), ("leaky", "contains the future")):
        path = SAMPLE / f"synthetic_signal_{name}.csv"
        if path.exists():
            opts[f"SYNTHETIC: {label}"] = {"signal": path, "price": SAMPLE / "synthetic_prices.csv", "transform": "level", "synthetic": True}
    opts["Upload a CSV"] = {"signal": None, "price": None, "transform": "pct_change", "synthetic": False}
    return opts


def page_altdata(b: ResearchBundle) -> None:
    st.title("Alternative Data Lab")
    st.markdown("**Does this dataset contain incremental information, and does that survive out of sample?**")
    options = dataset_options(b)
    choice = st.selectbox("Dataset", list(options))
    spec = options[choice]
    if spec["synthetic"]:
        st.warning("SYNTHETIC DATA: simulated to validate the lab against a known answer. This is not market data.")
    signal, prices = None, None
    try:
        if spec["signal"] is None:
            up = st.file_uploader("CSV with a date column and a numeric column", type="csv")
            if up is None:
                st.info(f"Upload a dataset. It will be tested against {b.ticker} prices.")
                return
            raw = pd.read_csv(up)
            c1, c2 = st.columns(2)
            date_col = c1.selectbox("Date column", list(raw.columns))
            value_col = c2.selectbox("Value column", [c for c in raw.columns if c != date_col])
            signal = load_dataset(raw, date_col=date_col, value_col=value_col)
            prices = b.prices.set_index("date")["adj_close"]
        else:
            signal, prices = load_dataset(spec["signal"]), load_dataset(spec["price"])
    except ValueError as exc:
        st.error(str(exc))
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    freq = c1.selectbox("Frequency", ["W-FRI", "ME"], format_func=lambda x: {"W-FRI": "Weekly", "ME": "Monthly"}[x])
    transforms = ["pct_change", "diff", "level", "trailing_zscore"]
    transform = c2.selectbox("Transform", transforms, index=transforms.index(spec["transform"]))
    lag_days = c3.number_input("Publication lag (days)", 0, 120, 0 if spec["synthetic"] else 1, key=f"lag_days:{choice}")
    max_lag = c4.slider("Max lag searched", 1, 12, 8)
    cost = c5.slider("Cost (bps per turnover)", 0.0, 50.0, 10.0, 1.0)
    use_benchmark = st.checkbox("Test excess return over SPY", value=False, disabled=spec["synthetic"] or not (SAMPLE / "spy_close.csv").exists())
    benchmark = load_dataset(SAMPLE / "spy_close.csv") if use_benchmark else None

    try:
        report = run_altdata_lab(signal, prices, freq=freq, publication_lag_days=int(lag_days), transform=transform, max_lag=max_lag, cost_bps=cost, benchmark=benchmark)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.markdown(f'<div class="verdict">{report.verdict}</div>', unsafe_allow_html=True)
    for reason in report.reasons:
        st.markdown(f"- {reason}")

    perf = report.performance_table()
    test = perf.iloc[-1]
    cols = st.columns(5)
    cols[0].metric("Test net return", pct(test["net_return"]))
    cols[1].metric("Buy & hold (test)", pct(test["buy_hold_return"]))
    cols[2].metric("Test Sharpe", f"{test['sharpe']:.2f}")
    cols[3].metric("Test max drawdown", pct(test["max_drawdown"]))
    cols[4].metric("Permutation p-value", f"{report.test_permutation_p:.3f}")

    st.subheader("Leakage checks")
    table(pd.DataFrame([{"check": c.name, "result": "✓ Pass" if c.passed else ("△ Warning" if c.severity == "warn" else "✗ FAIL"), "detail": c.detail} for c in report.leakage]))

    c1, c2 = st.columns(2)
    with c1:
        show(bars(report.lag_table["lag"], report.lag_table["correlation"], title="Lag test, training segment only (correlation with next return)", hover="%{y:.3f}"))
    with c2:
        show(line(report.rolling.index, report.rolling.values, title="Rolling correlation with next return", hover="%{y:.3f}"))
    equity = report.performance[-1].equity
    show(line(equity.index, equity.values, title="Test-segment strategy equity, net of costs (start = 1.0)", color=AQUA, hover="%{y:.3f}"))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Chronological splits")
        table(report.splits.as_rows())
        st.subheader("Does the signal add to a baseline?")
        table(report.models.table.round(4))
    with c2:
        st.subheader("Performance by segment")
        table(perf[["segment", "observations", "net_return", "gross_return", "buy_hold_return", "sharpe", "max_drawdown", "hit_rate", "turnover"]].round(3))
        st.subheader("Reverse-causality check")
        st.caption("Significant values suggest the signal follows price instead of leading it.")
        table(report.reverse.round(3))
    st.subheader("Parameter stability (diagnostic only, never used for selection)")
    pivot = report.stability.pivot(index="lag", columns="threshold", values="test_sharpe").round(2).reset_index()
    pivot.columns = [str(c) if c == "lag" else f"z≥{c}" for c in pivot.columns]
    c1, c2 = st.columns(2)
    with c1:
        table(pivot)
        st.caption("Test Sharpe across lag and z-threshold. A lone positive cell means fragility.")
    with c2:
        table(report.betas.round(4))
        st.caption("Signal coefficient by sequential block. Sign flips mean instability.")


def page_private() -> None:
    st.title("Private Markets")
    st.caption("LBO and private-credit underwriting. Default inputs are illustrative.")
    c1, c2, c3 = st.columns(3)
    purchase = c1.number_input("Purchase price", value=1_000_000_000.0, step=25_000_000.0)
    debt = c2.number_input("Debt", value=550_000_000.0, step=25_000_000.0)
    interest = c3.slider("Interest rate", 0.02, 0.20, 0.085, 0.005)
    amort = st.slider("Mandatory amortization (% of initial debt)", 0.0, 0.20, 0.05, 0.01)
    cfads_text = st.text_input("CFADS forecast", "150000000,160000000,170000000,180000000,190000000")
    exit_ev = st.number_input("Exit enterprise value", value=1_250_000_000.0, step=25_000_000.0)
    c1, c2 = st.columns(2)
    target_irr = c1.slider("Target sponsor IRR", 0.05, 0.40, 0.20, 0.01)
    minimum_dscr = c2.slider("Minimum lender DSCR", 1.0, 3.0, 1.40, 0.05)
    try:
        cfads = tuple(float(x.strip()) for x in cfads_text.split(","))
        result = run_lbo(LBOInputs(purchase, debt, 0.0, cfads, interest, amort, exit_ev))
        common = dict(cash=0.0, annual_cfads=cfads, interest_rate=interest, mandatory_amortization_pct=amort, exit_enterprise_value=exit_ev)
        max_debt = solve_max_debt_for_dscr(purchase_price=purchase, minimum_dscr=minimum_dscr, **common)
        try:
            max_price: float | None = solve_max_purchase_price(debt=debt, target_irr=target_irr, low=debt + 1, high=max(exit_ev * 2, purchase * 2), **common)
        except ValueError:
            max_price = None
    except ValueError as exc:
        st.error(str(exc))
        return
    cols = st.columns(5)
    cols[0].metric("IRR", pct(result["irr"]))
    cols[1].metric("MOIC", f"{result['moic']:.2f}x")
    cols[2].metric("Minimum DSCR", f"{result['min_dscr']:.2f}x")
    cols[3].metric("Max price @ target IRR", f"${max_price / 1e6:,.1f}M" if max_price else "Not reachable")
    cols[4].metric("Max debt @ min DSCR", f"${max_debt / 1e6:,.1f}M")
    if result["total_shortfall"] > 0:
        st.error(f"Debt service shortfall of ${result['total_shortfall'] / 1e6:,.1f}M: CFADS does not cover debt service, and the shortfall capitalizes onto the balance.")
    yearly = pd.DataFrame(result["yearly"])
    c1, c2 = st.columns(2)
    with c1:
        show(bars(yearly["year"], yearly["ending_debt"] / 1e6, title="Ending debt (USD millions)", hover="$%{y:,.1f}M"))
    with c2:
        fig = bars(yearly["year"], yearly["dscr"], title="DSCR by year (x), with lender minimum", color=AQUA, hover="%{y:.2f}x")
        fig.add_hline(y=minimum_dscr, line=dict(color=ORANGE, width=2), annotation_text=f"Min {minimum_dscr:.2f}x")
        show(fig)
    table(yearly.round(2))


def page_memo(b: ResearchBundle) -> None:
    st.title(f"IC Memo: {b.ticker}")
    v, error = valuation_for(b)
    report = thesis_for(b, v)
    ledger = v.ledger if v else b.ledger
    memo = build_memo(b, v, report)
    check = validate_citations(memo, ledger)
    label, _ = recommendation_for(v, report)
    st.markdown(f'<div class="verdict">Rule-based rating: {label}</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Citation check", "✓ Passed" if check.ok else "✗ Failed")
    cols[1].metric("Citations verified", f"{check.citations_checked}")
    cols[2].metric("Reported / derived", f"{len(ledger.by_kind(EvidenceKind.REPORTED))} / {len(ledger.by_kind(EvidenceKind.DERIVED))}")
    cols[3].metric("Assumed", f"{len(ledger.by_kind(EvidenceKind.ASSUMED))}")
    if error:
        st.warning(f"Valuation not applicable: {error}")
    if not check.ok:
        st.error(f"Citation validation failed: {check.uncited[:3]} {check.unknown_ids[:5]}")
    contra = contradictory_findings(report)
    st.caption(f"Reflects your current Reverse DCF and Thesis Lab inputs. {len(contra)} contradictory finding(s) surfaced.")
    page = memo_to_html(memo, ledger, title=f"{b.ticker} IC Memo")
    c1, c2, _ = st.columns([1, 1, 3])
    c1.download_button("Download Markdown", memo, f"{b.ticker}_ic_memo.md", "text/markdown", disabled=not check.ok)
    c2.download_button("Download HTML", page, f"{b.ticker}_ic_memo.html", "text/html", disabled=not check.ok)
    components.html(memo_to_html(memo, ledger, title=f"{b.ticker} IC Memo", force_light=True), height=900, scrolling=True)

    if settings.anthropic_api_key and st.button("Generate Claude critique (citations verified against the ledger)"):
        from investment_os.research.agent import AnthropicResearchAgent

        try:
            text = AnthropicResearchAgent().checked_analyze(
                ledger=ledger, hypothesis=report.hypothesis,
                model_outputs={"weighted_price": v.weighted_price if v else None, "expectations": v.expectations if v else None},
            )
            st.markdown(text)
        except Exception as exc:  # optional layer must never break the deterministic page
            st.error(f"Critique rejected or failed: {exc}")


def sidebar() -> tuple[str, str | None]:
    st.sidebar.markdown("## Investment OS")
    st.sidebar.caption("Hypothesis → evidence → model → counter-thesis → falsification → decision")
    page = st.sidebar.radio("Workspace", PAGES)
    tickers = available_bundles(OUTPUTS)
    default = tickers.index("VST") if "VST" in tickers else 0
    ticker = st.sidebar.selectbox("Company", tickers, index=default) if tickers else None
    with st.sidebar.expander("Research a new company"):
        new = st.text_input("Ticker", key="new_ticker").strip().upper()
        peers = st.text_input("Peers (comma-separated)", key="new_peers")
        if st.button("Pull from SEC", disabled=not new):
            try:
                with st.spinner(f"Pulling {new} from SEC EDGAR..."):
                    build_bundle(new, peers=tuple(p.strip().upper() for p in peers.split(",") if p.strip()), output_dir=OUTPUTS)
                st.success(f"{new} added.")
                st.rerun()
            except Exception as exc:  # network or unknown ticker: show, do not crash
                st.error(str(exc))
    st.sidebar.caption("Prices: Yahoo Finance (unlicensed). Fundamentals: SEC EDGAR. Not investment advice.")
    return page, ticker


def main() -> None:
    page, ticker = sidebar()
    if page == "Private Markets":
        page_private()
        return
    if ticker is None:
        st.title("Investment OS")
        st.info("No company bundles yet. Use **Research a new company** in the sidebar, or run `python scripts/research_company.py VST --peers CEG,NRG,TLN`.")
        return
    bundle = current_bundle(ticker)
    {"Company Research": page_company, "Reverse DCF": page_valuation, "Thesis Lab": page_thesis, "Alternative Data Lab": page_altdata, "IC Memo": page_memo}[page](bundle)


main()
