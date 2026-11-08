"""Regenerate examples/sample_ic_memo.md from a fully synthetic company.

The inputs are invented, but the memo is real pipeline output: the synthetic filings
pass through the same normalizer, valuation, Thesis Lab and citation check as a live
ticker. No network access is used. Pass --save-bundle outputs to also add the synthetic
company to the dashboard's company list.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment_os.pipeline import build_bundle
from investment_os.research.ic_memo import LEDGER_HEADING, build_memo, validate_citations
from investment_os.research.thesis_lab import run_thesis_lab
from investment_os.research.workflow import run_valuation

OUTPUT = ROOT / "examples" / "sample_ic_memo.md"
YEARS = (2021, 2022, 2023, 2024, 2025)
QUARTER_SHARE = (0.23, 0.24, 0.25)
TARGET = "DEMO"
HYPOTHESIS = (
    "The market underestimates revenue growth and the conversion of earnings into free cash flow "
    "as new capacity comes online."
)
# ticker: (revenue scale, margin shift, share count, last price). Every value is invented.
COMPANIES: dict[str, tuple[float, float, float, float]] = {
    "DEMO": (1.00, 0.00, 250e6, 104.0),
    "PEERA": (0.80, -0.01, 180e6, 92.0),
    "PEERB": (1.30, 0.01, 400e6, 88.0),
    "PEERC": (0.60, -0.02, 120e6, 78.0),
}
REVENUE = (6.0e9, 6.9e9, 8.1e9, 9.2e9, 10.4e9)
EBIT_MARGIN = (0.18, 0.19, 0.20, 0.19, 0.18)
CAPEX_PCT = (0.06, 0.07, 0.08, 0.09, 0.09)
DEBT = (3.0e9, 3.2e9, 3.6e9, 4.0e9, 4.2e9)
DNA_PCT, TAX_RATE, CFO_EBITDA, CASH = 0.05, 0.21, 0.82, 1.2e9
CIKS = {ticker: i for i, ticker in enumerate(COMPANIES, 1)}


def _fact(value: float, end: str, start: str | None, form: str, filed: str, accession: str, fy: int, fp: str) -> dict[str, Any]:
    row = {"val": value, "end": end, "form": form, "filed": filed, "accn": accession, "fy": fy, "fp": fp}
    return {**row, "start": start} if start else row


def synthetic_filings(ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Company Facts and submissions payloads with the shape EDGAR returns."""
    scale, shift, shares, _ = COMPANIES[ticker]
    cik = CIKS[ticker]
    gaap: dict[str, list[dict[str, Any]]] = {}
    filings: list[tuple[str, str, str, str]] = []

    def add(tag: str, *args: Any) -> None:
        gaap.setdefault(tag, []).append(_fact(*args))

    for i, year in enumerate(YEARS):
        revenue = REVENUE[i] * scale
        ebit = revenue * (EBIT_MARGIN[i] + shift)
        dna, capex = revenue * DNA_PCT, revenue * CAPEX_PCT[i]
        pretax = ebit - DEBT[i] * scale * 0.06
        tax = pretax * TAX_RATE
        net, cfo = pretax - tax, (ebit + dna) * CFO_EBITDA
        accession = f"{cik:010d}-{(year + 1) % 100:02d}-000010"
        annual = (f"{year}-01-01", f"{year}-12-31")
        meta = ("10-K", f"{year + 1}-02-15", accession, year, "FY")
        filings.append((accession, "10-K", f"{year + 1}-02-15", f"{year}-12-31"))
        for tag, value in (
            ("Revenues", revenue), ("OperatingIncomeLoss", ebit), ("NetIncomeLoss", net), ("IncomeTaxExpenseBenefit", tax),
            ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", pretax),
            ("DepreciationDepletionAndAmortization", dna), ("NetCashProvidedByUsedInOperatingActivities", cfo),
            ("PaymentsToAcquirePropertyPlantAndEquipment", capex),
        ):
            add(tag, value, annual[1], annual[0], *meta)
        _balance(add, i, scale, annual[1], meta)

        cumulative = 0.0
        for q, (first, end) in enumerate((("01-01", "03-31"), ("04-01", "06-30"), ("07-01", "09-30")), 1):
            cumulative += QUARTER_SHARE[q - 1]
            accession_q = f"{cik:010d}-{year % 100:02d}-00000{q}"
            filed = f"{year}-{3 * q + 2:02d}-05"
            meta_q = ("10-Q", filed, accession_q, year, f"Q{q}")
            filings.append((accession_q, "10-Q", filed, f"{year}-{end}"))
            for tag, value in (("Revenues", revenue), ("OperatingIncomeLoss", ebit), ("NetIncomeLoss", net)):
                add(tag, value * QUARTER_SHARE[q - 1], f"{year}-{end}", f"{year}-{first}", *meta_q)
            for tag, value in (
                ("DepreciationDepletionAndAmortization", dna), ("NetCashProvidedByUsedInOperatingActivities", cfo),
                ("PaymentsToAcquirePropertyPlantAndEquipment", capex),
            ):
                add(tag, value * cumulative, f"{year}-{end}", f"{year}-01-01", *meta_q)
            _balance(add, i, scale, f"{year}-{end}", meta_q)

    latest = filings[-4]
    dei = [_fact(shares, "2026-01-31", None, "10-K", latest[2], latest[0], YEARS[-1], "FY")]
    facts = {
        "entityName": f"Synthetic {ticker.title()} Co" if ticker != TARGET else "Synthetic Demo Co",
        "facts": {
            "us-gaap": {tag: {"units": {"USD": rows}} for tag, rows in gaap.items()},
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": dei}}},
        },
    }
    filings.sort(key=lambda row: row[2], reverse=True)
    submissions = {
        "cik": str(cik), "name": facts["entityName"], "sic": "3590", "sicDescription": "Synthetic issuer",
        "filings": {"recent": {
            "accessionNumber": [f[0] for f in filings], "form": [f[1] for f in filings], "filingDate": [f[2] for f in filings],
            "reportDate": [f[3] for f in filings], "primaryDocument": ["synthetic.htm" for _ in filings],
        }},
    }
    return facts, submissions


def _balance(add: Any, i: int, scale: float, end: str, meta: tuple[Any, ...]) -> None:
    debt = DEBT[i] * scale
    for tag, value in (
        ("CashAndCashEquivalentsAtCarryingValue", CASH * scale), ("Assets", REVENUE[i] * scale * 1.5), ("Liabilities", (REVENUE[i] * 0.4 + DEBT[i]) * scale),
        ("LongTermDebtNoncurrent", debt * 0.95), ("LongTermDebtCurrent", debt * 0.05),
    ):
        add(tag, value, end, None, *meta)


class SyntheticSEC:
    """Stands in for SECClient, so that no network call is made."""

    def cik_for_ticker(self, ticker: str) -> int:
        return CIKS[ticker]

    def companyfacts(self, ticker: str) -> dict[str, Any]:
        return synthetic_filings(ticker)[0]

    def submissions(self, cik: int) -> dict[str, Any]:
        ticker = next(t for t, c in CIKS.items() if c == cik)
        return synthetic_filings(ticker)[1]


def synthetic_prices(ticker: str) -> pd.DataFrame:
    """Seeded random walk that ends exactly on the invented last price."""
    dates = pd.date_range("2024-03-01", "2026-02-27", freq="B")
    walk = np.cumprod(1 + np.random.default_rng(CIKS[ticker]).normal(0.0004, 0.014, len(dates)))
    close = walk / walk[-1] * COMPANIES[ticker][3]
    return pd.DataFrame({"date": dates, "close": close, "adj_close": close, "volume": 1_000_000.0})


BANNER = """> **Synthetic example. Every company, filing, price and peer below is invented.**
> Synthetic Demo Co does not exist and nothing here describes any real security. The analysis
> is pipeline output, run on simulated filings by `scripts/build_example_memo.py`. Only this
> notice, the `synthetic-source` link labels and the collapsed ledger were added afterward.
> Not investment advice.
"""


def publishable(memo: str) -> str:
    """Label synthetic sources and collapse the ledger, leaving the analysis untouched."""
    memo = re.sub(r"https://(?:www\.sec\.gov|finance\.yahoo\.com)[^\s;|)]+", "synthetic-source", memo)
    memo = memo.replace("Yahoo Finance via yfinance; an unlicensed convenience source, verify before use.", "Simulated price.")
    title, _, rest = memo.partition("\n\n")
    body, heading, ledger = f"{rest}".partition(LEDGER_HEADING)
    collapsed = f"{heading}\n\n<details>\n<summary>Open the full evidence ledger</summary>\n{ledger.rstrip()}\n\n</details>\n"
    return f"{title}\n\n{BANNER}\n{body}{collapsed}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save-bundle", type=Path, default=None, help="Also write the synthetic company as a dashboard bundle here")
    args = parser.parse_args()

    bundle = build_bundle(TARGET, client=SyntheticSEC(), price_fetcher=synthetic_prices, peers=("PEERA", "PEERB", "PEERC"), output_dir=args.save_bundle)
    valuation = run_valuation(bundle)
    report = run_thesis_lab(HYPOTHESIS, bundle, valuation)
    memo = build_memo(bundle, valuation, report)
    check = validate_citations(memo, valuation.ledger)
    if not check.ok:
        raise SystemExit(f"Memo failed citation validation: {check.uncited[:3]} {check.unknown_ids[:5]}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(publishable(memo), encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {check.citations_checked} citations validated; thesis {report.status_counts()}")
    if bundle.warnings:
        print("Warnings:", *bundle.warnings, sep="\n  ")


if __name__ == "__main__":
    main()
