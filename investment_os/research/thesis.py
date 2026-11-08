from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThesisClaim:
    id: str
    statement: str
    evidence_needed: tuple[str, ...] = ()
    falsified_if: tuple[str, ...] = ()


@dataclass(frozen=True)
class ThesisPlan:
    hypothesis: str
    claims: tuple[ThesisClaim, ...]
    variant_perception_question: str
    key_unknowns: tuple[str, ...] = field(default_factory=tuple)


def build_manual_thesis_plan(
    hypothesis: str,
    *,
    claims: list[str],
    evidence_needed: list[list[str]] | None = None,
    falsification_tests: list[list[str]] | None = None,
    variant_perception_question: str = "What does the market appear to price differently from this thesis?",
    key_unknowns: list[str] | None = None,
) -> ThesisPlan:
    evidence_needed = evidence_needed or [[] for _ in claims]
    falsification_tests = falsification_tests or [[] for _ in claims]
    if not (len(claims) == len(evidence_needed) == len(falsification_tests)):
        raise ValueError("claims, evidence_needed, and falsification_tests must align")
    claim_objs = tuple(
        ThesisClaim(
            id=f"C{i+1}",
            statement=claim,
            evidence_needed=tuple(evidence_needed[i]),
            falsified_if=tuple(falsification_tests[i]),
        )
        for i, claim in enumerate(claims)
    )
    return ThesisPlan(
        hypothesis=hypothesis,
        claims=claim_objs,
        variant_perception_question=variant_perception_question,
        key_unknowns=tuple(key_unknowns or []),
    )
