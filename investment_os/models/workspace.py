"""Valuation workspace: operating assumptions -> FCFF -> EV -> equity -> per share.

All discounting goes through ``models.valuation.dcf_valuation``. Default assumptions
are mechanical anchors computed from reported history and labeled ``assumed``; they
are a starting point for the analyst, not a forecast.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from investment_os.models.valuation import (
    DCFInputs,
    dcf_sensitivity_table,
    dcf_valuation,
    reverse_dcf_implied_growth,
)

DEFAULT_YEARS = 5
DEFAULT_WACC = 0.09
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_TAX_RATE = 0.21
DEFAULT_NWC_PCT = 0.10
GROWTH_CLIP = (-0.05, 0.20)
TAX_CLIP = (0.0, 0.35)
SCENARIO_GROWTH_SHIFT = 0.04
SCENARIO_MARGIN_SHIFT_FLOOR = 0.02
SCENARIO_MARGIN_SHIFT_PCT = 0.20
SCENARIO_PROBABILITIES = {"bear": 0.25, "base": 0.50, "bull": 0.25}
HIGH_TERMINAL_SHARE = 0.75


class ValuationNotApplicable(ValueError):
    """The model cannot be applied to this company with the data available."""


@dataclass(frozen=True)
class OperatingAssumptions:
    name: str
    revenue_growth: tuple[float, ...]
    ebit_margin: tuple[float, ...]
    tax_rate: float
    dna_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_delta_revenue: float
    wacc: float
    terminal_growth: float
    probability: float = 1.0

    def __post_init__(self) -> None:
        if len(self.revenue_growth) != len(self.ebit_margin) or not self.revenue_growth:
            raise ValueError("revenue_growth and ebit_margin must be the same non-zero length")


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    assumptions: OperatingAssumptions
    bridge: pd.DataFrame
    dcf: dict[str, float]
    net_claims: float
    shares: float

    @property
    def implied_price(self) -> float:
        return self.dcf["implied_price"]

    @property
    def terminal_share(self) -> float:
        return self.dcf["pv_terminal"] / self.dcf["enterprise_value"] if self.dcf["enterprise_value"] else float("nan")


@dataclass(frozen=True)
class BaseFinancials:
    """Starting point for forecasts, with the rule behind each anchor."""

    revenue: float
    revenue_basis: str
    growth_anchor: float
    margin_anchor: float
    tax_rate: float
    dna_pct_revenue: float
    capex_pct_revenue: float
    provenance: dict[str, str]


def build_bridge(base_revenue: float, a: OperatingAssumptions) -> pd.DataFrame:
    """Year-by-year operating bridge from revenue to unlevered free cash flow."""
    rows = []
    prior = base_revenue
    for year, (growth, margin) in enumerate(zip(a.revenue_growth, a.ebit_margin), 1):
        revenue = prior * (1 + growth)
        ebit = revenue * margin
        # No tax shield on operating losses: conservative and avoids negative tax.
        taxes = max(0.0, ebit * a.tax_rate)
        nopat = ebit - taxes
        dna = revenue * a.dna_pct_revenue
        capex = revenue * a.capex_pct_revenue
        delta_nwc = (revenue - prior) * a.nwc_pct_delta_revenue
        rows.append({
            "year": year, "revenue": revenue, "growth": growth, "ebit_margin": margin, "ebit": ebit, "taxes": taxes,
            "nopat": nopat, "dna": dna, "capex": capex, "delta_nwc": delta_nwc, "fcff": nopat + dna - capex - delta_nwc,
        })
        prior = revenue
    return pd.DataFrame(rows)


def value_scenario(base_revenue: float, a: OperatingAssumptions, net_claims: float, shares: float) -> ScenarioResult:
    bridge = build_bridge(base_revenue, a)
    dcf = dcf_valuation(DCFInputs(tuple(bridge["fcff"]), a.wacc, a.terminal_growth, net_claims, shares))
    return ScenarioResult(a.name, a, bridge, dcf, net_claims, shares)


def value_bridge_table(result: ScenarioResult) -> pd.DataFrame:
    """Waterfall from discounted cash flows to value per share."""
    d = result.dcf
    return pd.DataFrame([
        ("PV of forecast FCFF", d["pv_explicit"]),
        ("PV of terminal value", d["pv_terminal"]),
        ("Enterprise value", d["enterprise_value"]),
        ("Less: net claims (debt + NCI + preferred - cash)", -result.net_claims),
        ("Equity value", d["equity_value"]),
        ("Shares outstanding", result.shares),
        ("Implied value per share", d["implied_price"]),
    ], columns=["line", "value"])


def _median_ratio(num: pd.Series, den: pd.Series) -> float | None:
    ratio = (num / den).replace([np.inf, -np.inf], np.nan).dropna()
    return float(ratio.median()) if len(ratio) else None


def derive_base_financials(annual: pd.DataFrame, ttm: dict[str, Any], *, lookback: int = 3) -> BaseFinancials:
    """Compute forecast anchors from reported history; raise if the core is missing."""
    frame = annual.dropna(subset=["revenue"]).tail(lookback + 1)
    if len(frame) < 2:
        raise ValueError("At least two fiscal years of revenue are required")
    recent = frame.tail(lookback)
    growth = frame["revenue"].pct_change().dropna()
    margin = _median_ratio(recent["operating_income"], recent["revenue"])
    if margin is None:
        raise ValueError("Operating income history is unavailable, so EBIT margin cannot be anchored")
    revenue, basis = (ttm["revenue"], f"TTM to {ttm.get('as_of')}") if ttm.get("revenue") else (
        float(frame["revenue"].iloc[-1]), f"FY{int(frame['fiscal_year'].iloc[-1])}"
    )
    raw_tax = _median_ratio(recent["income_tax"], recent["pretax_income"].where(recent["pretax_income"] > 0))
    tax_note = f"Median effective rate, last {lookback} FY, clipped to {TAX_CLIP[0]:.0%}-{TAX_CLIP[1]:.0%}"
    if raw_tax is None:
        tax, tax_note = DEFAULT_TAX_RATE, "US statutory rate; effective rate unavailable"
    else:
        tax = float(np.clip(raw_tax, *TAX_CLIP))
    dna_pct = _median_ratio(recent["dna"], recent["revenue"])
    capex_pct = _median_ratio(recent["capex"], recent["revenue"])
    if dna_pct is None or capex_pct is None:
        raise ValueError("D&A or capex history is unavailable, so reinvestment cannot be anchored")
    return BaseFinancials(
        revenue=float(revenue), revenue_basis=basis, growth_anchor=float(np.clip(growth.median(), *GROWTH_CLIP)),
        margin_anchor=margin, tax_rate=tax, dna_pct_revenue=dna_pct, capex_pct_revenue=capex_pct,
        provenance={
            "growth": f"Median annual revenue growth, last {lookback} FY, clipped to {GROWTH_CLIP[0]:.0%}/{GROWTH_CLIP[1]:.0%}; fades to terminal growth",
            "margin": f"Median EBIT margin, last {lookback} FY",
            "tax": tax_note,
            "dna": f"Median D&A / revenue, last {lookback} FY",
            "capex": f"Median capex / revenue, last {lookback} FY",
            "nwc": "Placeholder: 10% of incremental revenue; not derived from company data",
            "wacc": "Placeholder: 9% with no company-specific build-up; override it",
            "terminal_growth": "Placeholder: 2.5%, roughly long-run nominal growth; override it",
        },
    )


def _fade(start: float, end: float, years: int) -> tuple[float, ...]:
    return tuple(float(x) for x in np.linspace(start, end, years))


def default_scenarios(
    base: BaseFinancials, *, years: int = DEFAULT_YEARS, wacc: float = DEFAULT_WACC, terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
) -> dict[str, OperatingAssumptions]:
    margin_shift = max(SCENARIO_MARGIN_SHIFT_FLOOR, abs(base.margin_anchor) * SCENARIO_MARGIN_SHIFT_PCT)
    out = {}
    for name, sign in (("bear", -1), ("base", 0), ("bull", 1)):
        out[name] = OperatingAssumptions(
            name=name,
            revenue_growth=_fade(base.growth_anchor + sign * SCENARIO_GROWTH_SHIFT, terminal_growth + sign * 0.01, years),
            ebit_margin=(base.margin_anchor + sign * margin_shift,) * years,
            tax_rate=base.tax_rate, dna_pct_revenue=base.dna_pct_revenue, capex_pct_revenue=base.capex_pct_revenue,
            nwc_pct_delta_revenue=DEFAULT_NWC_PCT, wacc=wacc, terminal_growth=terminal_growth,
            probability=SCENARIO_PROBABILITIES[name],
        )
    return out


def probability_weighted_price(results: dict[str, ScenarioResult]) -> float:
    total = sum(r.assumptions.probability for r in results.values())
    if not np.isclose(total, 1.0):
        raise ValueError(f"Scenario probabilities must sum to 1, got {total:.3f}")
    return sum(r.implied_price * r.assumptions.probability for r in results.values())


def _bisect(fn, low: float, high: float, *, label: str) -> float:
    f_low, f_high = fn(low), fn(high)
    if f_low * f_high > 0:
        raise ValueError(f"No {label} in [{low:.0%}, {high:.0%}] reconciles to market EV")
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = fn(mid)
        if f_low * f_mid <= 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def implied_revenue_growth(
    market_ev: float, base_revenue: float, a: OperatingAssumptions, *, low: float = -0.40, high: float = 1.00,
) -> float:
    """Constant revenue CAGR that reconciles the operating bridge to market EV."""
    n = len(a.revenue_growth)

    def gap(g: float) -> float:
        trial = replace(a, revenue_growth=(g,) * n)
        fcff = tuple(build_bridge(base_revenue, trial)["fcff"])
        return dcf_valuation(DCFInputs(fcff, a.wacc, a.terminal_growth))["enterprise_value"] - market_ev

    return _bisect(gap, low, high, label="revenue CAGR")


def implied_ebit_margin(
    market_ev: float, base_revenue: float, a: OperatingAssumptions, *, low: float = -0.50, high: float = 0.95,
) -> float:
    """Constant EBIT margin that reconciles the operating bridge to market EV."""
    n = len(a.ebit_margin)

    def gap(m: float) -> float:
        trial = replace(a, ebit_margin=(m,) * n)
        fcff = tuple(build_bridge(base_revenue, trial)["fcff"])
        return dcf_valuation(DCFInputs(fcff, a.wacc, a.terminal_growth))["enterprise_value"] - market_ev

    return _bisect(gap, low, high, label="EBIT margin")


def market_expectations(market_ev: float, base_revenue: float, base_fcff: float | None, a: OperatingAssumptions) -> dict[str, Any]:
    """What the current EV discounts, in cash-flow and operating terms.

    Each solve can legitimately fail; failures are returned as explanations so that
    the caller shows why, instead of a number from an invalid setup.
    """
    out: dict[str, Any] = {"implied_fcff_cagr": None, "implied_revenue_cagr": None, "implied_ebit_margin": None, "notes": []}
    if base_fcff is None or base_fcff <= 0:
        out["notes"].append("FCFF-growth reverse DCF not meaningful: base-year FCFF is not positive. Use the operating solves.")
    else:
        try:
            out["implied_fcff_cagr"] = reverse_dcf_implied_growth(
                market_enterprise_value=market_ev, starting_fcff=base_fcff, years=len(a.revenue_growth),
                wacc=a.wacc, terminal_growth=a.terminal_growth,
            )
        except ValueError as exc:
            out["notes"].append(f"FCFF-growth reverse DCF: {exc}")
    for key, solver in (("implied_revenue_cagr", implied_revenue_growth), ("implied_ebit_margin", implied_ebit_margin)):
        try:
            out[key] = solver(market_ev, base_revenue, a)
        except ValueError as exc:
            out["notes"].append(str(exc))
    return out


def sensitivity(result: ScenarioResult, *, step_wacc: float = 0.01, step_g: float = 0.005) -> pd.DataFrame:
    a = result.assumptions
    return dcf_sensitivity_table(
        fcff=tuple(result.bridge["fcff"]), net_debt=result.net_claims, shares_outstanding=result.shares,
        wacc_values=[round(a.wacc + i * step_wacc, 4) for i in (-2, -1, 0, 1, 2)],
        terminal_growth_values=[round(a.terminal_growth + i * step_g, 4) for i in (-2, -1, 0, 1, 2)],
    )


COMPS_COLUMNS = ("ticker", "enterprise_value", "market_cap", "revenue", "ebitda", "fcf", "net_income", "source")


def comps_table(peers: pd.DataFrame) -> pd.DataFrame:
    """Multiples for a peer table. Rows without a source URL are marked unsourced."""
    missing = [c for c in COMPS_COLUMNS if c not in peers.columns]
    if missing:
        raise ValueError(f"Comps table missing columns: {missing}")
    df = peers.copy()

    def multiple(num: str, den: str) -> pd.Series:
        return (df[num] / df[den].where(df[den] > 0)).astype(float)

    df["ev_revenue"] = multiple("enterprise_value", "revenue")
    df["ev_ebitda"] = multiple("enterprise_value", "ebitda")
    df["pe"] = multiple("market_cap", "net_income")
    df["fcf_yield"] = (df["fcf"] / df["market_cap"]).astype(float)
    df["sourced"] = df["source"].astype(str).str.startswith(("http://", "https://"))
    return df


def comps_implied_values(comps: pd.DataFrame, target: dict[str, float | None], net_claims: float, shares: float) -> pd.DataFrame:
    """Implied price at peer-median multiples, using sourced peers only."""
    usable = comps[comps["sourced"]]
    rows = []
    for multiple, metric, is_ev in (("ev_ebitda", "ebitda", True), ("ev_revenue", "revenue", True), ("pe", "net_income", False)):
        median = usable[multiple].median() if len(usable) else float("nan")
        base = target.get(metric)
        if base is None or base <= 0 or not np.isfinite(median):
            rows.append({"method": multiple, "peer_median": median, "target_metric": base, "implied_price": float("nan")})
            continue
        value = median * base
        rows.append({
            "method": multiple, "peer_median": median, "target_metric": base,
            "implied_price": (value - net_claims) / shares if is_ev else value / shares,
        })
    return pd.DataFrame(rows)
