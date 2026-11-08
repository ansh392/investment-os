"""End-to-end company research: python scripts/research_company.py VST --peers CEG,NRG,TLN"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment_os.models.workspace import ValuationNotApplicable
from investment_os.pipeline import DEFAULT_OUTPUT_DIR, build_bundle, load_bundle
from investment_os.research.ic_memo import export_memo, recommendation_for
from investment_os.research.thesis_lab import run_thesis_lab
from investment_os.research.workflow import run_valuation

DEFAULT_THESIS = "The market underestimates this company's ability to grow revenue and convert earnings into free cash flow."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="US-listed ticker, e.g. VST or NVDA")
    parser.add_argument("--peers", default="", help="Comma-separated peer tickers for real comps")
    parser.add_argument("--thesis", default=DEFAULT_THESIS, help="Hypothesis to test")
    parser.add_argument("--wacc", type=float, default=0.09)
    parser.add_argument("--terminal-growth", type=float, default=0.025)
    parser.add_argument("--offline", action="store_true", help="Reuse the saved bundle in outputs/<TICKER> without network access")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    peers = tuple(p.strip().upper() for p in args.peers.split(",") if p.strip())
    bundle = load_bundle(ticker) if args.offline else build_bundle(ticker, peers=peers)

    try:
        valuation = run_valuation(bundle, wacc=args.wacc, terminal_growth=args.terminal_growth)
    except ValuationNotApplicable as exc:
        print(f"Valuation not applicable: {exc}")
        valuation = None
    report = run_thesis_lab(args.thesis, bundle, valuation)
    md_path, html_path, check = export_memo(bundle, valuation, report, DEFAULT_OUTPUT_DIR / ticker)

    m = bundle.market
    print(f"\n{bundle.name} ({ticker})  CIK {bundle.cik}  SIC {bundle.sic} {bundle.sic_description}")
    print(f"Annual periods: {len(bundle.annual)}  Quarterly periods: {len(bundle.quarterly)}  Evidence items: {len(valuation.ledger if valuation else bundle.ledger)}")
    if m.get("price"):
        print(f"Price ${m['price']:,.2f} ({m['price_date']})")
    if m.get("enterprise_value"):
        print(f"Market cap ${m['market_cap'] / 1e9:,.1f}B  EV ${m['enterprise_value'] / 1e9:,.1f}B")
    if valuation:
        for name, r in valuation.results.items():
            print(f"  {name:5} ${r.implied_price:,.2f}")
        print(f"  weighted ${valuation.weighted_price:,.2f}")
        x = valuation.expectations
        if x["implied_revenue_cagr"] is not None:
            print(f"Market-implied revenue CAGR {x['implied_revenue_cagr']:.1%}")
    print(f"Thesis: {report.status_counts()}")
    print(f"Rating: {recommendation_for(valuation, report)[0]}")
    print(f"Citations validated: {check.citations_checked}")
    if bundle.warnings:
        print("\nData warnings:")
        for warning in bundle.warnings:
            print(f"  ! {warning}")
    print(f"\nBundle: {DEFAULT_OUTPUT_DIR / ticker}\nMemo:   {md_path}\n        {html_path}")


if __name__ == "__main__":
    main()
