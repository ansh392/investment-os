"""LBO returns, DSCR and the reverse-underwriting solvers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LBOInputs:
    purchase_price: float
    debt: float
    cash: float
    annual_cfads: tuple[float, ...]
    interest_rate: float
    mandatory_amortization_pct: float
    exit_enterprise_value: float


def _irr(cashflows: list[float], low: float = -0.99, high: float = 10.0, tol: float = 1e-8) -> float:
    if not any(cf > 0 for cf in cashflows):
        return -1.0  # total loss: no rate can equate an all-outflow series

    def npv(rate: float) -> float:
        return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cashflows))

    f_low, f_high = npv(low), npv(high)
    if f_low * f_high > 0:
        return float("nan")
    for _ in range(300):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def run_lbo(inputs: LBOInputs) -> dict[str, object]:
    if inputs.purchase_price <= 0 or inputs.debt < 0:
        raise ValueError("Invalid purchase price or debt")
    if not (0 <= inputs.interest_rate < 1):
        raise ValueError("Invalid interest rate")
    equity = inputs.purchase_price - inputs.debt - inputs.cash
    if equity <= 0:
        raise ValueError("Initial sponsor equity must be positive")
    debt_balance = inputs.debt
    sponsor_cashflows: list[float] = [-equity]
    yearly: list[dict[str, float]] = []
    for year, cfads in enumerate(inputs.annual_cfads, 1):
        interest = debt_balance * inputs.interest_rate
        scheduled = min(debt_balance, inputs.debt * inputs.mandatory_amortization_pct)
        debt_service = interest + scheduled
        dscr = cfads / debt_service if debt_service > 0 else float("inf")
        distribution = max(0.0, cfads - debt_service)
        # Unfunded debt service is not forgiven: it capitalizes onto the balance.
        shortfall = max(0.0, debt_service - cfads)
        debt_balance = max(0.0, debt_balance - scheduled) + shortfall
        sponsor_cashflows.append(distribution)
        yearly.append({
            "year": year,
            "cfads": cfads,
            "interest": interest,
            "principal": scheduled,
            "debt_service": debt_service,
            "dscr": dscr,
            "ending_debt": debt_balance,
            "sponsor_distribution": distribution,
            "debt_service_shortfall": shortfall,
        })
    # Limited liability: equity cannot be worth less than zero at exit.
    exit_equity = max(0.0, inputs.exit_enterprise_value - debt_balance)
    sponsor_cashflows[-1] += exit_equity
    moic = sum(max(0.0, x) for x in sponsor_cashflows[1:]) / equity
    irr = _irr(sponsor_cashflows)
    min_dscr = min((row["dscr"] for row in yearly), default=float("inf"))
    return {
        "initial_equity": equity,
        "ending_debt": debt_balance,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
        "min_dscr": min_dscr,
        "total_shortfall": sum(row["debt_service_shortfall"] for row in yearly),
        "cashflows": sponsor_cashflows,
        "yearly": yearly,
    }


def solve_max_purchase_price(
    *,
    debt: float,
    cash: float,
    annual_cfads: tuple[float, ...],
    interest_rate: float,
    mandatory_amortization_pct: float,
    exit_enterprise_value: float,
    target_irr: float,
    low: float,
    high: float,
) -> float:
    """Highest price clearing ``target_irr``; raises if no price in range does.

    IRR falls as price rises, and prices at or below debt + cash are unfinanceable
    (no sponsor equity), so the search floor is lifted above that point.
    """
    low = max(low, (debt + cash) * (1 + 1e-9) + 1e-6)
    best: float | None = None
    for _ in range(120):
        mid = (low + high) / 2
        irr = run_lbo(LBOInputs(mid, debt, cash, annual_cfads, interest_rate, mandatory_amortization_pct, exit_enterprise_value))["irr"]
        if irr != irr or irr < target_irr:
            high = mid
        else:
            best = mid
            low = mid
    if best is None:
        raise ValueError(f"No purchase price in the search range reaches a {target_irr:.1%} IRR")
    return best


def solve_max_debt_for_dscr(
    *,
    purchase_price: float,
    cash: float,
    annual_cfads: tuple[float, ...],
    interest_rate: float,
    mandatory_amortization_pct: float,
    exit_enterprise_value: float,
    minimum_dscr: float,
    low: float = 0.0,
    high: float | None = None,
) -> float:
    high = high if high is not None else purchase_price * 0.95
    best = low
    for _ in range(120):
        mid = (low + high) / 2
        try:
            result = run_lbo(LBOInputs(purchase_price, mid, cash, annual_cfads, interest_rate, mandatory_amortization_pct, exit_enterprise_value))
        except ValueError:
            high = mid
            continue
        if result["min_dscr"] >= minimum_dscr:
            best = mid
            low = mid
        else:
            high = mid
    return best
