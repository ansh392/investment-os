"""Run the core mechanics on illustrative inputs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from investment_os.core.evidence import EvidenceItem, EvidenceKind, EvidenceLedger
from investment_os.models.valuation import (
    DCFInputs,
    dcf_valuation,
    reverse_dcf_implied_growth,
)
from investment_os.private.lbo import (
    LBOInputs,
    run_lbo,
    solve_max_debt_for_dscr,
    solve_max_purchase_price,
)
from investment_os.research.memo import ICMemoBuilder, MemoInputs
from investment_os.research.thesis import build_manual_thesis_plan
from investment_os.signals.analytics import (
    lead_lag_table,
    out_of_sample_signal_backtest,
)


def main() -> None:
    print("=== INVESTMENT OS MECHANICS DEMO (illustrative data) ===")

    fcff = (2.5e9, 2.8e9, 3.05e9, 3.25e9, 3.45e9)
    dcf = dcf_valuation(DCFInputs(fcff, 0.09, 0.025, 8e9, 300e6))
    implied_growth = reverse_dcf_implied_growth(
        market_enterprise_value=45e9,
        starting_fcff=2.4e9,
        years=5,
        wacc=0.09,
        terminal_growth=0.025,
    )
    print(f"DCF implied price: ${dcf['implied_price']:.2f}")
    print(f"Reverse-DCF implied 5y FCFF CAGR: {implied_growth:.1%}")

    rng = np.random.default_rng(7)
    n = 180
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    signal = pd.Series(rng.normal(size=n), index=dates)
    noise = pd.Series(rng.normal(scale=0.02, size=n), index=dates)
    forward_return = 0.004 * signal + noise
    oos = out_of_sample_signal_backtest(signal, forward_return, transaction_cost_bps=5)
    best_lag = lead_lag_table(signal, forward_return, max_lag=5).sort_values("abs_correlation", ascending=False).iloc[0]
    print(f"OOS test correlation: {oos.test_correlation:.3f}; strategy return: {oos.test_strategy_return:.1%}")
    print(f"Strongest lead/lag correlation at lag {int(best_lag['lag'])}: {best_lag['correlation']:.3f}")

    lbo_inputs = LBOInputs(
        purchase_price=1_000e6,
        debt=550e6,
        cash=0,
        annual_cfads=(150e6, 160e6, 170e6, 180e6, 190e6),
        interest_rate=0.085,
        mandatory_amortization_pct=0.05,
        exit_enterprise_value=1_250e6,
    )
    lbo = run_lbo(lbo_inputs)
    max_price = solve_max_purchase_price(
        debt=550e6,
        cash=0,
        annual_cfads=lbo_inputs.annual_cfads,
        interest_rate=0.085,
        mandatory_amortization_pct=0.05,
        exit_enterprise_value=1_250e6,
        target_irr=0.20,
        low=550e6 + 1,
        high=1_800e6,
    )
    max_debt = solve_max_debt_for_dscr(
        purchase_price=1_000e6,
        cash=0,
        annual_cfads=lbo_inputs.annual_cfads,
        interest_rate=0.085,
        mandatory_amortization_pct=0.05,
        exit_enterprise_value=1_250e6,
        minimum_dscr=1.40,
    )
    print(f"LBO IRR: {lbo['irr']:.1%}; MOIC: {lbo['moic']:.2f}x; min DSCR: {lbo['min_dscr']:.2f}x")
    print(f"Max purchase price @ 20% IRR: ${max_price/1e6:.1f}M")
    print(f"Max debt @ 1.40x minimum DSCR: ${max_debt/1e6:.1f}M")

    plan = build_manual_thesis_plan(
        "IllustrativeCo earnings can compound faster than market expectations.",
        claims=[
            "A leading operating KPI is accelerating.",
            "Incremental margins remain above historical average.",
            "Current valuation implies lower growth than the base case.",
        ],
        evidence_needed=[
            ["KPI history", "industry data"],
            ["segment margins", "cost structure"],
            ["reverse DCF", "consensus estimates"],
        ],
        falsification_tests=[
            ["KPI growth falls below 5% for two periods"],
            ["incremental margin falls below 15%"],
            ["market-implied growth exceeds base-case growth"],
        ],
        key_unknowns=["pricing durability", "competitive response"],
    )
    print(f"Thesis plan contains {len(plan.claims)} testable claims")

    ledger = EvidenceLedger([
        EvidenceItem("D1", "Illustrative DCF implied price", f"${dcf['implied_price']:.2f}", EvidenceKind.DERIVED, "Investment OS demo model"),
        EvidenceItem("A1", "Forecast-period FCFF values are illustrative", "demo assumptions", EvidenceKind.ASSUMED),
    ])
    memo = ICMemoBuilder().build(MemoInputs(
        company="IllustrativeCo",
        recommendation="WATCH — demo only",
        thesis="The company may be mispriced if operating KPIs compound faster than market-implied expectations.",
        variant_perception="The key question is whether the market is embedding materially lower growth than the evidence supports.",
        valuation_summary=f"Illustrative DCF produces ${dcf['implied_price']:.2f}/share [D1].",
        bull_case="KPI acceleration persists and incremental margins remain elevated.",
        bear_case="Growth normalizes while the market already embeds optimistic terminal economics.",
        catalysts=("KPI acceleration", "earnings revisions"),
        risks=("multiple compression", "competitive response"),
        falsification_tests=("Operating KPI fails to accelerate", "reverse DCF implies more growth than the base case"),
        next_diligence=("source consensus estimates", "validate KPI data provenance"),
    ), ledger)
    print("\n" + memo[:900] + "\n...")


if __name__ == "__main__":
    main()
