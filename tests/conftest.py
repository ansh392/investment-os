"""Hand-built SEC fixtures. All values are invented test inputs, not company data."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investment_os.pipeline import build_bundle


def fact(val, end, start=None, form="10-K", filed="2025-02-15", accn="0000000001-25-000001", fy=2024, fp="FY"):
    row = {"val": val, "end": end, "form": form, "filed": filed, "accn": accn, "fy": fy, "fp": fp}
    if start:
        row["start"] = start
    return row


def company(us_gaap=None, dei=None):
    wrap = lambda rows, unit="USD": {"units": {unit: rows}}
    return {
        "entityName": "Fixture Co",
        "facts": {
            "us-gaap": {k: wrap(v) for k, v in (us_gaap or {}).items()},
            "dei": {k: wrap(v, "shares") for k, v in (dei or {}).items()},
        },
    }


Q10 = dict(form="10-Q")


def calendar_company(revenue_scale: float = 1.0) -> dict:
    """Two complete fiscal years plus a partial year with YTD-style cash flows."""
    def yr(y):
        return dict(start=f"{y}-01-01", end=f"{y}-12-31")

    revenue, cfo, capex, opinc, dna, ni, cash, assets, liabs, ltd_nc, ltd_c = [], [], [], [], [], [], [], [], [], [], []
    for i, y in enumerate((2022, 2023, 2024)):
        base = (100 + 20 * i) * revenue_scale
        accn = f"0000000001-{y + 1 - 2000}-000010"
        filed = f"{y + 1}-02-15"
        k = dict(form="10-K", filed=filed, accn=accn, fy=y, fp="FY")
        revenue.append(fact(base * 4, f"{y}-12-31", f"{y}-01-01", **k))
        opinc.append(fact(base * 4 * 0.2, f"{y}-12-31", f"{y}-01-01", **k))
        ni.append(fact(base * 4 * 0.15, f"{y}-12-31", f"{y}-01-01", **k))
        dna.append(fact(base * 0.4, f"{y}-12-31", f"{y}-01-01", **k))
        cfo.append(fact(base, f"{y}-12-31", f"{y}-01-01", **k))
        capex.append(fact(base * 0.4, f"{y}-12-31", f"{y}-01-01", **k))
        for tag, v in ((cash, 50.0), (assets, 1000.0), (liabs, 500.0), (ltd_nc, 200.0), (ltd_c, 20.0)):
            tag.append(fact(v, f"{y}-12-31", **k))
        for q, (s, e, n) in enumerate((("01-01", "03-31", 1), ("01-01", "06-30", 2), ("01-01", "09-30", 3)), 1):
            qk = dict(form="10-Q", filed=f"{y}-{3 * q + 1:02d}-20" if q < 3 else f"{y}-11-05", accn=f"0000000001-{y - 2000}-00000{q}", fy=y, fp=f"Q{q}")
            cfo.append(fact(base * 0.25 * n, f"{y}-{e}", f"{y}-{s}", **qk))
            capex.append(fact(base * 0.1 * n, f"{y}-{e}", f"{y}-{s}", **qk))
            dna.append(fact(base * 0.1 * n, f"{y}-{e}", f"{y}-{s}", **qk))
            q_start = {1: "01-01", 2: "04-01", 3: "07-01"}[q]
            for tag, m in ((revenue, 1.0), (opinc, 0.2), (ni, 0.15)):
                tag.append(fact(base * m, f"{y}-{e}", f"{y}-{q_start}", **qk))
            for tag, v in ((cash, 45.0), (assets, 990.0), (liabs, 495.0), (ltd_nc, 200.0), (ltd_c, 20.0)):
                tag.append(fact(v, f"{y}-{e}", **qk))
    return company(
        {
            "Revenues": revenue, "OperatingIncomeLoss": opinc, "NetIncomeLoss": ni, "DepreciationDepletionAndAmortization": dna,
            "NetCashProvidedByUsedInOperatingActivities": cfo, "PaymentsToAcquirePropertyPlantAndEquipment": capex,
            "CashAndCashEquivalentsAtCarryingValue": cash, "Assets": assets, "Liabilities": liabs,
            "LongTermDebtNoncurrent": ltd_nc, "LongTermDebtCurrent": ltd_c,
        },
        {"EntityCommonStockSharesOutstanding": [fact(10.0, "2025-01-31", form="10-K", filed="2025-02-15", accn="0000000001-25-000010")]},
    )


def submissions(sic="3674"):
    return {
        "cik": "1", "name": "Fixture Co", "sic": sic, "sicDescription": "Fixture",
        "filings": {"recent": {
            "accessionNumber": ["0000000001-25-000010"], "form": ["10-K"], "filingDate": ["2025-02-15"],
            "reportDate": ["2024-12-31"], "primaryDocument": ["fixture-20241231.htm"],
        }},
    }


class FakeSEC:
    def __init__(self, facts, subs):
        self.facts, self.subs = facts, subs

    def cik_for_ticker(self, ticker):
        return 1

    def companyfacts(self, ticker):
        return self.facts

    def submissions(self, cik):
        return self.subs


def fake_prices(_ticker: str, price: float = 150.0) -> pd.DataFrame:
    dates = pd.date_range("2025-01-02", periods=30, freq="B")
    return pd.DataFrame({"date": dates, "close": price, "adj_close": price, "volume": 1000.0})


@pytest.fixture
def bundle(tmp_path):
    return build_bundle("FIX", client=FakeSEC(calendar_company(), submissions()), price_fetcher=fake_prices, output_dir=tmp_path)


def synthetic_weekly(n=420, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2016-01-01", periods=n, freq="W-FRI")
    s = rng.normal(size=n)
    r = np.r_[0.0, 0.012 * s[:-1] + rng.normal(scale=0.02, size=n - 1)]
    return pd.Series(s, index=dates), pd.Series(100 * np.cumprod(1 + r), index=dates), r
