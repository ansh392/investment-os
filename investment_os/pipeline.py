"""Real-company research pipeline: ticker -> filings -> history -> market -> evidence bundle."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from investment_os.core.evidence import (
    EvidenceItem,
    EvidenceKind,
    EvidenceLedger,
    now_iso,
)
from investment_os.data.market import PRICE_SOURCE_URL, price_frame
from investment_os.data.normalize import (
    NormalizedFinancials,
    latest_shares_outstanding,
    normalize_company_facts,
    trailing_twelve_months,
)
from investment_os.data.sec import (
    SEC_COMPANYFACTS_URL,
    SECClient,
    filing_url,
    filings_frame,
)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
EVIDENCE_ANNUAL_YEARS = 6
EVIDENCE_QUARTERS = 8
STALE_SHARES_DAYS = 135
STALE_BALANCE_SHEET_DAYS = 135
FLOW_FIELDS = ("revenue", "operating_income", "net_income", "cfo", "capex", "dna")
INSTANT_FIELDS = ("cash", "total_assets", "total_liabilities", "noncontrolling_interest", "preferred_stock")
TTM_FIELDS = ("revenue", "operating_income", "net_income", "cfo", "capex", "dna")
# SIC 6000-6799: banks, insurers, brokers, REITs. Debt is raw material, not financing.
FINANCIAL_SIC_RANGE = (6000, 6799)

PriceFetcher = Callable[[str], pd.DataFrame]


@dataclass
class ResearchBundle:
    ticker: str
    cik: int
    name: str
    sic: str
    sic_description: str
    retrieved_at: str
    annual: pd.DataFrame
    quarterly: pd.DataFrame
    lineage: pd.DataFrame
    filings: pd.DataFrame
    prices: pd.DataFrame
    market: dict[str, Any]
    ttm: dict[str, Any]
    ledger: EvidenceLedger
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    peers: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def is_financial(self) -> bool:
        return self.sic.isdigit() and FINANCIAL_SIC_RANGE[0] <= int(self.sic) <= FINANCIAL_SIC_RANGE[1]

    def latest_balance_sheet(self) -> pd.Series | None:
        for frame in (self.quarterly, self.annual):
            if not frame.empty:
                return frame.iloc[-1]
        return None

    def evidence_id(self, name: str, period: str) -> str | None:
        """Evidence id for a metric-period pair, whichever kind it was recorded as."""
        for prefix in ("R", "D"):
            candidate = f"{prefix}.{name}.{period}"
            if candidate in self.ledger:
                return candidate
        return None


def _period_key(row: dict[str, Any]) -> str:
    if row["period_type"] == "annual":
        return f"FY{row['fiscal_year']}"
    return f"{row['fiscal_year']}{row['fiscal_period']}"


def _as_float(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def build_ledger(
    *,
    ticker: str,
    cik: int,
    normalized: NormalizedFinancials,
    filings: pd.DataFrame,
    retrieved_at: str,
) -> EvidenceLedger:
    """Evidence items for recent periods, each linked to the filing it came from."""
    ledger = EvidenceLedger()
    if normalized.lineage.empty:
        return ledger
    urls = dict(zip(filings["accession"], filings["url"])) if not filings.empty else {}
    lineage = normalized.lineage
    keep_annual = set(normalized.annual["period_end"].tail(EVIDENCE_ANNUAL_YEARS))
    keep_quarter = set(normalized.quarterly["period_end"].tail(EVIDENCE_QUARTERS))

    selected = lineage[
        ((lineage["period_type"] == "annual") & lineage["period_end"].isin(keep_annual))
        | ((lineage["period_type"] == "quarterly") & lineage["period_end"].isin(keep_quarter))
    ]
    for row in selected.to_dict("records"):
        name = row["field"]
        if name not in FLOW_FIELDS + INSTANT_FIELDS + ("debt",):
            continue
        reported = row["derivation"] == "reported"
        period = _period_key(row)
        accession = row["accession"]
        ledger.add(EvidenceItem(
            id=f"{'R' if reported else 'D'}.{name}.{period}",
            claim=f"{ticker} {name.replace('_', ' ')}, {period}",
            value=row["value"],
            kind=EvidenceKind.REPORTED if reported else EvidenceKind.DERIVED,
            source=urls.get(accession) or filing_url(cik, accession),
            retrieved_at=retrieved_at,
            unit=row["unit"],
            form=row["form"],
            period=row["period_end"],
            filed=row["filed"],
            accession=accession,
            notes=(
                f"XBRL concept: {row['concept']}" if reported
                else f"Method: {row['derivation']}; concept/method: {row['concept']}; components: {row['components']}"
            ) + ("; value differs across filings (restated)" if row["restated"] else ""),
        ))

    frames = [("annual", normalized.annual.tail(EVIDENCE_ANNUAL_YEARS)), ("quarterly", normalized.quarterly.tail(EVIDENCE_QUARTERS))]
    for ptype, frame in frames:
        for row in frame.to_dict("records"):
            if pd.isna(row["fcf"]):
                continue
            period = _period_key({"period_type": ptype, "fiscal_year": row["fiscal_year"], "fiscal_period": row["fiscal_period"]})
            inputs = tuple(i for i in (_find(ledger, "cfo", period), _find(ledger, "capex", period)) if i)
            if len(inputs) == 2:
                ledger.add(EvidenceItem(
                    id=f"D.fcf.{period}", claim=f"{ticker} free cash flow (CFO less capex), {period}",
                    value=row["fcf"], kind=EvidenceKind.DERIVED, unit="USD", period=row["period_end"],
                    retrieved_at=retrieved_at, inputs=inputs,
                ))
    return ledger


def _find(ledger: EvidenceLedger, name: str, period: str) -> str | None:
    for prefix in ("R", "D"):
        candidate = f"{prefix}.{name}.{period}"
        if candidate in ledger:
            return candidate
    return None


def _build_ttm(
    ticker: str, normalized: NormalizedFinancials, ledger: EvidenceLedger, retrieved_at: str, warnings: list[str],
) -> dict[str, Any]:
    ttm: dict[str, Any] = {}
    quarterly = normalized.quarterly
    for name in TTM_FIELDS:
        result = trailing_twelve_months(quarterly, name)
        if result is None:
            warnings.append(f"TTM {name}: four contiguous quarters unavailable; TTM left missing.")
            continue
        value, end = result
        ttm[name] = value
        ttm["as_of"] = end
        periods = quarterly.dropna(subset=[name]).tail(4)
        inputs = tuple(
            i for i in (_find(ledger, name, f"{r.fiscal_year}{r.fiscal_period}") for r in periods.itertuples()) if i
        )
        if len(inputs) == 4:
            ledger.add(EvidenceItem(
                id=f"D.ttm.{name}", claim=f"{ticker} trailing-twelve-month {name.replace('_', ' ')}",
                value=value, kind=EvidenceKind.DERIVED, unit="USD", period=end, retrieved_at=retrieved_at, inputs=inputs,
            ))
    if "cfo" in ttm and "capex" in ttm and "D.ttm.cfo" in ledger and "D.ttm.capex" in ledger:
        ttm["fcf"] = ttm["cfo"] - ttm["capex"]
        ledger.add(EvidenceItem(
            id="D.ttm.fcf", claim=f"{ticker} trailing-twelve-month free cash flow", value=ttm["fcf"],
            kind=EvidenceKind.DERIVED, unit="USD", period=ttm["as_of"], retrieved_at=retrieved_at,
            inputs=("D.ttm.cfo", "D.ttm.capex"),
        ))
    return ttm


def build_market_snapshot(
    *,
    ticker: str,
    cik: int,
    companyfacts: dict[str, Any],
    normalized: NormalizedFinancials,
    prices: pd.DataFrame,
    filings: pd.DataFrame,
    ledger: EvidenceLedger,
    retrieved_at: str,
    warnings: list[str],
) -> dict[str, Any]:
    """Market cap and EV, computed only from inputs that are actually available."""
    market: dict[str, Any] = {"price": None, "price_date": None, "shares": None, "market_cap": None, "enterprise_value": None, "net_claims": None}
    if prices.empty:
        warnings.append("Market price unavailable; market cap and EV not computed.")
    else:
        last = prices.iloc[-1]
        market["price"] = float(last["close"])
        market["price_date"] = pd.Timestamp(last["date"]).date().isoformat()
        ledger.add(EvidenceItem(
            id="M.price", claim=f"{ticker} closing share price", value=market["price"], kind=EvidenceKind.REPORTED,
            source=PRICE_SOURCE_URL.format(ticker=ticker), retrieved_at=retrieved_at, unit="USD/share",
            period=market["price_date"], notes="Yahoo Finance via yfinance; an unlicensed convenience source, verify before use.",
        ))

    shares = latest_shares_outstanding(companyfacts)
    if shares is None:
        warnings.append("Shares outstanding unavailable in SEC data; market cap not computed.")
    else:
        market["shares"], market["shares_as_of"] = shares["shares"], shares["as_of"]
        urls = dict(zip(filings["accession"], filings["url"])) if not filings.empty else {}
        ledger.add(EvidenceItem(
            id="R.shares", claim=f"{ticker} common shares outstanding", value=shares["shares"], kind=EvidenceKind.REPORTED,
            source=urls.get(shares["accession"]) or filing_url(cik, shares["accession"]), retrieved_at=retrieved_at,
            unit="shares", form=shares["form"], period=shares["as_of"], filed=shares["filed"], accession=shares["accession"],
            notes=f"XBRL concept: {shares['concept']}. Basic count; excludes dilution from options, RSUs and convertibles.",
        ))
        if market["price_date"] and (date.fromisoformat(market["price_date"]) - date.fromisoformat(shares["as_of"])).days > STALE_SHARES_DAYS:
            warnings.append(f"Share count is dated {shares['as_of']}, more than {STALE_SHARES_DAYS} days before the price date.")

    if market["price"] is None or market["shares"] is None:
        return market
    market["market_cap"] = market["price"] * market["shares"]
    ledger.add(EvidenceItem(
        id="D.market_cap", claim=f"{ticker} market capitalization (price x basic shares)", value=market["market_cap"],
        kind=EvidenceKind.DERIVED, unit="USD", period=market["price_date"], retrieved_at=retrieved_at, inputs=("M.price", "R.shares"),
    ))

    frame = normalized.quarterly if not normalized.quarterly.empty else normalized.annual
    if frame.empty:
        warnings.append("No balance sheet available; EV not computed.")
        return market
    sheet = frame.iloc[-1]
    period = _period_key({
        "period_type": "quarterly" if frame is normalized.quarterly else "annual",
        "fiscal_year": sheet["fiscal_year"], "fiscal_period": sheet["fiscal_period"],
    })
    market["balance_sheet_date"] = sheet["period_end"]
    if market["price_date"] and (date.fromisoformat(market["price_date"]) - date.fromisoformat(sheet["period_end"])).days > STALE_BALANCE_SHEET_DAYS:
        warnings.append(f"Latest balance sheet ({sheet['period_end']}) is more than {STALE_BALANCE_SHEET_DAYS} days before the price date.")
    debt, cash = _as_float(sheet["debt"]), _as_float(sheet["cash"])
    if debt is None or cash is None:
        missing = [n for n, v in (("debt", debt), ("cash", cash)) if v is None]
        warnings.append(f"Enterprise value not computed: reliable {' and '.join(missing)} unavailable at {sheet['period_end']}.")
        return market
    nci = _as_float(sheet["noncontrolling_interest"]) or 0.0
    preferred = _as_float(sheet["preferred_stock"]) or 0.0
    market.update(debt=debt, cash=cash, noncontrolling_interest=nci, preferred_stock=preferred)
    market["net_claims"] = debt + nci + preferred - cash
    market["enterprise_value"] = market["market_cap"] + market["net_claims"]
    inputs = [i for i in ("D.market_cap", _find(ledger, "debt", period), _find(ledger, "cash", period),
                          _find(ledger, "noncontrolling_interest", period), _find(ledger, "preferred_stock", period)) if i]
    ledger.add(EvidenceItem(
        id="D.enterprise_value", claim=f"{ticker} enterprise value (market cap + debt + NCI + preferred - cash)",
        value=market["enterprise_value"], kind=EvidenceKind.DERIVED, unit="USD", period=market["price_date"],
        retrieved_at=retrieved_at, inputs=tuple(inputs),
        notes="NCI and preferred at book value; operating leases excluded.",
    ))
    return market


def build_bundle(
    ticker: str,
    *,
    client: SECClient | None = None,
    price_fetcher: PriceFetcher = price_frame,
    peers: tuple[str, ...] = (),
    output_dir: Path | None = DEFAULT_OUTPUT_DIR,
) -> ResearchBundle:
    """Fetch, normalize and persist one company. Pass ``output_dir=None`` to skip writing."""
    symbol = ticker.upper()
    client = client or SECClient()
    cik = client.cik_for_ticker(symbol)
    retrieved_at = now_iso()
    companyfacts = client.companyfacts(symbol)
    submissions = client.submissions(cik)
    filings = filings_frame(submissions)
    normalized = normalize_company_facts(companyfacts)
    warnings = list(normalized.warnings)

    try:
        prices = price_fetcher(symbol)
    except Exception as exc:  # third-party source; surfaced, never papered over
        warnings.append(f"Market price download failed: {exc}")
        prices = pd.DataFrame(columns=["date", "close", "adj_close", "volume"])

    ledger = build_ledger(ticker=symbol, cik=cik, normalized=normalized, filings=filings, retrieved_at=retrieved_at)
    ttm = _build_ttm(symbol, normalized, ledger, retrieved_at, warnings)
    market = build_market_snapshot(
        ticker=symbol, cik=cik, companyfacts=companyfacts, normalized=normalized, prices=prices,
        filings=filings, ledger=ledger, retrieved_at=retrieved_at, warnings=warnings,
    )
    bundle = ResearchBundle(
        ticker=symbol, cik=cik, name=submissions.get("name") or companyfacts.get("entityName", symbol),
        sic=str(submissions.get("sic", "")), sic_description=submissions.get("sicDescription", ""),
        retrieved_at=retrieved_at, annual=normalized.annual, quarterly=normalized.quarterly, lineage=normalized.lineage,
        filings=filings, prices=prices, market=market, ttm=ttm, ledger=ledger, warnings=warnings, notes=normalized.notes,
    )
    if bundle.is_financial:
        bundle.warnings.append(
            f"SIC {bundle.sic} ({bundle.sic_description}) is a financial company: FCFF DCF and EV multiples are not meaningful and are disabled."
        )
    if peers:
        bundle.peers = pd.DataFrame(_peer_rows(peers, client, price_fetcher, bundle))
    if output_dir is not None:
        save_bundle(bundle, Path(output_dir), companyfacts, submissions)
    return bundle


def _peer_rows(peers: tuple[str, ...], client: SECClient, price_fetcher: PriceFetcher, target: ResearchBundle) -> list[dict[str, Any]]:
    rows = []
    for peer in peers:
        try:
            b = build_bundle(peer, client=client, price_fetcher=price_fetcher, output_dir=None)
        except Exception as exc:  # one failed peer should not sink the target's research
            target.warnings.append(f"Peer {peer} failed: {exc}")
            continue
        ebitda = None
        if "operating_income" in b.ttm and "dna" in b.ttm:
            ebitda = b.ttm["operating_income"] + b.ttm["dna"]
        rows.append({
            "ticker": b.ticker, "enterprise_value": b.market.get("enterprise_value"), "market_cap": b.market.get("market_cap"),
            "revenue": b.ttm.get("revenue"), "ebitda": ebitda, "fcf": b.ttm.get("fcf"), "net_income": b.ttm.get("net_income"),
            "source": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={b.cik}", "retrieved_at": b.retrieved_at,
            "origin": "derived",
        })
    return rows


def save_bundle(bundle: ResearchBundle, root: Path, companyfacts: dict[str, Any], submissions: dict[str, Any]) -> Path:
    out = root / bundle.ticker
    (out / "raw").mkdir(parents=True, exist_ok=True)
    manifest = {
        "ticker": bundle.ticker, "cik": bundle.cik, "name": bundle.name, "sic": bundle.sic,
        "sic_description": bundle.sic_description, "retrieved_at": bundle.retrieved_at,
        "sources": {"companyfacts": SEC_COMPANYFACTS_URL.format(cik=bundle.cik), "prices": PRICE_SOURCE_URL.format(ticker=bundle.ticker)},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "market.json").write_text(json.dumps(bundle.market, indent=2), encoding="utf-8")
    (out / "ttm.json").write_text(json.dumps(bundle.ttm, indent=2), encoding="utf-8")
    (out / "warnings.json").write_text(json.dumps({"warnings": bundle.warnings, "notes": bundle.notes}, indent=2), encoding="utf-8")
    (out / "evidence.json").write_text(json.dumps(bundle.ledger.as_list(), indent=2, default=str), encoding="utf-8")
    for name, frame in (("annual", bundle.annual), ("quarterly", bundle.quarterly), ("lineage", bundle.lineage),
                        ("filings", bundle.filings), ("prices", bundle.prices), ("peers", bundle.peers)):
        frame.to_csv(out / f"{name}.csv", index=False)
    (out / "raw" / "companyfacts.json").write_text(json.dumps(companyfacts), encoding="utf-8")
    (out / "raw" / "submissions.json").write_text(json.dumps(submissions), encoding="utf-8")
    return out


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def load_bundle(ticker: str, root: Path = DEFAULT_OUTPUT_DIR) -> ResearchBundle:
    """Reload a saved bundle, so analysis can run without network access."""
    out = Path(root) / ticker.upper()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    logs = json.loads((out / "warnings.json").read_text(encoding="utf-8"))
    prices = _read_csv(out / "prices.csv")
    if not prices.empty:
        prices["date"] = pd.to_datetime(prices["date"])
    return ResearchBundle(
        ticker=manifest["ticker"], cik=manifest["cik"], name=manifest["name"], sic=str(manifest["sic"]),
        sic_description=manifest["sic_description"], retrieved_at=manifest["retrieved_at"],
        annual=_read_csv(out / "annual.csv"), quarterly=_read_csv(out / "quarterly.csv"), lineage=_read_csv(out / "lineage.csv"),
        filings=_read_csv(out / "filings.csv"), prices=prices,
        market=json.loads((out / "market.json").read_text(encoding="utf-8")),
        ttm=json.loads((out / "ttm.json").read_text(encoding="utf-8")),
        ledger=EvidenceLedger.from_list(json.loads((out / "evidence.json").read_text(encoding="utf-8"))),
        warnings=logs["warnings"], notes=logs["notes"], peers=_read_csv(out / "peers.csv"),
    )


def available_bundles(root: Path = DEFAULT_OUTPUT_DIR) -> list[str]:
    root = Path(root)
    return sorted(p.name for p in root.iterdir() if (p / "manifest.json").exists()) if root.exists() else []
