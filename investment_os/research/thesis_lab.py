"""Thesis Lab: turn a hypothesis into claims tested against the evidence ledger.

Fully deterministic. Each finding is computed from normalized filings data and cites
evidence ids. A claim that filings cannot test is marked inconclusive rather than
given a plausible-sounding answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pandas as pd

from investment_os.core.evidence import EvidenceLedger
from investment_os.pipeline import ResearchBundle
from investment_os.research.workflow import ValuationPackage
from investment_os.sectors import plugin_for_sic

MIN_CLAIMS, MAX_CLAIMS = 3, 7
ALWAYS = ("growth", "valuation", "balance_sheet")
KEYWORDS = {
    "growth": ("growth", "grow", "revenue", "demand", "sales", "accelerat", "compound"),
    "margin": ("margin", "profit", "pricing", "operating leverage", "earnings", "ebit"),
    "cash": ("cash", "fcf", "conversion", "free cash"),
    "reinvestment": ("capex", "invest", "capacity", "build", "expansion"),
    "balance_sheet": ("debt", "leverage", "balance sheet", "deleverag", "credit"),
    "valuation": ("valuation", "undervalued", "mispriced", "priced", "market", "multiple", "cheap"),
}
HIGH_LEVERAGE = 4.0
LOW_INTEREST_COVER = 2.5
LOW_CASH_CONVERSION = 0.8
MARGIN_VOLATILITY_RATIO = 0.5
HIGH_CAPEX_TO_DNA = 1.5
MATERIAL_UPSIDE = 0.15


@dataclass(frozen=True)
class Finding:
    text: str
    evidence: tuple[str, ...]

    @property
    def citation(self) -> str:
        return " ".join(f"[{e}]" for e in self.evidence)


@dataclass
class ClaimAssessment:
    id: str
    category: str
    statement: str
    evidence_required: tuple[str, ...]
    supporting: list[Finding] = field(default_factory=list)
    contradicting: list[Finding] = field(default_factory=list)
    falsified_if: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.supporting and self.contradicting:
            return "mixed"
        if self.supporting:
            return "supported"
        if self.contradicting:
            return "contradicted"
        return "inconclusive"


@dataclass
class ThesisReport:
    hypothesis: str
    claims: list[ClaimAssessment]
    priced_in: list[Finding]
    catalysts: list[str]
    diligence: list[str]
    sector: str
    limitations: list[str]

    def status_counts(self) -> dict[str, int]:
        counts = {"supported": 0, "mixed": 0, "contradicted": 0, "inconclusive": 0}
        for claim in self.claims:
            counts[claim.status] += 1
        return counts


def select_categories(hypothesis: str) -> list[str]:
    """Always test growth, valuation and balance sheet; add what the hypothesis names."""
    text = hypothesis.lower()
    mentioned = [c for c, words in KEYWORDS.items() if any(w in text for w in words)]
    ordered = list(dict.fromkeys([*ALWAYS, *mentioned]))
    if len(ordered) == len(ALWAYS):
        ordered += ["margin", "cash"]  # a vague thesis gets the full default set
    return ordered


class _Evidence:
    """Helper for looking up values with their ids over the annual history."""

    def __init__(self, bundle: ResearchBundle, ledger: EvidenceLedger):
        self.b, self.ledger = bundle, ledger
        self.annual = bundle.annual.tail(4).reset_index(drop=True)

    def ids(self, name: str, *rows: Any) -> tuple[str, ...]:
        out = []
        for row in rows:
            eid = self.b.evidence_id(name, f"FY{int(row['fiscal_year'])}")
            if eid:
                out.append(eid)
        return tuple(out)

    def ttm(self, *names: str) -> tuple[str, ...]:
        return tuple(f"D.ttm.{n}" for n in names if f"D.ttm.{n}" in self.ledger)


def _growth(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    a = e.annual.dropna(subset=["revenue"])
    if len(a) >= 2:
        first, last = a.iloc[0], a.iloc[-1]
        years = int(last["fiscal_year"] - first["fiscal_year"]) or 1
        cagr = (last["revenue"] / first["revenue"]) ** (1 / years) - 1
        ids = e.ids("revenue", first, last)
        implied = v.expectations.get("implied_revenue_cagr") if v else None
        if implied is not None:
            ids_all = (*ids, "D.implied_revenue_cagr")
            finding = Finding(f"Revenue compounded at {cagr:.1%} over {years} years, against a market-implied {implied:.1%}", ids_all)
            (c.supporting if cagr >= implied else c.contradicting).append(finding)
            c.falsified_if = (f"Revenue growth stays below the market-implied {implied:.1%} for two consecutive fiscal years.",)
        else:
            (c.supporting if cagr > 0 else c.contradicting).append(Finding(f"Revenue compounded at {cagr:.1%} over {years} years", ids))
            c.falsified_if = ("Revenue declines year over year for two consecutive fiscal years.",)
    q = e.b.quarterly.dropna(subset=["revenue"])
    if len(q) >= 5:
        now, prior = q.iloc[-1], q.iloc[-5]
        yoy = now["revenue"] / prior["revenue"] - 1
        ids = tuple(i for i in (e.b.evidence_id("revenue", f"{now['fiscal_year']}{now['fiscal_period']}"), e.b.evidence_id("revenue", f"{prior['fiscal_year']}{prior['fiscal_period']}")) if i)
        (c.supporting if yoy > 0 else c.contradicting).append(Finding(f"Latest quarter revenue changed {yoy:+.1%} year over year", ids))


def _margin(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    a = e.annual.dropna(subset=["revenue", "operating_income"])
    if len(a) >= 2:
        margins = a["operating_income"] / a["revenue"]
        rows = [r for _, r in a.iterrows()]
        ids = (*e.ids("operating_income", rows[0], rows[-1]), *e.ids("revenue", rows[0], rows[-1]))
        (c.supporting if margins.iloc[-1] >= margins.iloc[0] else c.contradicting).append(
            Finding(f"EBIT margin moved from {margins.iloc[0]:.1%} to {margins.iloc[-1]:.1%} over the period", ids))
        spread, centre = float(margins.std(ddof=0)), abs(float(margins.mean()))
        if centre and spread / centre > MARGIN_VOLATILITY_RATIO:
            c.contradicting.append(Finding(f"EBIT margin is volatile (standard deviation {spread:.1%} around a {centre:.1%} mean), which weakens any single-point margin forecast", ids))
    implied = v.expectations.get("implied_ebit_margin") if v else None
    if implied is not None and {"operating_income", "revenue"} <= e.b.ttm.keys():
        current = e.b.ttm["operating_income"] / e.b.ttm["revenue"]
        finding = Finding(f"TTM EBIT margin is {current:.1%}, against a market-implied {implied:.1%}", (*e.ttm("operating_income", "revenue"), "D.implied_ebit_margin"))
        (c.supporting if current >= implied else c.contradicting).append(finding)
        c.falsified_if = (f"TTM EBIT margin stays below {implied:.1%} (market-implied) for four quarters.",)
    else:
        c.falsified_if = ("EBIT margin falls below its three-year median for two consecutive fiscal years.",)


def _cash(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    a = e.annual.dropna(subset=["fcf"])
    if not a.empty:
        positive = int((a["fcf"] > 0).sum())
        ids = tuple(i for _, r in a.iterrows() for i in [e.b.evidence_id("fcf", f"FY{int(r['fiscal_year'])}")] if i)
        (c.supporting if positive == len(a) else c.contradicting).append(Finding(f"Free cash flow was positive in {positive} of the last {len(a)} fiscal years", ids))
    ttm = e.b.ttm
    if ttm.get("net_income", 0) > 0 and "cfo" in ttm:
        ratio = ttm["cfo"] / ttm["net_income"]
        finding = Finding(f"TTM operating cash flow is {ratio:.1f}x net income", e.ttm("cfo", "net_income"))
        (c.supporting if ratio >= LOW_CASH_CONVERSION else c.contradicting).append(finding)
    c.falsified_if = (f"Operating cash flow falls below {LOW_CASH_CONVERSION:.1f}x net income, or TTM free cash flow turns negative.",)


def _reinvestment(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    ttm = e.b.ttm
    if {"capex", "dna"} <= ttm.keys() and ttm["dna"] > 0:
        ratio = ttm["capex"] / ttm["dna"]
        finding = Finding(f"TTM capex is {ratio:.1f}x D&A", e.ttm("capex", "dna"))
        (c.contradicting if ratio > HIGH_CAPEX_TO_DNA else c.supporting).append(finding)
    a = e.annual.dropna(subset=["revenue", "operating_income", "capex"])
    if len(a) >= 2:
        first, last = a.iloc[0], a.iloc[-1]
        d_ebit = last["operating_income"] - first["operating_income"]
        spend = a["capex"].iloc[1:].sum()
        ids = (*e.ids("operating_income", first, last), *e.ids("capex", last))
        sign = "+" if d_ebit >= 0 else "-"
        finding = Finding(f"Cumulative capex of ${spend / 1e9:.1f}B coincided with a {sign}${abs(d_ebit) / 1e9:.1f}B change in annual EBIT", ids)
        (c.supporting if d_ebit > 0 else c.contradicting).append(finding)
    c.falsified_if = ("Capex keeps rising while incremental EBIT stays flat or negative for two fiscal years.",)


def _balance(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    m, ttm = e.b.market, e.b.ttm
    ebitda = ttm["operating_income"] + ttm["dna"] if {"operating_income", "dna"} <= ttm.keys() else None
    sheet = e.b.latest_balance_sheet()
    if sheet is not None and m.get("debt") is not None and ebitda and ebitda > 0:
        period = f"{sheet['fiscal_year']}{sheet['fiscal_period']}"
        leverage = (m["debt"] - m["cash"]) / ebitda
        ids = tuple(i for i in (e.b.evidence_id("debt", period), e.b.evidence_id("cash", period), *e.ttm("operating_income", "dna")) if i)
        (c.contradicting if leverage > HIGH_LEVERAGE else c.supporting).append(Finding(f"Net debt is {leverage:.1f}x TTM EBITDA", ids))
    else:
        c.open_questions += ("Net leverage could not be computed from reliable debt and EBITDA data.",)
    a = e.annual.dropna(subset=["debt"])
    if len(a) >= 2:
        first, last = a.iloc[0], a.iloc[-1]
        ids = e.ids("debt", first, last)
        change = last["debt"] / first["debt"] - 1
        (c.contradicting if change > 0.25 else c.supporting).append(Finding(f"Reconstructed debt changed {change:+.0%} over the period", ids))
    c.falsified_if = (f"Net debt exceeds {HIGH_LEVERAGE:.1f}x TTM EBITDA, or a refinancing occurs at a materially higher cost.",)


def _valuation(c: ClaimAssessment, e: _Evidence, v: ValuationPackage | None) -> None:
    if v is None or "M.price" not in v.ledger:
        c.open_questions += ("Valuation could not be computed for this company.",)
        c.falsified_if = ("Not testable until a valid valuation exists.",)
        return
    price = v.ledger.get("M.price").value
    upside = v.weighted_price / price - 1
    finding = Finding(f"Probability-weighted DCF of ${v.weighted_price:,.2f} is {upside:+.0%} versus the ${price:,.2f} share price", ("D.value.weighted", "M.price"))
    (c.supporting if upside > MATERIAL_UPSIDE else c.contradicting).append(finding)
    if not v.comps_implied.empty:
        row = v.comps_implied.dropna(subset=["implied_price"])
        row = row[row["method"] == "ev_ebitda"]
        if not row.empty:
            implied = float(row["implied_price"].iloc[0])
            comp_up = implied / price - 1
            finding = Finding(f"Peer-median EV/EBITDA implies ${implied:,.2f}, {comp_up:+.0%} versus the share price", ("D.comps.ev_ebitda", "M.price"))
            (c.supporting if comp_up > MATERIAL_UPSIDE else c.contradicting).append(finding)
    c.falsified_if = (f"Sourced base-case value falls within {MATERIAL_UPSIDE:.0%} of, or below, the share price after assumptions are replaced with company-specific estimates.",)


_TEMPLATES = {
    "growth": ("Revenue growth can meet or exceed what the market is discounting.", _growth,
               ("Revenue history", "Reverse DCF implied growth", "Backlog or contracted demand")),
    "margin": ("Operating margins are durable at or above the level the market is discounting.", _margin,
               ("EBIT margin history", "Implied EBIT margin", "Cost structure by segment")),
    "cash": ("Reported earnings convert into free cash flow.", _cash,
             ("CFO and capex history", "Working-capital detail")),
    "reinvestment": ("Capital spending earns an adequate incremental return.", _reinvestment,
                     ("Capex and D&A history", "Incremental EBIT", "Project-level returns")),
    "balance_sheet": ("The balance sheet can absorb the downside case.", _balance,
                      ("Reconstructed debt", "Debt maturity ladder", "Covenants")),
    "valuation": ("The current price offers a margin of safety against independent value.", _valuation,
                  ("DCF scenarios", "Peer multiples", "Consensus estimates")),
}


def run_thesis_lab(
    hypothesis: str,
    bundle: ResearchBundle,
    valuation: ValuationPackage | None,
    *,
    extra_claims: tuple[str, ...] = (),
) -> ThesisReport:
    ledger = valuation.ledger if valuation else bundle.ledger
    evidence = _Evidence(bundle, ledger)
    plugin = plugin_for_sic(bundle.sic)
    claims: list[ClaimAssessment] = []
    room = MAX_CLAIMS - min(len(extra_claims), MAX_CLAIMS - MIN_CLAIMS)
    for i, category in enumerate(select_categories(hypothesis)[:room], 1):
        statement, test, required = _TEMPLATES[category]
        claim = ClaimAssessment(f"C{i}", category, statement, required)
        test(claim, evidence, valuation)
        claims.append(claim)
    for text in extra_claims[: MAX_CLAIMS - len(claims)]:
        claims.append(ClaimAssessment(
            f"C{len(claims) + 1}", "custom", text, ("Primary evidence chosen by the analyst",),
            falsified_if=("Analyst must define a measurable falsification condition before this claim is used.",),
            open_questions=("No automated test exists for this claim; it needs sourced evidence.",),
        ))

    priced_in: list[Finding] = []
    if valuation:
        x = valuation.expectations
        if x.get("implied_revenue_cagr") is not None:
            priced_in.append(Finding(f"Holding margins at the base case, the market EV requires a {x['implied_revenue_cagr']:.1%} revenue CAGR", ("D.implied_revenue_cagr",)))
        if x.get("implied_ebit_margin") is not None:
            priced_in.append(Finding(f"Holding growth at the base case, the market EV requires a {x['implied_ebit_margin']:.1%} EBIT margin", ("D.implied_ebit_margin",)))
        if x.get("implied_fcff_cagr") is not None:
            priced_in.append(Finding(f"From base-period FCFF, the market EV requires a {x['implied_fcff_cagr']:.1%} FCFF CAGR", ("D.implied_fcff_cagr",)))

    catalysts = list(plugin.catalysts)
    periodic = bundle.filings[bundle.filings["form"].isin(["10-Q", "10-K"])] if not bundle.filings.empty else pd.DataFrame()
    if not periodic.empty:
        last_filed = pd.Timestamp(periodic["filed"].iloc[0])
        estimate = (last_filed + timedelta(days=91)).date()
        catalysts.insert(0, f"Next periodic filing, estimated around {estimate} from past filing cadence")

    diligence = list(dict.fromkeys([
        *plugin.diligence,
        "Replace placeholder WACC and terminal growth with a company-specific build-up.",
        "Source consensus estimates; this system has none and does not infer them.",
        *(q for c in claims for q in c.open_questions),
    ]))
    limitations = [
        "Findings test only what standardized XBRL data can show; segment and footnote detail are not parsed.",
        "No consensus estimates, so the variant view is measured against reverse-DCF expectations.",
    ]
    return ThesisReport(hypothesis, claims, priced_in, catalysts, diligence, plugin.name, limitations)


def contradictory_findings(report: ThesisReport) -> list[tuple[str, Finding]]:
    return [(c.id, f) for c in report.claims for f in c.contradicting]
