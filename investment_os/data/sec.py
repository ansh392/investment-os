"""SEC EDGAR client: ticker lookup, Company Facts, submissions and filing links."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import requests

from investment_os.config import settings
from investment_os.core.evidence import EvidenceItem, EvidenceKind, today_iso

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SEC_MIN_REQUEST_INTERVAL = 0.12  # SEC fair-access limit is 10 requests/second.
ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS = 350, 380


class SECError(RuntimeError):
    pass


@dataclass(frozen=True)
class SECFact:
    concept: str
    value: float
    unit: str
    filed: str
    form: str
    end: str = ""
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    accession: str = ""


CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_income": ("OperatingIncomeLoss",),
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
}

# Duration concepts: "latest" must compare like with like (full fiscal years).
FLOW_FIELDS = frozenset({"revenue", "net_income", "operating_income", "cfo", "capex"})


def _duration_days(item: dict[str, Any]) -> int | None:
    if not item.get("start") or not item.get("end"):
        return None
    return (date.fromisoformat(item["end"]) - date.fromisoformat(item["start"])).days


def filing_url(cik: int, accession: str, document: str = "") -> str:
    """Direct URL for a filing's primary document, or its folder if unknown."""
    return SEC_ARCHIVE_URL.format(cik=int(cik), accession=accession.replace("-", ""), document=document)


def filings_frame(submissions: dict[str, Any]) -> pd.DataFrame:
    """Flatten EDGAR submissions JSON into one row per filing with a source URL."""
    cik = int(submissions["cik"])
    columns = ["accessionNumber", "form", "filingDate", "reportDate", "primaryDocument"]
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent.get("accessionNumber"):
        return pd.DataFrame(columns=["accession", "form", "filed", "report_date", "primary_document", "url"])
    df = pd.DataFrame({c: recent.get(c, [""] * len(recent["accessionNumber"])) for c in columns}).rename(
        columns={
            "accessionNumber": "accession",
            "filingDate": "filed",
            "reportDate": "report_date",
            "primaryDocument": "primary_document",
        }
    )
    df["url"] = [filing_url(cik, a, d) for a, d in zip(df["accession"], df["primary_document"])]
    return df.drop_duplicates("accession").sort_values("filed", ascending=False).reset_index(drop=True)


class SECClient:
    """Thin client for SEC public EDGAR JSON APIs, within SEC fair-access limits."""

    def __init__(self, user_agent: str | None = None, timeout: int = 30, retries: int = 3):
        self.user_agent = user_agent or settings.sec_user_agent
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})
        self._ticker_map: dict[str, int] | None = None
        self._last_request = 0.0

    def _get_json(self, url: str) -> dict[str, Any]:
        for attempt in range(self.retries):
            wait = SEC_MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in {429, 500, 502, 503, 504} or attempt == self.retries - 1:
                raise SECError(f"SEC request failed ({r.status_code}): {url}")
            time.sleep(2**attempt)
        raise SECError(f"SEC request failed: {url}")

    def ticker_map(self) -> dict[str, int]:
        if self._ticker_map is None:
            raw = self._get_json(SEC_TICKERS_URL)
            self._ticker_map = {item["ticker"].upper(): int(item["cik_str"]) for item in raw.values()}
        return self._ticker_map

    def cik_for_ticker(self, ticker: str) -> int:
        ticker = ticker.upper()
        mapping = self.ticker_map()
        if ticker not in mapping:
            raise SECError(f"Ticker {ticker!r} not found in SEC ticker map")
        return mapping[ticker]

    def companyfacts(self, ticker: str) -> dict[str, Any]:
        cik = self.cik_for_ticker(ticker)
        return self._get_json(SEC_COMPANYFACTS_URL.format(cik=cik))

    def submissions(self, cik: int) -> dict[str, Any]:
        return self._get_json(SEC_SUBMISSIONS_URL.format(cik=cik))

    @staticmethod
    def latest_fact(
        companyfacts: dict[str, Any],
        concept: str,
        *,
        units_preference: tuple[str, ...] = ("USD", "shares", "USD/shares"),
        forms: tuple[str, ...] = ("10-K", "10-Q"),
        annual_only: bool = False,
    ) -> SECFact | None:
        facts = companyfacts.get("facts", {}).get("us-gaap", {})
        node = facts.get(concept)
        if not node:
            return None
        candidates: list[tuple[str, dict[str, Any]]] = []
        for unit in units_preference:
            for item in node.get("units", {}).get(unit, []):
                if item.get("form") not in forms or item.get("val") is None:
                    continue
                if annual_only:
                    days = _duration_days(item)
                    if days is None or not ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
                        continue
                candidates.append((unit, item))
        if not candidates:
            return None
        # Period end first: a new filing also carries prior-year comparatives.
        unit, item = max(candidates, key=lambda x: (x[1].get("end", ""), x[1].get("filed", "")))
        return SECFact(
            concept=concept,
            value=float(item["val"]),
            unit=unit,
            filed=item.get("filed", ""),
            form=item.get("form", ""),
            end=item.get("end", ""),
            fiscal_year=item.get("fy"),
            fiscal_period=item.get("fp"),
            accession=item.get("accn", ""),
        )

    @classmethod
    def latest_standardized(cls, companyfacts: dict[str, Any]) -> dict[str, SECFact]:
        """Latest value per field, for full fiscal years where the field is a flow.

        Compares every alias by period end, so a discontinued XBRL tag cannot win
        merely because it appears earlier in the alias list.
        """
        out: dict[str, SECFact] = {}
        for field, aliases in CONCEPT_ALIASES.items():
            found = [
                fact
                for concept in aliases
                if (fact := cls.latest_fact(companyfacts, concept, annual_only=field in FLOW_FIELDS)) is not None
            ]
            if found:
                # max() keeps the first maximal element, so alias order breaks ties.
                out[field] = max(found, key=lambda f: f.end)
        return out

    @staticmethod
    def fact_to_evidence(ticker: str, field: str, fact: SECFact, cik: int | None = None) -> EvidenceItem:
        symbol = ticker.upper()
        if cik is not None and fact.accession:
            source = filing_url(cik, fact.accession)
        else:
            source = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}&type=10-K"
        return EvidenceItem(
            id=f"SEC-{symbol}-{field}",
            claim=f"Latest SEC-reported {field}",
            value=f"{fact.value:g}",
            kind=EvidenceKind.REPORTED,
            source=source,
            retrieved_at=today_iso(),
            notes=f"Concept={fact.concept}",
            unit=fact.unit,
            form=fact.form,
            period=fact.end,
            filed=fact.filed,
            accession=fact.accession,
        )
