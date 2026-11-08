"""Connects a research bundle to valuation and records every output as evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from investment_os.core.evidence import EvidenceItem, EvidenceKind, EvidenceLedger
from investment_os.models.workspace import (
    BaseFinancials,
    OperatingAssumptions,
    ScenarioResult,
    ValuationNotApplicable,
    comps_implied_values,
    comps_table,
    default_scenarios,
    derive_base_financials,
    market_expectations,
    probability_weighted_price,
    sensitivity,
    value_scenario,
    DEFAULT_TERMINAL_GROWTH,
    DEFAULT_WACC,
    HIGH_TERMINAL_SHARE,
)
from investment_os.pipeline import ResearchBundle


@dataclass
class ValuationPackage:
    base: BaseFinancials
    results: dict[str, ScenarioResult]
    weighted_price: float
    expectations: dict[str, Any]
    sensitivity: pd.DataFrame
    base_fcff: float | None
    ledger: EvidenceLedger
    comps: pd.DataFrame = field(default_factory=pd.DataFrame)
    comps_implied: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)

    @property
    def upside(self) -> float | None:
        price = self.ledger.get("M.price").value if "M.price" in self.ledger else None
        return self.weighted_price / price - 1 if price else None


def _base_fcff(base: BaseFinancials, bundle: ResearchBundle) -> float | None:
    """Unlevered base-period FCFF: taxed EBIT plus D&A less capex (before working capital)."""
    ttm = bundle.ttm
    if not all(k in ttm for k in ("operating_income", "dna", "capex")):
        return None
    ebit = ttm["operating_income"]
    return ebit - max(0.0, ebit * base.tax_rate) + ttm["dna"] - ttm["capex"]


def _record_assumptions(ledger: EvidenceLedger, base: BaseFinancials, scenarios: dict[str, OperatingAssumptions]) -> None:
    a = scenarios["base"]
    entries = [
        ("A.growth_anchor", "Base-case initial revenue growth", base.growth_anchor, base.provenance["growth"]),
        ("A.ebit_margin", "Base-case EBIT margin", base.margin_anchor, base.provenance["margin"]),
        ("A.tax_rate", "Tax rate", base.tax_rate, base.provenance["tax"]),
        ("A.dna_pct", "D&A as share of revenue", base.dna_pct_revenue, base.provenance["dna"]),
        ("A.capex_pct", "Capex as share of revenue", base.capex_pct_revenue, base.provenance["capex"]),
        ("A.nwc_pct", "Working capital as share of incremental revenue", a.nwc_pct_delta_revenue, base.provenance["nwc"]),
        ("A.wacc", "Weighted average cost of capital", a.wacc, base.provenance["wacc"]),
        ("A.terminal_growth", "Terminal growth rate", a.terminal_growth, base.provenance["terminal_growth"]),
    ]
    for eid, claim, value, note in entries:
        ledger.add(EvidenceItem(eid, claim, round(value, 6), EvidenceKind.ASSUMED, notes=note, unit="ratio"))
    for name, s in scenarios.items():
        ledger.add(EvidenceItem(
            f"A.scenario.{name}", f"{name.title()} scenario path",
            f"growth {s.revenue_growth[0]:.1%} fading to {s.revenue_growth[-1]:.1%}; EBIT margin {s.ebit_margin[0]:.1%}; probability {s.probability:.0%}",
            EvidenceKind.ASSUMED, notes="Mechanical shift around the base anchors; analyst should override.",
        ))


def run_valuation(
    bundle: ResearchBundle,
    *,
    wacc: float = DEFAULT_WACC,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    scenarios: dict[str, OperatingAssumptions] | None = None,
) -> ValuationPackage:
    """Value a company, or raise ``ValuationNotApplicable`` explaining why it cannot be."""
    if bundle.is_financial:
        raise ValuationNotApplicable(
            f"{bundle.name} is a financial company (SIC {bundle.sic}); FCFF DCF is not meaningful. Use book-value or dividend-based methods."
        )
    if not bundle.market.get("shares"):
        raise ValuationNotApplicable("Shares outstanding are unavailable.")
    if bundle.market.get("net_claims") is None:
        raise ValuationNotApplicable("Net debt could not be reliably reconstructed, so equity value cannot be bridged.")
    try:
        base = derive_base_financials(bundle.annual, bundle.ttm)
    except ValueError as exc:
        raise ValuationNotApplicable(str(exc)) from exc

    scenarios = scenarios or default_scenarios(base, wacc=wacc, terminal_growth=terminal_growth)
    ledger = EvidenceLedger(bundle.ledger.items())
    _record_assumptions(ledger, base, scenarios)
    net_claims, shares = bundle.market["net_claims"], bundle.market["shares"]
    results = {k: value_scenario(base.revenue, a, net_claims, shares) for k, a in scenarios.items()}
    weighted = probability_weighted_price(results)

    warnings: list[str] = []
    for name, result in results.items():
        inputs = tuple(i for i in ("A.growth_anchor", "A.ebit_margin", "A.wacc", "A.terminal_growth", f"A.scenario.{name}", "D.enterprise_value") if i in ledger)
        ledger.add(EvidenceItem(
            f"D.value.{name}", f"{name.title()} DCF value per share", round(result.implied_price, 2),
            EvidenceKind.DERIVED, source="Investment OS valuation model", unit="USD/share", inputs=inputs,
        ))
        if result.terminal_share > HIGH_TERMINAL_SHARE:
            warnings.append(f"{name} case: terminal value is {result.terminal_share:.0%} of EV, so the result is dominated by WACC and terminal growth.")
    ledger.add(EvidenceItem(
        "D.value.weighted", "Probability-weighted DCF value per share", round(weighted, 2), EvidenceKind.DERIVED,
        source="Investment OS valuation model", unit="USD/share", inputs=tuple(f"D.value.{k}" for k in results),
    ))

    fcff = _base_fcff(base, bundle)
    ev = bundle.market.get("enterprise_value")
    expectations: dict[str, Any] = {"implied_fcff_cagr": None, "implied_revenue_cagr": None, "implied_ebit_margin": None, "notes": []}
    if ev and ev > 0:
        expectations = market_expectations(ev, base.revenue, fcff, scenarios["base"])
        labels = {"implied_fcff_cagr": "FCFF CAGR", "implied_revenue_cagr": "revenue CAGR", "implied_ebit_margin": "EBIT margin"}
        for key, label in labels.items():
            if expectations[key] is not None:
                ledger.add(EvidenceItem(
                    f"D.{key}", f"Market-implied {label} (reverse DCF)", round(expectations[key], 4), EvidenceKind.DERIVED,
                    source="Investment OS reverse DCF", unit="ratio",
                    inputs=tuple(i for i in ("D.enterprise_value", "A.wacc", "A.terminal_growth", "A.ebit_margin") if i in ledger),
                ))
    else:
        expectations["notes"].append("Reverse DCF skipped: market enterprise value is unavailable or non-positive.")

    comps, implied = pd.DataFrame(), pd.DataFrame()
    if not bundle.peers.empty:
        comps = comps_table(bundle.peers)
        ebitda = bundle.ttm["operating_income"] + bundle.ttm["dna"] if {"operating_income", "dna"} <= bundle.ttm.keys() else None
        implied = comps_implied_values(comps, {"ebitda": ebitda, "revenue": bundle.ttm.get("revenue"), "net_income": bundle.ttm.get("net_income")}, net_claims, shares)
        for row in implied.dropna(subset=["implied_price"]).to_dict("records"):
            ledger.add(EvidenceItem(
                f"D.comps.{row['method']}", f"Implied price at peer-median {row['method']} ({row['peer_median']:.1f}x)",
                round(row["implied_price"], 2), EvidenceKind.DERIVED,
                source=";".join(comps.loc[comps["sourced"], "source"].astype(str)), unit="USD/share", retrieved_at=bundle.retrieved_at,
            ))

    return ValuationPackage(
        base=base, results=results, weighted_price=weighted, expectations=expectations, sensitivity=sensitivity(results["base"]),
        base_fcff=fcff, ledger=ledger, comps=comps, comps_implied=implied, warnings=warnings,
    )
