import pytest

from investment_os.core.evidence import EvidenceItem, EvidenceKind, EvidenceLedger
from investment_os.research.thesis import build_manual_thesis_plan


def test_reported_evidence_requires_source():
    with pytest.raises(ValueError):
        EvidenceLedger([EvidenceItem("R1", "Revenue", 100, EvidenceKind.REPORTED)])


def test_assumption_can_be_source_free():
    ledger = EvidenceLedger([EvidenceItem("A1", "WACC", "9%", EvidenceKind.ASSUMED)])
    assert "A1" in ledger.ids()


def test_thesis_plan_alignment_validation():
    with pytest.raises(ValueError):
        build_manual_thesis_plan("x", claims=["a", "b"], evidence_needed=[["one"]])
