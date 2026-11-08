"""DCF, reverse DCF and sensitivity primitives."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DCFInputs:
    fcff: tuple[float, ...]
    wacc: float
    terminal_growth: float
    net_debt: float = 0.0
    shares_outstanding: float = 1.0


def dcf_valuation(inputs: DCFInputs) -> dict[str, float]:
    if not inputs.fcff:
        raise ValueError("At least one FCFF year is required")
    if not (0 < inputs.wacc < 1):
        raise ValueError("WACC must be a decimal between 0 and 1")
    if inputs.wacc <= inputs.terminal_growth:
        raise ValueError("WACC must exceed terminal growth")
    if inputs.shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be positive")
    pv_explicit = sum(cf / ((1 + inputs.wacc) ** i) for i, cf in enumerate(inputs.fcff, 1))
    terminal_cf = inputs.fcff[-1] * (1 + inputs.terminal_growth)
    terminal_value = terminal_cf / (inputs.wacc - inputs.terminal_growth)
    pv_terminal = terminal_value / ((1 + inputs.wacc) ** len(inputs.fcff))
    ev = pv_explicit + pv_terminal
    equity = ev - inputs.net_debt
    price = equity / inputs.shares_outstanding
    result = {
        "pv_explicit": pv_explicit,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": ev,
        "equity_value": equity,
        "implied_price": price,
    }
    if not all(isfinite(v) for v in result.values()):
        raise ValueError("DCF produced non-finite values")
    return result


def fcff_forecast(starting_fcff: float, annual_growth: float, years: int) -> tuple[float, ...]:
    if years < 1:
        raise ValueError("years must be >= 1")
    return tuple(starting_fcff * ((1 + annual_growth) ** year) for year in range(1, years + 1))


def reverse_dcf_implied_growth(
    *,
    market_enterprise_value: float,
    starting_fcff: float,
    years: int,
    wacc: float,
    terminal_growth: float,
    low: float = -0.50,
    high: float = 1.50,
) -> float:
    """Solve the constant forecast-period FCFF CAGR implied by market EV."""
    if market_enterprise_value <= 0 or starting_fcff <= 0:
        raise ValueError("market EV and starting FCFF must be positive")

    def model_ev(g: float) -> float:
        fcff = fcff_forecast(starting_fcff, g, years)
        return dcf_valuation(DCFInputs(fcff, wacc, terminal_growth))["enterprise_value"]

    f_low = model_ev(low) - market_enterprise_value
    f_high = model_ev(high) - market_enterprise_value
    if f_low * f_high > 0:
        raise ValueError("Implied growth is outside the supplied search interval")
    for _ in range(160):
        mid = (low + high) / 2
        f_mid = model_ev(mid) - market_enterprise_value
        if abs(f_mid) < max(1e-10, market_enterprise_value * 1e-12):
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2


def dcf_sensitivity_table(
    *,
    fcff: tuple[float, ...],
    net_debt: float,
    shares_outstanding: float,
    wacc_values: list[float],
    terminal_growth_values: list[float],
) -> pd.DataFrame:
    rows = []
    for wacc in wacc_values:
        row = {"wacc": wacc}
        for tg in terminal_growth_values:
            key = f"g={tg:.1%}"
            try:
                row[key] = dcf_valuation(DCFInputs(fcff, wacc, tg, net_debt, shares_outstanding))["implied_price"]
            except ValueError:
                row[key] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def valuation_multiples(*, market_cap: float, debt: float, cash: float, ebitda: float, fcf: float) -> dict[str, float]:
    ev = market_cap + debt - cash
    return {
        "enterprise_value": ev,
        "ev_ebitda": ev / ebitda if ebitda else float("nan"),
        "fcf_yield": fcf / market_cap if market_cap else float("nan"),
        "net_debt_ebitda": (debt - cash) / ebitda if ebitda else float("nan"),
    }
