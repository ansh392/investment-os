from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment_os.data.sec import SECClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull latest standardized SEC Company Facts for a ticker.")
    parser.add_argument("ticker", help="US public-company ticker, e.g. VST or NVDA")
    args = parser.parse_args()

    client = SECClient()
    facts = client.companyfacts(args.ticker)
    normalized = client.latest_standardized(facts)
    print(f"{facts.get('entityName', args.ticker.upper())} ({args.ticker.upper()})")
    for field, fact in normalized.items():
        print(
            f"{field:20} {fact.value:,.2f} {fact.unit:8} "
            f"| {fact.form} filed {fact.filed} | concept={fact.concept}"
        )


if __name__ == "__main__":
    main()
