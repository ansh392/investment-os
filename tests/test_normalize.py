import pandas as pd
import pytest

from conftest import calendar_company, company, fact
from investment_os.data.normalize import (
    fiscal_year_label,
    latest_shares_outstanding,
    normalize_company_facts,
    reconstruct_debt,
    trailing_twelve_months,
)
from investment_os.data.sec import SECClient, filing_url, filings_frame
from datetime import date


def value(n, field, fy, fp):
    frame = n.annual if fp == "FY" else n.quarterly
    row = frame[(frame.fiscal_year == fy) & (frame.fiscal_period == fp)]
    return float(row[field].iloc[0])


def test_comparative_fact_uses_dates_not_filing_fy():
    # A FY2025 10-K tags its FY2023 comparative as fy=2025; the period end must win.
    n = normalize_company_facts(company({"Revenues": [
        fact(100, "2023-12-31", "2023-01-01", fy=2025, filed="2026-02-01"),
        fact(120, "2025-12-31", "2025-01-01", fy=2025, filed="2026-02-01"),
    ]}))
    assert value(n, "revenue", 2023, "FY") == 100
    assert value(n, "revenue", 2025, "FY") == 120


def test_duplicate_contexts_latest_filing_wins_and_flags_restatement():
    rows = [
        fact(100, "2023-12-31", "2023-01-01", filed="2024-02-01", accn="A-1"),
        fact(90, "2023-12-31", "2023-01-01", filed="2025-02-01", accn="A-2"),
    ]
    n = normalize_company_facts(company({"Revenues": rows}))
    assert value(n, "revenue", 2023, "FY") == 90
    assert bool(n.lineage[n.lineage.field == "revenue"].restated.iloc[0])


def test_original_vintage_returns_first_reported():
    rows = [
        fact(100, "2023-12-31", "2023-01-01", filed="2024-02-01"),
        fact(90, "2023-12-31", "2023-01-01", filed="2025-02-01"),
    ]
    assert value(normalize_company_facts(company({"Revenues": rows}), vintage="original"), "revenue", 2023, "FY") == 100


def test_tag_change_is_merged_per_period():
    n = normalize_company_facts(company({
        "PaymentsToAcquirePropertyPlantAndEquipment": [fact(10, "2019-12-31", "2019-01-01")],
        "PaymentsToAcquireProductiveAssets": [fact(20, "2020-12-31", "2020-01-01")],
        "Revenues": [fact(1, "2019-12-31", "2019-01-01"), fact(1, "2020-12-31", "2020-01-01")],
    }))
    assert value(n, "capex", 2019, "FY") == 10
    assert value(n, "capex", 2020, "FY") == 20
    assert any("multiple XBRL tags" in note for note in n.notes)


def test_priority_tag_wins_when_both_report_same_period():
    n = normalize_company_facts(company({
        "Revenues": [fact(100, "2023-12-31", "2023-01-01")],
        "RevenueFromContractWithCustomerExcludingAssessedTax": [fact(80, "2023-12-31", "2023-01-01")],
    }))
    assert value(n, "revenue", 2023, "FY") == 100
    assert any("disagree" in note for note in n.notes)


def test_ytd_cash_flows_are_differenced_and_q4_derived():
    n = normalize_company_facts(calendar_company())
    assert value(n, "cfo", 2022, "Q1") == pytest.approx(25)
    assert value(n, "cfo", 2022, "Q2") == pytest.approx(25)
    assert value(n, "cfo", 2022, "Q3") == pytest.approx(25)
    assert value(n, "cfo", 2022, "Q4") == pytest.approx(100 - 75)
    derivations = set(n.lineage[(n.lineage.field == "cfo") & (n.lineage.period_type == "quarterly")].derivation)
    assert {"reported", "ytd_difference", "q4_fy_minus_ytd"} <= derivations


def test_quarters_sum_to_annual():
    n = normalize_company_facts(calendar_company())
    for field in ("revenue", "cfo", "capex"):
        total = n.quarterly[n.quarterly.fiscal_year == 2023][field].sum()
        assert total == pytest.approx(value(n, field, 2023, "FY"))


def test_ytd_contexts_never_leak_into_annual():
    n = normalize_company_facts(calendar_company())
    assert len(n.annual) == 3


def test_fcf_requires_both_inputs():
    n = normalize_company_facts(company({
        "NetCashProvidedByUsedInOperatingActivities": [fact(50, "2023-12-31", "2023-01-01")],
        "Revenues": [fact(1, "2023-12-31", "2023-01-01")],
    }))
    assert pd.isna(n.annual.fcf.iloc[0])
    assert any("capex" in w for w in n.warnings)


def test_debt_noncurrent_plus_current_plus_short_term_high_confidence():
    debt, _, confidence = reconstruct_debt({
        "LongTermDebtNoncurrent": 90.0, "LongTermDebtCurrent": 10.0, "LongTermDebt": 100.0, "ShortTermBorrowings": 5.0,
    })
    assert debt == 105.0 and confidence == "high"


def test_debt_requires_current_portion():
    assert reconstruct_debt({"LongTermDebtNoncurrent": 90.0}) is None


def test_commercial_paper_is_not_double_counted_with_short_term():
    debt, _, _ = reconstruct_debt({"LongTermDebt": 100.0, "ShortTermBorrowings": 10.0, "CommercialPaper": 10.0})
    assert debt == 110.0


def test_unreconstructable_debt_stays_missing_with_warning():
    n = normalize_company_facts(company({
        "Revenues": [fact(1, "2023-12-31", "2023-01-01")],
        "LongTermDebtNoncurrent": [fact(90, "2023-12-31")],
    }))
    assert pd.isna(n.annual.debt.iloc[0])
    assert any("left missing" in w for w in n.warnings)


def test_ttm_requires_contiguous_quarters():
    q = pd.DataFrame({"period_end": ["2024-03-31", "2024-06-30", "2024-12-31", "2025-03-31"], "x": [1.0, 1.0, 1.0, 1.0]})
    assert trailing_twelve_months(q, "x") is None
    q["period_end"] = ["2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31"]
    assert trailing_twelve_months(q, "x") == (4.0, "2025-03-31")


def test_fiscal_year_label_handles_53_week_year():
    assert fiscal_year_label(date(2026, 1, 3)) == 2025
    assert fiscal_year_label(date(2026, 1, 25)) == 2026


def test_shares_fall_back_to_balance_sheet_for_multi_class():
    raw = company({})
    raw["facts"]["us-gaap"]["CommonStockSharesOutstanding"] = {"units": {"shares": [fact(7.0, "2024-12-31")]}}
    assert latest_shares_outstanding(raw)["shares"] == 7.0


def test_latest_standardized_prefers_current_tag_over_discontinued():
    raw = company({
        "PaymentsToAcquirePropertyPlantAndEquipment": [fact(10, "2019-12-31", "2019-01-01")],
        "PaymentsToAcquireProductiveAssets": [fact(20, "2024-12-31", "2024-01-01")],
    })
    assert SECClient.latest_standardized(raw)["capex"].value == 20


def test_latest_standardized_ignores_partial_year_flows():
    raw = company({"Revenues": [
        fact(400, "2024-12-31", "2024-01-01"),
        fact(120, "2025-03-31", "2025-01-01", form="10-Q", filed="2025-05-01"),
    ]})
    assert SECClient.latest_standardized(raw)["revenue"].value == 400


def test_filing_links_point_at_primary_document():
    frame = filings_frame({"cik": "0000001", "filings": {"recent": {
        "accessionNumber": ["0000000001-25-000010"], "form": ["10-K"], "filingDate": ["2025-02-15"],
        "reportDate": ["2024-12-31"], "primaryDocument": ["doc.htm"],
    }}})
    assert frame.url.iloc[0] == "https://www.sec.gov/Archives/edgar/data/1/000000000125000010/doc.htm"
    assert filing_url(1, "0000000001-25-000010").endswith("/000000000125000010/")
