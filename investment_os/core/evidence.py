"""Evidence schema and the ledger that enforces sourcing rules at insertion."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    REPORTED = "reported"
    DERIVED = "derived"
    ASSUMED = "assumed"
    JUDGMENT = "judgment"


@dataclass(frozen=True)
class EvidenceItem:
    """One auditable fact, calculation, assumption, or opinion.

    ``source`` is a URL for reported facts. ``inputs`` lists the evidence ids a
    derived value was calculated from, so a number can be traced to its filings.
    """

    id: str
    claim: str
    value: Any
    kind: EvidenceKind
    source: str = ""
    retrieved_at: str = ""
    notes: str = ""
    unit: str = ""
    form: str = ""
    period: str = ""
    filed: str = ""
    accession: str = ""
    inputs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["kind"] = self.kind.value
        out["inputs"] = list(self.inputs)
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvidenceItem":
        data = dict(raw)
        data["kind"] = EvidenceKind(data["kind"])
        data["inputs"] = tuple(data.get("inputs") or ())
        return cls(**data)


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


class EvidenceLedger:
    """Audit trail used by memos and research agents.

    Enforced at insertion, so an unsourced number cannot enter a memo:

    * reported -> http(s) source URL and a retrieval timestamp;
    * derived  -> a source, or ``inputs`` that already exist in this ledger;
    * assumed / judgment -> may be source-free, but are labeled as such.
    """

    def __init__(self, items: list[EvidenceItem] | None = None):
        self._items: dict[str, EvidenceItem] = {}
        for item in items or []:
            self.add(item)

    def add(self, item: EvidenceItem) -> None:
        if item.id in self._items:
            raise ValueError(f"Duplicate evidence id: {item.id}")
        if item.kind is EvidenceKind.REPORTED:
            if not _is_url(item.source):
                raise ValueError(f"reported evidence requires a source URL: {item.id}")
            if not item.retrieved_at:
                raise ValueError(f"reported evidence requires a retrieval timestamp: {item.id}")
        if item.kind is EvidenceKind.DERIVED and not (item.source or item.inputs):
            raise ValueError(f"derived evidence requires a source or inputs: {item.id}")
        missing = [i for i in item.inputs if i not in self._items]
        if missing:
            raise ValueError(f"{item.id} references unknown evidence inputs: {missing}")
        self._items[item.id] = item

    def get(self, evidence_id: str) -> EvidenceItem:
        return self._items[evidence_id]

    def ids(self) -> set[str]:
        return set(self._items)

    def __contains__(self, evidence_id: str) -> bool:
        return evidence_id in self._items

    def __len__(self) -> int:
        return len(self._items)

    def items(self) -> list[EvidenceItem]:
        return list(self._items.values())

    def by_kind(self, kind: EvidenceKind) -> list[EvidenceItem]:
        return [item for item in self._items.values() if item.kind is kind]

    def as_list(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._items.values()]

    @classmethod
    def from_list(cls, rows: list[dict[str, Any]]) -> "EvidenceLedger":
        return cls([EvidenceItem.from_dict(row) for row in rows])

    def markdown(self) -> str:
        lines = []
        for item in self._items.values():
            unit = f" {item.unit}" if item.unit else ""
            filing = " | ".join(x for x in (item.form, item.period, f"filed {item.filed}" if item.filed else "") if x)
            filing = f" | {filing}" if filing else ""
            source = f" | Source: {item.source}" if item.source else ""
            retrieved = f" | Retrieved: {item.retrieved_at}" if item.retrieved_at else ""
            inputs = f" | Inputs: {', '.join(item.inputs)}" if item.inputs else ""
            lines.append(
                f"- **[{item.id}] {item.claim}** — {item.value}{unit} "
                f"({item.kind.value}){filing}{source}{retrieved}{inputs}"
            )
        return "\n".join(lines)


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
