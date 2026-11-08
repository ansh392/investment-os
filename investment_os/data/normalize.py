"""Normalize SEC Company Facts into annual and quarterly financial histories.

XBRL traps handled here, each covered by fixtures in tests/test_normalize.py:

* ``fy``/``fp`` describe the *filing*, not the fact: a FY2025 10-K tags its FY2023
  comparative as fy=2025. Periods are therefore identified from start/end dates.
* A concept appears in many filings for one period. Latest-filed wins by default
  (``vintage="original"`` gives as-first-reported), and restatements are flagged.
* Companies change tags over time, so aliases are resolved per period.
* 10-Q cash-flow statements are year-to-date; discrete quarters are differenced.
* Q4 is rarely tagged directly and is FY minus nine months.
* Debt has no single reliable tag. It is emitted only when reconstructed from
  balance-sheet components; otherwise it is left missing with a warning.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd

Vintage = Literal["latest", "original"]

ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "20-F", "20-F/A")
QUARTERLY_FORMS = ("10-Q", "10-Q/A")
ALL_FORMS = ANNUAL_FORMS + QUARTERLY_FORMS

ANNUAL_DAYS = (350, 380)
QUARTER_DAYS = (75, 105)
HALF_DAYS = (165, 195)
NINE_MONTH_DAYS = (255, 285)
FY_START_TOLERANCE_DAYS = 10
RESTATEMENT_TOLERANCE = 0.005
ALIAS_CONFLICT_TOLERANCE = 0.02
DEBT_AGREEMENT_TOLERANCE = 0.02
QUARTER_RECONCILE_TOLERANCE = 0.01


@dataclass(frozen=True)
class FieldSpec:
    kind: Literal["flow", "instant"]
    concepts: tuple[str, ...]


FIELD_SPECS: dict[str, FieldSpec] = {
    "revenue": FieldSpec("flow", (
        "Revenues",
        "RevenuesNetOfInterestExpense",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    )),
    "operating_income": FieldSpec("flow", ("OperatingIncomeLoss",)),
    "net_income": FieldSpec("flow", ("NetIncomeLoss", "ProfitLoss")),
    "pretax_income": FieldSpec("flow", (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    )),
    "income_tax": FieldSpec("flow", ("IncomeTaxExpenseBenefit",)),
    "interest_expense": FieldSpec("flow", ("InterestExpense", "InterestExpenseNonoperating")),
    "dna": FieldSpec("flow", (
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
    )),
    "cfo": FieldSpec("flow", (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    )),
    "capex": FieldSpec("flow", (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    )),
    "cash": FieldSpec("instant", (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    )),
    "total_assets": FieldSpec("instant", ("Assets",)),
    "total_liabilities": FieldSpec("instant", ("Liabilities",)),
    "stockholders_equity": FieldSpec("instant", ("StockholdersEquity",)),
    "noncontrolling_interest": FieldSpec("instant", ("MinorityInterest",)),
    "preferred_stock": FieldSpec("instant", ("PreferredStockValue",)),
}

DEBT_CONCEPTS = (
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "LongTermDebt",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligationsCurrent",
    "DebtCurrent",
    "ShortTermBorrowings",
    "CommercialPaper",
)


@dataclass
class NormalizedFinancials:
    annual: pd.DataFrame
    quarterly: pd.DataFrame
    lineage: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # routine tag-resolution detail, not data problems


def _days(item: dict[str, Any]) -> int | None:
    if not item.get("start"):
        return None
    return (_d(item["end"]) - _d(item["start"])).days


def _d(value: str) -> date:
    return date.fromisoformat(value)


def _within(days: int | None, bounds: tuple[int, int]) -> bool:
    return days is not None and bounds[0] <= days <= bounds[1]


def fiscal_year_label(end: date) -> int:
    """Calendar year of the period end, except 52/53-week years ending in early January."""
    return end.year - 1 if end.month == 1 and end.day <= 7 else end.year


def _facts_by_period(node: dict[str, Any]) -> dict[tuple[str | None, str], list[dict[str, Any]]]:
    """Group USD facts from accepted forms by their (start, end) context."""
    grouped: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for item in node.get("units", {}).get("USD", []):
        if item.get("form") in ALL_FORMS and item.get("val") is not None and item.get("end"):
            grouped[(item.get("start"), item["end"])].append(item)
    return grouped


def _pick(rows: list[dict[str, Any]], vintage: Vintage) -> tuple[dict[str, Any], bool]:
    """Choose one fact among duplicates; report whether filings disagree on the value."""
    ordered = sorted(rows, key=lambda r: (r.get("filed", ""), r.get("accn", "")))
    chosen = ordered[-1] if vintage == "latest" else ordered[0]
    base = float(chosen["val"])
    restated = any(
        abs(float(r["val"]) - base) > RESTATEMENT_TOLERANCE * max(abs(base), 1.0) for r in rows
    )
    return chosen, restated


@dataclass(frozen=True)
class _Resolved:
    value: float
    start: str | None
    end: str
    concept: str
    accession: str
    form: str
    filed: str
    restated: bool


def _resolve_field(
    us_gaap: dict[str, Any],
    name: str,
    spec: FieldSpec,
    vintage: Vintage,
    notes: list[str],
) -> dict[tuple[str | None, str], _Resolved]:
    """Per-period merge of aliases: the highest-priority concept present wins."""
    merged: dict[tuple[str | None, str], _Resolved] = {}
    conflicts = 0
    used: list[str] = []
    for concept in spec.concepts:
        if concept not in us_gaap:
            continue
        grouped = _facts_by_period(us_gaap[concept])
        contributed = False
        for period, rows in grouped.items():
            chosen, restated = _pick(rows, vintage)
            value = float(chosen["val"])
            if period in merged:
                existing = merged[period].value
                if abs(existing - value) > ALIAS_CONFLICT_TOLERANCE * max(abs(existing), 1.0):
                    conflicts += 1
                continue
            contributed = True
            merged[period] = _Resolved(
                value, period[0], period[1], concept,
                chosen.get("accn", ""), chosen.get("form", ""), chosen.get("filed", ""), restated,
            )
        if contributed:
            used.append(concept)
    if len(used) > 1:
        notes.append(f"{name}: history spans multiple XBRL tags ({', '.join(used)}); resolved per period.")
    if conflicts:
        notes.append(
            f"{name}: {conflicts} period(s) where alternative tags disagree by more than "
            f"{ALIAS_CONFLICT_TOLERANCE:.0%}; the higher-priority tag was used."
        )
    return merged


def _fiscal_calendar(us_gaap: dict[str, Any]) -> list[tuple[date, date]]:
    """Fiscal years, taken from full-year contexts in annual filings."""
    by_end: dict[date, date] = {}
    for spec_name in ("revenue", "net_income", "cfo", "operating_income"):
        for concept in FIELD_SPECS[spec_name].concepts:
            for item in us_gaap.get(concept, {}).get("units", {}).get("USD", []):
                if item.get("form") in ANNUAL_FORMS and _within(_days(item), ANNUAL_DAYS):
                    by_end.setdefault(_d(item["end"]), _d(item["start"]))
    return sorted(((s, e) for e, s in by_end.items()), key=lambda p: p[1])


def _fiscal_years_with_stub(calendar: list[tuple[date, date]]) -> list[tuple[date, date, bool]]:
    """Append the in-progress fiscal year so that recent 10-Qs have a home."""
    out = [(s, e, True) for s, e in calendar]
    if calendar:
        last_end = calendar[-1][1]
        out.append((last_end + timedelta(days=1), last_end + timedelta(days=371), False))
    return out


def _quarter_number(start: date, end: date) -> int:
    return int(min(4, max(1, round((end - start).days / 91.3))))


def _lineage_row(
    field_name: str, period_type: str, fy: int, fp: str, end: str, value: float, unit: str,
    derivation: str, concept: str, accession: str, form: str, filed: str, restated: bool, components: str = "",
) -> dict[str, Any]:
    return {
        "field": field_name, "period_type": period_type, "fiscal_year": fy, "fiscal_period": fp,
        "period_end": end, "value": value, "unit": unit, "derivation": derivation, "concept": concept,
        "accession": accession, "form": form, "filed": filed, "restated": restated, "components": components,
    }


def _build_flow_rows(name: str, resolved: dict, fiscal_years: list[tuple[date, date, bool]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_ctx = [(_d(k[0]), _d(k[1]), v) for k, v in resolved.items() if k[0]]

    def row(ptype: str, fy: int, fp: str, r_end: str, value: float, derivation: str, parts: list[_Resolved]) -> dict:
        lead = parts[-1]
        return _lineage_row(
            name, ptype, fy, fp, r_end, value, "USD", derivation, lead.concept, lead.accession, lead.form,
            lead.filed, any(p.restated for p in parts), ";".join(p.accession for p in parts),
        )

    for fy_start, fy_end, complete in fiscal_years:
        fy = fiscal_year_label(fy_end)
        in_year = [
            (s, e, v) for s, e, v in by_ctx
            if fy_start - timedelta(days=FY_START_TOLERANCE_DAYS) <= s and e <= fy_end + timedelta(days=FY_START_TOLERANCE_DAYS)
        ]
        annual = next((v for s, e, v in in_year if complete and e == fy_end and _within((e - s).days, ANNUAL_DAYS)), None)
        if annual is not None:
            rows.append(row("annual", fy, "FY", annual.end, annual.value, "reported", [annual]))

        direct: dict[int, _Resolved] = {}
        ytd: dict[int, _Resolved] = {}
        for s, e, v in in_year:
            days = (e - s).days
            if _within(days, QUARTER_DAYS):
                q = _quarter_number(fy_start, e)
                if q not in direct or v.filed > direct[q].filed:
                    direct[q] = v
            elif abs((s - fy_start).days) <= FY_START_TOLERANCE_DAYS:
                if _within(days, HALF_DAYS):
                    ytd[2] = v
                elif _within(days, NINE_MONTH_DAYS):
                    ytd[3] = v

        quarters: dict[int, float] = {}
        for q in (1, 2, 3, 4):
            if q in direct:
                quarters[q] = direct[q].value
                rows.append(row("quarterly", fy, f"Q{q}", direct[q].end, direct[q].value, "reported", [direct[q]]))
            elif q == 2 and 2 in ytd and 1 in direct:
                quarters[2] = ytd[2].value - direct[1].value
                rows.append(row("quarterly", fy, "Q2", ytd[2].end, quarters[2], "ytd_difference", [direct[1], ytd[2]]))
            elif q == 3 and 3 in ytd and 2 in ytd:
                quarters[3] = ytd[3].value - ytd[2].value
                rows.append(row("quarterly", fy, "Q3", ytd[3].end, quarters[3], "ytd_difference", [ytd[2], ytd[3]]))
            elif q == 3 and 3 in ytd and 1 in quarters and 2 in quarters and 2 in direct:
                quarters[3] = ytd[3].value - quarters[1] - quarters[2]
                rows.append(row("quarterly", fy, "Q3", ytd[3].end, quarters[3], "ytd_difference", [direct[1], direct[2], ytd[3]]))
            elif q == 4 and annual is not None and 3 in ytd:
                quarters[4] = annual.value - ytd[3].value
                rows.append(row("quarterly", fy, "Q4", annual.end, quarters[4], "q4_fy_minus_ytd", [ytd[3], annual]))
            elif q == 4 and annual is not None and all(i in direct for i in (1, 2, 3)):
                quarters[4] = annual.value - sum(direct[i].value for i in (1, 2, 3))
                rows.append(row("quarterly", fy, "Q4", annual.end, quarters[4], "q4_fy_minus_quarters", [direct[1], direct[2], direct[3], annual]))
    return rows


def reconstruct_debt(values: dict[str, float]) -> tuple[float, str, str] | None:
    """Total debt from one balance-sheet date, or None if it cannot be trusted.

    Returns ``(debt, method, confidence)``. Excludes operating leases. Requires an
    explicit current portion: a noncurrent line alone could understate debt.
    """
    short_term = values.get("ShortTermBorrowings", values.get("CommercialPaper", 0.0))
    noncurrent = values.get("LongTermDebtNoncurrent")
    current = values.get("LongTermDebtCurrent")
    total_ltd = values.get("LongTermDebt")
    lease_nc = values.get("LongTermDebtAndCapitalLeaseObligations")
    lease_cur = values.get("LongTermDebtAndCapitalLeaseObligationsCurrent")
    debt_current = values.get("DebtCurrent")

    def agrees(a: float, b: float) -> bool:
        return abs(a - b) <= DEBT_AGREEMENT_TOLERANCE * max(abs(a), abs(b), 1.0)

    if noncurrent is not None and (current is not None or debt_current is not None):
        if current is not None:
            debt, method = noncurrent + current + short_term, "LTD noncurrent + current + short-term"
            ltd_view = noncurrent + current
        else:
            debt, method = noncurrent + debt_current, "LTD noncurrent + DebtCurrent"
            ltd_view = None
        if total_ltd is not None and ltd_view is not None:
            confidence = "high" if agrees(ltd_view, total_ltd) else "medium"
        else:
            confidence = "medium"
        return debt, method, confidence

    if lease_nc is not None and lease_cur is not None:
        ltd_view = lease_nc + lease_cur
        confidence = "high" if total_ltd is not None and agrees(ltd_view, total_ltd) else "medium"
        return ltd_view + short_term, "LTD and finance leases noncurrent + current + short-term", confidence

    if total_ltd is not None and noncurrent is None and lease_nc is None:
        return total_ltd + short_term, "LongTermDebt (total) + short-term", "medium"

    if noncurrent is not None and total_ltd is not None:
        return total_ltd + short_term, "LongTermDebt (total) + short-term", "medium"

    return None


def _instant_values(us_gaap: dict[str, Any], concept: str, vintage: Vintage) -> dict[str, tuple[float, dict]]:
    out: dict[str, tuple[float, dict]] = {}
    grouped = _facts_by_period(us_gaap.get(concept, {}))
    for (start, end), rows in grouped.items():
        if start is None:
            chosen, _ = _pick(rows, vintage)
            out[end] = (float(chosen["val"]), chosen)
    return out


def normalize_company_facts(companyfacts: dict[str, Any], *, vintage: Vintage = "latest") -> NormalizedFinancials:
    warnings: list[str] = []
    notes: list[str] = []
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    if not us_gaap:
        warnings.append("No us-gaap facts available (foreign filer or no XBRL); nothing could be normalized.")
        empty = pd.DataFrame()
        return NormalizedFinancials(empty, empty, empty, warnings)

    calendar = _fiscal_calendar(us_gaap)
    fiscal_years = _fiscal_years_with_stub(calendar)
    if not calendar:
        warnings.append("No full fiscal-year contexts found; annual history is empty.")

    lineage: list[dict[str, Any]] = []
    for name, spec in FIELD_SPECS.items():
        resolved = _resolve_field(us_gaap, name, spec, vintage, notes)
        if not resolved:
            warnings.append(f"{name}: no matching XBRL concept reported ({', '.join(spec.concepts)}).")
            continue
        if spec.kind == "flow":
            lineage.extend(_build_flow_rows(name, resolved, fiscal_years))

    flow_periods = {
        (r["period_type"], r["fiscal_year"], r["fiscal_period"]): r["period_end"] for r in lineage
    }
    # Instants attach to the period calendar established by the flow statements.
    for name, spec in FIELD_SPECS.items():
        if spec.kind != "instant":
            continue
        resolved = _resolve_field(us_gaap, name, spec, vintage, [])
        by_end = {k[1]: v for k, v in resolved.items() if k[0] is None}
        for (ptype, fy, fp), end in flow_periods.items():
            if end in by_end:
                v = by_end[end]
                lineage.append(_lineage_row(name, ptype, fy, fp, end, v.value, "USD", "reported", v.concept, v.accession, v.form, v.filed, v.restated))

    debt_tags = {c: _instant_values(us_gaap, c, vintage) for c in DEBT_CONCEPTS}
    undetermined: list[str] = []
    downgraded = 0
    for (ptype, fy, fp), end in flow_periods.items():
        values = {c: tags[end][0] for c, tags in debt_tags.items() if end in tags}
        if not values:
            continue
        result = reconstruct_debt(values)
        if result is None:
            undetermined.append(end)
            continue
        debt, method, confidence = result
        downgraded += confidence != "high"
        anchor = next(tags[end][1] for tags in debt_tags.values() if end in tags)
        lineage.append(_lineage_row(
            "debt", ptype, fy, fp, end, debt, "USD", f"reconstructed:{confidence}", method,
            anchor.get("accn", ""), anchor.get("form", ""), anchor.get("filed", ""), False, "+".join(sorted(values)),
        ))
    if undetermined:
        latest = max(undetermined)
        warnings.append(f"debt: could not be reconstructed for {len(set(undetermined))} period end(s), latest {latest}; left missing rather than guessed.")
    if not any(debt_tags[c] for c in DEBT_CONCEPTS):
        warnings.append("debt: no debt concepts reported; left missing (not assumed zero).")

    lineage_df = pd.DataFrame(lineage)
    if lineage_df.empty:
        warnings.append("No usable facts after normalization.")
        return NormalizedFinancials(pd.DataFrame(), pd.DataFrame(), lineage_df, warnings)
    lineage_df = lineage_df.sort_values(["period_end", "field"]).reset_index(drop=True)

    annual = _wide(lineage_df, "annual")
    quarterly = _wide(lineage_df, "quarterly")
    for frame, label in ((annual, "annual"), (quarterly, "quarterly")):
        _check_integrity(frame, label, warnings)
    _check_quarters_reconcile(annual, quarterly, warnings)
    return NormalizedFinancials(annual, quarterly, lineage_df, warnings, notes)


def _wide(lineage: pd.DataFrame, period_type: str) -> pd.DataFrame:
    part = lineage[lineage["period_type"] == period_type]
    if part.empty:
        return pd.DataFrame()
    wide = part.pivot_table(
        index=["fiscal_year", "fiscal_period", "period_end"], columns="field", values="value", aggfunc="first"
    ).reset_index()
    wide.columns.name = None
    for name in [*FIELD_SPECS, "debt"]:
        if name not in wide:
            wide[name] = np.nan
    # NaN propagates: FCF exists only when CFO and capex are both known for the period.
    wide["fcf"] = wide["cfo"] - wide["capex"]
    return wide.sort_values("period_end").reset_index(drop=True)


def _check_integrity(frame: pd.DataFrame, label: str, warnings: list[str]) -> None:
    if frame.empty:
        warnings.append(f"{label} history is empty.")
        return
    latest = frame.iloc[-1]
    missing = [c for c in ("revenue", "operating_income", "net_income", "cfo", "capex", "cash", "debt") if pd.isna(latest[c])]
    if missing:
        warnings.append(f"{label}: latest period ({latest['period_end']}) is missing {', '.join(missing)}.")
    if (frame["capex"] < 0).any():
        warnings.append(f"{label}: negative capex reported in {int((frame['capex'] < 0).sum())} period(s); sign left as filed.")
    breach = frame[(frame["debt"].notna()) & (frame["total_liabilities"].notna()) & (frame["debt"] > frame["total_liabilities"])]
    if not breach.empty:
        warnings.append(f"{label}: reconstructed debt exceeds total liabilities in {len(breach)} period(s); treat debt as unreliable.")


def _check_quarters_reconcile(annual: pd.DataFrame, quarterly: pd.DataFrame, warnings: list[str]) -> None:
    """Four discrete quarters should sum to the fiscal year, barring restatements."""
    if annual.empty or quarterly.empty:
        return
    for name in ("revenue", "cfo", "capex", "net_income"):
        counts = quarterly.dropna(subset=[name]).groupby("fiscal_year")[name].agg(["sum", "count"])
        joined = counts[counts["count"] == 4].join(annual.set_index("fiscal_year")[name], how="inner").dropna()
        gap = (joined["sum"] - joined[name]).abs() > QUARTER_RECONCILE_TOLERANCE * joined[name].abs().clip(lower=1.0)
        if gap.any():
            years = ", ".join(str(y) for y in joined.index[gap])
            warnings.append(f"{name}: quarters do not sum to the fiscal year within {QUARTER_RECONCILE_TOLERANCE:.0%} for FY {years} (likely restatement).")


def trailing_twelve_months(quarterly: pd.DataFrame, field_name: str) -> tuple[float, str] | None:
    """Sum the latest four quarters, only if all exist and are contiguous."""
    if quarterly.empty or field_name not in quarterly:
        return None
    usable = quarterly.dropna(subset=[field_name]).tail(4)
    if len(usable) < 4:
        return None
    ends = pd.to_datetime(usable["period_end"]).reset_index(drop=True)
    if not all(75 <= d <= 105 for d in ends.diff().dropna().dt.days):
        return None
    if ends.iloc[-1] != pd.to_datetime(quarterly["period_end"]).iloc[-1]:
        return None
    return float(usable[field_name].sum()), str(usable["period_end"].iloc[-1])


def latest_shares_outstanding(companyfacts: dict[str, Any]) -> dict[str, Any] | None:
    """Most recent share count: the filing cover page, else the balance sheet.

    Multi-class issuers may report the cover count only by class, which Company
    Facts omits; the balance-sheet figure then acts as the fallback.
    """
    sources = [
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
    ]
    for taxonomy, concept in sources:
        rows = companyfacts.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {}).get("shares", [])
        rows = [r for r in rows if r.get("form") in ALL_FORMS and r.get("val")]
        if rows:
            best = max(rows, key=lambda r: (r.get("end", ""), r.get("filed", "")))
            return {
                "shares": float(best["val"]), "as_of": best.get("end", ""), "concept": concept,
                "accession": best.get("accn", ""), "form": best.get("form", ""), "filed": best.get("filed", ""),
            }
    return None
