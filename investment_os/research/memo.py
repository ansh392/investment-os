"""Hand-assembled memo builder used by scripts/demo.py; company memos use ic_memo."""
from __future__ import annotations

from dataclasses import dataclass

from investment_os.core.evidence import EvidenceLedger


@dataclass(frozen=True)
class MemoInputs:
    company: str
    recommendation: str
    thesis: str
    variant_perception: str
    valuation_summary: str
    bull_case: str
    bear_case: str
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]
    falsification_tests: tuple[str, ...]
    next_diligence: tuple[str, ...] = ()


class ICMemoBuilder:
    def build(self, x: MemoInputs, ledger: EvidenceLedger) -> str:
        return "\n".join([
            f"# Investment Committee Memo — {x.company}",
            "",
            f"**Recommendation:** {x.recommendation}",
            "",
            "## Thesis",
            x.thesis.strip(),
            "",
            "## Variant Perception",
            x.variant_perception.strip(),
            "",
            "## Valuation",
            x.valuation_summary.strip(),
            "",
            "## Bull Case",
            x.bull_case.strip(),
            "",
            "## Bear Case",
            x.bear_case.strip(),
            "",
            "## Catalysts",
            *[f"- {v}" for v in x.catalysts],
            "",
            "## Risks",
            *[f"- {v}" for v in x.risks],
            "",
            "## Falsification Tests",
            *[f"- {v}" for v in x.falsification_tests],
            "",
            "## Next Diligence",
            *[f"- {v}" for v in x.next_diligence],
            "",
            "## Evidence Ledger",
            ledger.markdown(),
        ])
