import dataclasses

import numpy as np
import pandas as pd
import pytest

from conftest import FakeSEC, calendar_company, fake_prices, submissions
from investment_os.core.evidence import EvidenceItem, EvidenceKind, EvidenceLedger
from investment_os.models.valuation import DCFInputs, dcf_valuation
from investment_os.models.workspace import (
    BaseFinancials,
    OperatingAssumptions,
    ValuationNotApplicable,
    build_bridge,
    comps_implied_values,
    comps_table,
    default_scenarios,
    implied_ebit_margin,
    implied_revenue_growth,
    market_expectations,
    probability_weighted_price,
    value_bridge_table,
    value_scenario,
)
from investment_os.pipeline import build_bundle, load_bundle
from investment_os.research.agent import apply_claim_rewording, unknown_citations
from investment_os.research.ic_memo import build_memo, export_memo, memo_to_html, recommendation_for, validate_citations
from investment_os.research.thesis_lab import MAX_CLAIMS, MIN_CLAIMS, run_thesis_lab, select_categories
from investment_os.research.workflow import run_valuation
from investment_os.sectors import plugin_for_sic


def assumptions(**kw):
    defaults = dict(
        name="base", revenue_growth=(0.1, 0.1, 0.1), ebit_margin=(0.2, 0.2, 0.2), tax_rate=0.25, dna_pct_revenue=0.05,
        capex_pct_revenue=0.07, nwc_pct_delta_revenue=0.1, wacc=0.1, terminal_growth=0.02,
    )
    return OperatingAssumptions(**{**defaults, **kw})


# --- Evidence ledger -------------------------------------------------------

def test_reported_requires_url_not_just_text():
    with pytest.raises(ValueError):
        EvidenceLedger([EvidenceItem("R1", "x", 1, EvidenceKind.REPORTED, source="a filing", retrieved_at="2025-01-01")])


def test_reported_requires_retrieval_timestamp():
    with pytest.raises(ValueError):
        EvidenceLedger([EvidenceItem("R1", "x", 1, EvidenceKind.REPORTED, source="https://sec.gov/x")])


def test_derived_must_reference_existing_inputs():
    with pytest.raises(ValueError):
        EvidenceLedger([EvidenceItem("D1", "x", 1, EvidenceKind.DERIVED, inputs=("MISSING",))])


def test_ledger_round_trips_through_json_shape():
    ledger = EvidenceLedger([
        EvidenceItem("R1", "x", 1.5, EvidenceKind.REPORTED, source="https://sec.gov/x", retrieved_at="t", unit="USD"),
        EvidenceItem("D1", "y", 3.0, EvidenceKind.DERIVED, inputs=("R1",)),
    ])
    restored = EvidenceLedger.from_list(ledger.as_list())
    assert restored.get("D1").inputs == ("R1",) and restored.get("R1").kind is EvidenceKind.REPORTED


# --- Pipeline --------------------------------------------------------------

def test_bundle_links_reported_facts_to_filing(bundle):
    item = bundle.ledger.get("R.revenue.FY2024")
    assert item.source.endswith("/000000000125000010/fixture-20241231.htm")
    assert item.kind is EvidenceKind.REPORTED and item.form == "10-K" and item.retrieved_at


def test_q4_values_are_recorded_as_derived_not_reported(bundle):
    assert "D.cfo.2024Q4" in bundle.ledger and "R.cfo.2024Q4" not in bundle.ledger


def test_enterprise_value_arithmetic(bundle):
    m = bundle.market
    assert m["market_cap"] == pytest.approx(150 * 10)
    assert m["enterprise_value"] == pytest.approx(1500 + 220 - 50)


def test_enterprise_value_not_computed_without_reliable_debt(tmp_path):
    facts = calendar_company()
    del facts["facts"]["us-gaap"]["LongTermDebtCurrent"]
    b = build_bundle("FIX", client=FakeSEC(facts, submissions()), price_fetcher=fake_prices, output_dir=tmp_path)
    assert b.market["enterprise_value"] is None
    assert any("Enterprise value not computed" in w for w in b.warnings)


def test_price_failure_warns_and_does_not_invent(tmp_path):
    def broken(_):
        raise RuntimeError("feed down")

    b = build_bundle("FIX", client=FakeSEC(calendar_company(), submissions()), price_fetcher=broken, output_dir=tmp_path)
    assert b.market["price"] is None and "M.price" not in b.ledger
    assert any("feed down" in w for w in b.warnings)


def test_saved_bundle_reloads_identically(bundle, tmp_path):
    reloaded = load_bundle("FIX", root=tmp_path)
    assert reloaded.ledger.ids() == bundle.ledger.ids()
    assert reloaded.market == bundle.market


# --- Valuation -------------------------------------------------------------

def test_bridge_identity():
    b = build_bridge(1000, assumptions())
    assert np.allclose(b.fcff, b.ebit - b.taxes + b.dna - b.capex - b.delta_nwc)
    assert b.revenue.iloc[0] == pytest.approx(1100)


def test_no_tax_credit_on_losses():
    assert (build_bridge(1000, assumptions(ebit_margin=(-0.1, -0.1, -0.1))).taxes == 0).all()


def test_workspace_matches_core_dcf_engine():
    a = assumptions()
    r = value_scenario(1000, a, 100, 10)
    direct = dcf_valuation(DCFInputs(tuple(build_bridge(1000, a).fcff), a.wacc, a.terminal_growth, 100, 10))
    assert r.implied_price == pytest.approx(direct["implied_price"])


def test_value_bridge_foots():
    r = value_scenario(1000, assumptions(), 100, 10)
    t = value_bridge_table(r).set_index("line")["value"]
    assert t["Enterprise value"] == pytest.approx(t["PV of forecast FCFF"] + t["PV of terminal value"])
    assert t["Equity value"] == pytest.approx(t["Enterprise value"] - 100)


def test_implied_growth_round_trip():
    a = assumptions(revenue_growth=(0.12,) * 3)
    ev = value_scenario(1000, a, 0, 1).dcf["enterprise_value"]
    assert implied_revenue_growth(ev, 1000, a) == pytest.approx(0.12, abs=1e-6)


def test_implied_margin_round_trip():
    a = assumptions(ebit_margin=(0.31,) * 3)
    ev = value_scenario(1000, a, 0, 1).dcf["enterprise_value"]
    assert implied_ebit_margin(ev, 1000, a) == pytest.approx(0.31, abs=1e-6)


def test_ev_increases_with_margin_and_falls_with_wacc():
    low, high = (value_scenario(1000, assumptions(ebit_margin=(m,) * 3), 0, 1).dcf["enterprise_value"] for m in (0.1, 0.3))
    assert high > low
    cheap, dear = (value_scenario(1000, assumptions(wacc=w), 0, 1).dcf["enterprise_value"] for w in (0.08, 0.12))
    assert cheap > dear


def test_negative_base_fcff_explains_instead_of_solving():
    out = market_expectations(2000, 1000, -50, assumptions())
    assert out["implied_fcff_cagr"] is None
    assert any("not positive" in n for n in out["notes"])


def base_fin():
    return BaseFinancials(1000, "FY", 0.06, 0.2, 0.25, 0.05, 0.07, {})


def test_scenarios_are_ordered_and_probabilities_validated():
    sc = default_scenarios(base_fin())
    res = {k: value_scenario(1000, a, 0, 1) for k, a in sc.items()}
    assert res["bear"].implied_price < res["base"].implied_price < res["bull"].implied_price
    res["bull"] = dataclasses.replace(res["bull"], assumptions=dataclasses.replace(res["bull"].assumptions, probability=0.9))
    with pytest.raises(ValueError):
        probability_weighted_price(res)


def peers_frame(source="https://sec.gov/x"):
    return pd.DataFrame([
        {"ticker": "A", "enterprise_value": 100.0, "market_cap": 80.0, "revenue": 50.0, "ebitda": 10.0, "fcf": 4.0, "net_income": 5.0, "source": source},
        {"ticker": "B", "enterprise_value": 200.0, "market_cap": 150.0, "revenue": 50.0, "ebitda": -5.0, "fcf": 4.0, "net_income": 5.0, "source": source},
    ])


def test_comps_exclude_negative_denominators():
    assert pd.isna(comps_table(peers_frame()).ev_ebitda.iloc[1])


def test_unsourced_comps_are_excluded_from_implied_value():
    out = comps_implied_values(comps_table(peers_frame(source="my spreadsheet")), {"ebitda": 10.0, "revenue": 10.0, "net_income": 1.0}, 0, 1)
    assert out.implied_price.isna().all()


def test_financial_companies_refuse_dcf(tmp_path):
    b = build_bundle("BNK", client=FakeSEC(calendar_company(), submissions(sic="6021")), price_fetcher=fake_prices, output_dir=tmp_path)
    with pytest.raises(ValuationNotApplicable):
        run_valuation(b)


def test_run_valuation_records_assumptions_as_assumed(bundle):
    v = run_valuation(bundle)
    assert v.ledger.get("A.wacc").kind is EvidenceKind.ASSUMED
    assert v.ledger.get("D.value.base").kind is EvidenceKind.DERIVED
    assert "A.wacc" not in bundle.ledger  # the source bundle is not mutated


# --- Thesis Lab ------------------------------------------------------------

def test_claim_count_within_bounds(bundle):
    v = run_valuation(bundle)
    for text in ("vague idea", "growth margin cash capex debt valuation"):
        report = run_thesis_lab(text, bundle, v, extra_claims=("a", "b", "c"))
        assert MIN_CLAIMS <= len(report.claims) <= MAX_CLAIMS


def test_core_claims_always_tested():
    assert {"growth", "valuation", "balance_sheet"} <= set(select_categories("margins will expand"))


def test_every_finding_cites_real_evidence(bundle):
    v = run_valuation(bundle)
    report = run_thesis_lab("growth and valuation", bundle, v)
    findings = [f for c in report.claims for f in c.supporting + c.contradicting] + report.priced_in
    assert findings and all(f.evidence and set(f.evidence) <= v.ledger.ids() for f in findings)


def test_each_claim_has_falsification_and_required_evidence(bundle):
    for claim in run_thesis_lab("growth", bundle, run_valuation(bundle)).claims:
        assert claim.falsified_if and claim.evidence_required


def test_untestable_claim_stays_inconclusive(bundle):
    report = run_thesis_lab("growth", bundle, run_valuation(bundle), extra_claims=("Management is excellent",))
    assert report.claims[-1].status == "inconclusive"


def test_expensive_stock_produces_contradictory_valuation(tmp_path):
    b = build_bundle("FIX", client=FakeSEC(calendar_company(), submissions()), price_fetcher=lambda t: fake_prices(t, 9000.0), output_dir=tmp_path)
    report = run_thesis_lab("valuation", b, run_valuation(b))
    assert next(c for c in report.claims if c.category == "valuation").contradicting


def test_sector_plugin_routing_is_agnostic():
    assert plugin_for_sic("4911").name == "Energy & Power"
    assert plugin_for_sic("3674").name == "Semiconductors"
    assert plugin_for_sic("9999").name == "General"
    assert plugin_for_sic(None).name == "General"


# --- Memo citations --------------------------------------------------------

@pytest.fixture
def small_ledger():
    return EvidenceLedger([EvidenceItem("R.a", "x", 1, EvidenceKind.REPORTED, source="https://sec.gov/x", retrieved_at="t")])


def test_uncited_sentence_fails(small_ledger):
    assert not validate_citations("Revenue grew 10%.", small_ledger).ok


def test_unknown_citation_fails(small_ledger):
    assert validate_citations("Revenue grew 10%. [R.fake]", small_ledger).unknown_ids == ["R.fake"]


def test_judgment_label_passes_and_citation_passes(small_ledger):
    assert validate_citations("Revenue grew. [R.a]\n\nWe like it. [Judgment]", small_ledger).ok


def test_each_sentence_is_checked_separately(small_ledger):
    assert validate_citations("Revenue grew. [R.a] Margins also rose.", small_ledger).uncited == ["Margins also rose."]


def test_uncited_table_row_fails(small_ledger):
    assert not validate_citations("| Scenario | Value |\n|---|---|\n| Base | 10 |", small_ledger).ok


def test_full_memo_passes_validation_and_has_required_sections(bundle):
    v = run_valuation(bundle)
    memo = build_memo(bundle, v, run_thesis_lab("growth", bundle, v))
    assert validate_citations(memo, v.ledger).ok
    for section in ("Recommendation", "Thesis", "Variant Perception", "Valuation", "Catalysts", "Bear Case", "Risks",
                    "Falsification Conditions", "Evidence Ledger", "Model Assumptions Appendix"):
        assert f"## {section}" in memo


def test_memo_without_valuation_still_validates(tmp_path):
    b = build_bundle("BNK", client=FakeSEC(calendar_company(), submissions(sic="6021")), price_fetcher=fake_prices, output_dir=tmp_path)
    report = run_thesis_lab("growth", b, None)
    assert recommendation_for(None, report)[0].startswith("NO RATING")
    assert validate_citations(build_memo(b, None, report), b.ledger).ok


def test_rating_is_watch_when_dcf_and_peers_conflict(tmp_path):
    b = build_bundle("FIX", client=FakeSEC(calendar_company(), submissions()), price_fetcher=lambda t: fake_prices(t, 9000.0), output_dir=tmp_path)
    v = run_valuation(b)
    report = run_thesis_lab("valuation", b, v)
    assert recommendation_for(v, report)[0].startswith("AVOID")
    v.comps_implied = pd.DataFrame([{"method": "ev_ebitda", "peer_median": 10.0, "target_metric": 1.0, "implied_price": 20000.0}])
    assert recommendation_for(v, report)[0].startswith("WATCH")


def test_html_links_citations_and_escapes(bundle):
    v = run_valuation(bundle)
    memo = build_memo(bundle, v, run_thesis_lab("<script>alert(1)</script> growth", bundle, v))
    page = memo_to_html(memo, v.ledger)
    assert "<script>alert" not in page
    assert 'href="#M.price"' in page and 'id="M.price"' in page
    assert "sec.gov/Archives" in page


def test_export_refuses_invalid_memo(bundle, tmp_path, monkeypatch):
    v = run_valuation(bundle)
    report = run_thesis_lab("growth", bundle, v)
    monkeypatch.setattr("investment_os.research.ic_memo.build_memo", lambda *_: "An uncited fact.")
    with pytest.raises(ValueError):
        export_memo(bundle, v, report, tmp_path / "memo")


# --- LLM guardrails --------------------------------------------------------

def test_llm_cannot_add_numbers_or_touch_findings(bundle):
    v = run_valuation(bundle)
    report = run_thesis_lab("growth", bundle, v)
    original = report.claims[0].statement
    findings = list(report.claims[0].supporting)
    _, rejected = apply_claim_rewording(report, {"C1": "Revenue will grow 40% next year."}, v.ledger)
    assert rejected and report.claims[0].statement == original and report.claims[0].supporting == findings


def test_llm_valid_rewording_applies_and_unknown_claim_rejected(bundle):
    v = run_valuation(bundle)
    report = run_thesis_lab("growth", bundle, v)
    _, rejected = apply_claim_rewording(report, {"C1": "Growth will outrun expectations.", "C99": "x"}, v.ledger)
    assert report.claims[0].statement == "Growth will outrun expectations." and len(rejected) == 1


def test_agent_citation_check_flags_fabricated_ids(small_ledger):
    assert unknown_citations("Fact [R.a] and invented [R.zzz].", small_ledger) == ["R.zzz"]
