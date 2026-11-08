from __future__ import annotations

import json
import re
from typing import Any

from investment_os.config import settings
from investment_os.core.evidence import EvidenceLedger
from investment_os.research.ic_memo import CITATION
from investment_os.research.thesis_lab import ThesisReport

SYSTEM_PROMPT = """You are an institutional investment-research copilot.
Rules:
1. Never invent a filing fact, market statistic, source, or model output.
2. Facts must cite supplied evidence IDs in square brackets.
3. Separate reported facts, derived model outputs, assumptions, and judgment.
4. Build the strongest bear case, not a token counterargument.
5. State what evidence would falsify each key claim.
6. Identify what appears priced in versus what must be true for the thesis to work.
7. If evidence is missing, say MISSING rather than fill the gap.
Return concise investment-committee-quality analysis, not generic prose.
"""


REWORD_PROMPT = """Reword each investment claim to be sharper and more testable.
Do not add any number, company fact, source, or evidence that is not in the original claim.
Return only a JSON object mapping claim id to the reworded statement."""

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def apply_claim_rewording(
    report: ThesisReport, proposed: dict[str, str], ledger: EvidenceLedger,
) -> tuple[ThesisReport, list[str]]:
    """Apply LLM wording only where it adds no number or unknown citation.

    The deterministic findings, statuses and evidence are never touched. Returns the
    report and a list of rejected claim ids with reasons.
    """
    rejected: list[str] = []
    claims = {c.id: c for c in report.claims}
    for claim_id, text in proposed.items():
        claim = claims.get(claim_id)
        if claim is None:
            rejected.append(f"{claim_id}: unknown claim id")
        elif not isinstance(text, str) or not text.strip():
            rejected.append(f"{claim_id}: empty rewording")
        elif set(_NUMBER.findall(text)) - set(_NUMBER.findall(claim.statement)):
            rejected.append(f"{claim_id}: introduces a number absent from the original claim")
        elif [i for i in CITATION.findall(text) if i not in ledger]:
            rejected.append(f"{claim_id}: cites unknown evidence")
        else:
            claim.statement = text.strip()
    return report, rejected


def unknown_citations(text: str, ledger: EvidenceLedger) -> list[str]:
    return sorted({i for i in CITATION.findall(text.replace("[MISSING]", "")) if i not in ledger})


class AnthropicResearchAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Install anthropic to use AnthropicResearchAgent") from exc
        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required")
        self.client = Anthropic(api_key=key)
        self.model = model or settings.anthropic_model

    def _complete(self, system: str, content: str) -> str:
        options: dict[str, Any] = {}
        if settings.anthropic_effort:
            options["output_config"] = {"effort": settings.anthropic_effort}
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=settings.anthropic_max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            **options,
        )
        return "\n".join(block.text for block in msg.content if getattr(block, "type", None) == "text")

    def analyze(
        self,
        *,
        hypothesis: str,
        evidence: list[dict[str, Any]],
        model_outputs: dict[str, Any],
        thesis_plan: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "hypothesis": hypothesis,
            "thesis_plan": thesis_plan or {},
            "evidence": evidence,
            "model_outputs": model_outputs,
            "required_sections": [
                "recommendation",
                "variant perception",
                "supporting evidence",
                "bear case / contradictory evidence",
                "valuation implications",
                "catalysts",
                "falsification tests",
                "missing diligence",
            ],
        }
        return self._complete(SYSTEM_PROMPT, json.dumps(payload, default=str))

    def checked_analyze(self, *, ledger: EvidenceLedger, **kwargs: Any) -> str:
        """Run ``analyze`` and reject output that cites evidence outside the ledger."""
        text = self.analyze(evidence=ledger.as_list(), **kwargs)
        if not text.strip():
            raise RuntimeError("The model returned no text (possibly a refusal).")
        unknown = unknown_citations(text, ledger)
        if unknown:
            raise ValueError(f"Agent output cites evidence not in the ledger: {unknown}")
        return text

    def reword_claims(self, report: ThesisReport, ledger: EvidenceLedger) -> tuple[ThesisReport, list[str]]:
        """Improve claim wording; a malformed reply leaves the deterministic claims as they were."""
        text = self._complete(REWORD_PROMPT, json.dumps({c.id: c.statement for c in report.claims}))
        match = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            proposed = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            proposed = None
        if not isinstance(proposed, dict):
            return report, ["Model reply was not valid JSON; deterministic claims kept."]
        return apply_claim_rewording(report, proposed, ledger)
