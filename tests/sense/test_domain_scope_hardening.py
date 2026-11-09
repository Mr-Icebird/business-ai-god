import json
from dataclasses import replace

import pytest

from app.sense.domain.ambiguity.models import AmbiguityType
from app.sense.domain.confidence.models import DomainScopeConfidence
from app.sense.domain.correction.models import (
    CorrectionType,
    DomainScopeCorrection,
    InterpretationUpdate,
)
from app.sense.domain.engine import DomainUnderstandingEngine
from app.sense.domain.models import DomainConfidence, DomainContext, DomainType
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeLevel,
    ScopeType,
)
from app.sense.input.engine import INPUT_SENSE
from app.sense.intent.engine import IntentUnderstandingEngine


def _interpret(previous_text, current_text):
    engine = DomainUnderstandingEngine()
    previous = engine.understand(previous_text)
    current = engine.understand(
        current_text,
        context=DomainContext(previous_result=previous, previous_text=previous_text),
    )
    return previous, current


# 1. Ambiguity


@pytest.mark.parametrize(
    "text",
    [
        "Tell me about oil.",
        "Tell me about gold.",
        "Analyze Apple.",
        "What's happening with the market?",
        "Tell me about the bank.",
        "Research trade.",
        "Research capital.",
        "Research interest.",
        "Research rate.",
        "Tell me about exchange.",
        "Tell me about Amazon.",
    ],
)
def test_generic_terms_preserve_domain_and_scope_candidates(text):
    result = DomainUnderstandingEngine().understand(text)
    assert result.ambiguity.ambiguity_present
    assert result.ambiguity.clarification_required
    assert result.ambiguity.possible_interpretations
    assert result.requires_clarification
    assert result.confidence.overall in {DomainConfidence.LOW, DomainConfidence.UNKNOWN}


@pytest.mark.parametrize(
    "text",
    [
        "Tell me about stock.",
        "Research company.",
        "Tell me about energy.",
        "Tell me about exchange.",
        "Analyze Amazon.",
    ],
)
def test_generic_terms_do_not_receive_high_overall_confidence(text):
    result = DomainUnderstandingEngine().understand(text)
    assert result.confidence.overall != DomainConfidence.HIGH


def test_apple_fruit_stock_is_a_domain_conflict():
    result = DomainUnderstandingEngine().understand("Research Apple fruit stock.")
    assert result.ambiguity.ambiguity_type == AmbiguityType.DOMAIN_CONFLICT
    assert result.ambiguity.conflicting_domains
    assert result.confidence.overall == DomainConfidence.CONFLICTING
    assert result.requires_clarification


def test_valid_multi_domain_request_is_not_automatically_ambiguous():
    result = DomainUnderstandingEngine().understand(
        "How does oil affect airline operating costs?"
    )
    assert len(result.classification.domains) > 1
    assert not result.ambiguity.ambiguity_present
    assert not result.requires_clarification


def test_valid_multi_scope_request_is_not_a_conflict():
    result = DomainUnderstandingEngine().understand(
        "Compare physical gold with gold futures."
    )
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.FINANCIAL_MARKET in scopes
    assert result.ambiguity.ambiguity_type == AmbiguityType.NONE
    assert not result.requires_clarification


def test_contextless_reference_requires_clarification():
    result = DomainUnderstandingEngine().understand("How does this affect the market?")
    assert result.ambiguity.ambiguity_type == AmbiguityType.INSUFFICIENT_CONTEXT
    assert result.requires_clarification


# 2. Confidence


def test_domain_and_scope_confidence_are_independent_and_evidence_based():
    clear = DomainUnderstandingEngine().understand("Analyze EURUSD.")
    ambiguous = DomainUnderstandingEngine().understand("Tell me about oil.")
    assert isinstance(clear.confidence, DomainScopeConfidence)
    assert clear.confidence.domain == DomainConfidence.HIGH
    assert clear.confidence.scope == DomainConfidence.HIGH
    assert ambiguous.confidence.domain == DomainConfidence.LOW
    assert ambiguous.confidence.scope == DomainConfidence.LOW


def test_confidence_is_unknown_without_domain_or_scope_evidence():
    result = DomainUnderstandingEngine().understand("A pleasant afternoon.")
    assert result.confidence.domain == DomainConfidence.UNKNOWN
    assert result.confidence.scope == DomainConfidence.UNKNOWN
    assert result.confidence.overall == DomainConfidence.UNKNOWN


def test_conflicting_evidence_produces_conflicting_confidence():
    result = DomainUnderstandingEngine().understand("Research Apple fruit stock.")
    assert result.confidence.domain == DomainConfidence.CONFLICTING
    assert result.confidence.scope != DomainConfidence.CONFLICTING
    assert result.confidence.overall == DomainConfidence.CONFLICTING


# 3. Corrections


def test_company_to_stock_correction_adds_market_scope_and_preserves_company():
    previous, updated = _interpret("Research Apple.", "I mean Apple stock.")
    assert updated.correction.detected
    assert updated.correction.correction_type in {
        CorrectionType.SCOPE_REFINEMENT,
        CorrectionType.INTERPRETATION_REPLACEMENT,
    }
    scopes = {
        updated.scope_classification.primary_scope,
        *updated.scope_classification.secondary_scopes,
    }
    assert ScopeType.COMPANY in scopes
    assert ScopeType.FINANCIAL_MARKET in scopes
    assert "company" in updated.correction.preserved_context
    assert previous.scope_classification.primary_scope == ScopeType.COMPANY


def test_oil_scope_correction_replaces_financial_context_with_physical_commerce():
    previous, updated = _interpret(
        "Research oil futures.", "I mean physical oil supply."
    )
    scopes = {
        updated.scope_classification.primary_scope,
        *updated.scope_classification.secondary_scopes,
    }
    assert updated.correction.detected
    assert updated.correction.correction_type in {
        CorrectionType.SCOPE_REPLACEMENT,
        CorrectionType.INTERPRETATION_REPLACEMENT,
    }
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes
    assert previous.scope_classification.primary_scope == ScopeType.FINANCIAL_MARKET


def test_gold_futures_correction_adds_supported_market_scope():
    previous, updated = _interpret("Research gold.", "I mean gold futures.")
    scopes = {
        updated.scope_classification.primary_scope,
        *updated.scope_classification.secondary_scopes,
    }
    assert updated.correction.detected
    assert ScopeType.FINANCIAL_MARKET in scopes
    assert ScopeType.ASSET in scopes
    assert previous.scope_classification.primary_scope == ScopeType.ASSET
    assert updated.confidence.domain == previous.confidence.domain
    assert updated.confidence.scope != previous.confidence.scope


def test_company_to_its_stock_correction_preserves_company_and_adds_equity_scope():
    previous, updated = _interpret("Analyze the company.", "I mean its stock.")
    scopes = {
        updated.scope_classification.primary_scope,
        *updated.scope_classification.secondary_scopes,
    }
    assert updated.correction.detected
    assert ScopeType.COMPANY in scopes
    assert ScopeType.FINANCIAL_MARKET in scopes
    assert updated.correction.preserved_context


def test_correction_without_previous_context_is_not_applied():
    result = DomainUnderstandingEngine().understand("I mean gold futures.")
    assert not result.correction.detected


def test_unrelated_actuality_sentence_is_not_a_correction():
    _, result = _interpret("Research oil futures.", "Actually, the weather is warm.")
    assert not result.correction.detected


def test_correction_of_correction_updates_active_scope():
    engine = DomainUnderstandingEngine()
    first = engine.understand("Research oil.")
    second = engine.understand(
        "I mean oil futures.", context=DomainContext(previous_result=first)
    )
    third = engine.understand(
        "I mean physical oil supply.", context=DomainContext(previous_result=second)
    )
    scopes = {
        third.scope_classification.primary_scope,
        *third.scope_classification.secondary_scopes,
    }
    assert third.correction.detected
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes
    assert len(third.correction.history) == 2
    assert third.correction.history[0].evidence == "I mean oil futures."


def test_physical_oil_correction_preserves_evidence_and_history():
    engine = DomainUnderstandingEngine()
    previous = engine.understand("Research oil futures.")
    corrected = engine.understand(
        "I mean physical oil supply.",
        context=DomainContext(previous_result=previous),
    )

    assert corrected.correction.detected
    assert corrected.correction.evidence == "I mean physical oil supply."
    assert corrected.correction.previous_scope_evidence == tuple(
        (
            replace(item, provenance=EvidenceProvenance.HISTORICAL)
            if item.provenance != EvidenceProvenance.INTERNAL_TAXONOMY
            else item
        )
        for item in previous.scope_detection.evidence
    )
    assert corrected.correction.updated_scope_evidence
    assert corrected.correction.history[-1].previous_domain_evidence == tuple(
        (
            replace(item, provenance=EvidenceProvenance.HISTORICAL)
            if item.provenance != EvidenceProvenance.INTERNAL_TAXONOMY
            else item
        )
        for item in previous.detection.signals
    )
    assert corrected.detection.signals
    assert corrected.confidence.scope == DomainConfidence.HIGH
    assert ScopeType.PHYSICAL_COMMERCE in {
        corrected.scope_type,
        *corrected.scope_classification.secondary_scopes,
    }
    assert ScopeType.FINANCIAL_MARKET not in {
        corrected.scope_type,
        *corrected.scope_classification.secondary_scopes,
    }
    assert ScopeLevel.MARKET not in corrected.scope_classification.scope_levels
    assert ScopeLevel.TRANSACTION not in corrected.scope_classification.scope_levels
    assert "futures" not in corrected.scope_classification.scope_subjects


def test_domain_correction_preserves_unaffected_scope_confidence():
    previous = DomainUnderstandingEngine().understand("Research Apple.")
    correction = DomainScopeCorrection(
        detected=True,
        correction_type=CorrectionType.DOMAIN_REFINEMENT,
        updates=(
            InterpretationUpdate(
                "domains", "", "markets, equities", "I mean Apple stock"
            ),
        ),
        previous_domains=previous.classification.domains,
        updated_domains=(DomainType.MARKETS, DomainType.EQUITIES),
        previous_scopes=(
            previous.scope_classification.primary_scope,
            *previous.scope_classification.secondary_scopes,
        ),
        previous_domain_evidence=previous.detection.signals,
        previous_scope_evidence=previous.scope_detection.evidence,
        previous_domain_confidence=previous.confidence.domain,
        previous_scope_confidence=previous.confidence.scope,
    )

    class FixedCorrectionDetector:
        def detect(self, text, current, context):
            return correction

    updated = DomainUnderstandingEngine(
        correction_detector=FixedCorrectionDetector()
    ).understand(
        "I mean Apple stock.",
        context=DomainContext(previous_result=previous),
    )

    assert updated.confidence.domain == DomainConfidence.HIGH
    assert updated.confidence.scope == previous.confidence.scope
    assert (
        updated.scope_classification.primary_scope
        == previous.scope_classification.primary_scope
    )
    assert (
        updated.scope_classification.secondary_scopes
        == previous.scope_classification.secondary_scopes
    )
    assert all(
        item.provenance == EvidenceProvenance.UPSTREAM_CONTEXT
        for item in updated.scope_classification.boundaries
        if item.provenance != EvidenceProvenance.INTERNAL_TAXONOMY
    )


def test_unrelated_entity_does_not_inherit_previous_correction():
    _, updated = _interpret(
        "Research oil futures.",
        "Actually, Google shares are up.",
    )

    assert not updated.correction.detected
    assert not updated.correction.history
    assert DomainType.EQUITIES in updated.classification.domains


def test_ambiguous_entityless_correction_is_not_applied():
    engine = DomainUnderstandingEngine()
    previous = engine.understand("Research Apple.")
    updated = engine.understand(
        "I mean stock.",
        context=DomainContext(previous_result=previous),
    )

    assert not updated.correction.detected
    assert not any(
        item.source == "previous_scope_context"
        for item in updated.scope_detection.evidence
    )


def test_correction_preserves_unrelated_multi_domain_and_scope_context():
    engine = DomainUnderstandingEngine()
    previous = engine.understand(
        "Research oil futures and airline logistics in Nigeria."
    )
    updated = engine.understand(
        "I mean physical oil supply.",
        context=DomainContext(previous_result=previous),
    )

    assert updated.correction.detected
    assert DomainType.OPERATIONS in updated.classification.domains
    scopes = {
        updated.scope_classification.primary_scope,
        *updated.scope_classification.secondary_scopes,
    }
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.GEOGRAPHIC in scopes
    assert ScopeType.OPERATIONAL in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes
    assert ScopeLevel.COUNTRY in updated.scope_classification.scope_levels
    assert ScopeLevel.TRANSACTION not in updated.scope_classification.scope_levels
    assert "futures" not in updated.scope_classification.scope_subjects


# 4. Output Contract


def test_final_result_exposes_required_domain_scope_part3_fields():
    result = DomainUnderstandingEngine().understand("Analyze EURUSD.")
    payload = result.to_dict()
    required = {
        "primary_domain",
        "secondary_domains",
        "subdomains",
        "domain_hierarchy",
        "domain_relationships",
        "scope",
        "scope_type",
        "scope_level",
        "scope_context",
        "ambiguity",
        "confidence",
        "correction",
        "requires_clarification",
        "explanation",
        "evidence",
        "source_signals",
    }
    assert required.issubset(payload)
    assert result.ambiguity is not None
    assert result.confidence is not None
    assert result.correction is not None
    assert result.explanation


def test_final_contract_is_json_compatible_and_keeps_upstream_results():
    source = INPUT_SENSE.understand("Analyze EURUSD at $1.08 in 2025")
    sense2 = IntentUnderstandingEngine().understand(source)
    result = DomainUnderstandingEngine().understand(sense2)
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["source_input"]["raw_input"] == source.raw_input
    assert payload["source_sense2"]["raw_text"] == sense2.raw_text
    assert payload["confidence"]["domain"] == "high"
    assert payload["corrections"] == payload["correction"]
    assert payload["scope_context"] == result.to_dict()["scope_context"]


# 5. SENSE-1 Integration


def test_sense1_market_input_and_dates_reach_part3_contract():
    source = INPUT_SENSE.understand("Gold futures in 2025", input_type="market_data")
    result = DomainUnderstandingEngine().understand(source)
    assert result.source_input is source
    assert result.scope_context.contexts
    assert result.confidence.scope != DomainConfidence.UNKNOWN


# 6. SENSE-2 Integration


def test_sense2_context_and_constraints_reach_final_scope_contract():
    sense2 = IntentUnderstandingEngine().understand(
        "Research Nigerian inflation in 2025."
    )
    result = DomainUnderstandingEngine().understand(sense2)
    assert result.source_sense2 is sense2
    assert result.scope_context.contexts
    assert result.confidence.domain != DomainConfidence.UNKNOWN


# 7. Domain + Scope Integration


def test_market_asset_and_domain_hierarchy_remain_in_final_result():
    result = DomainUnderstandingEngine().understand("Analyze EURUSD.")
    assert DomainType.MARKETS in result.classification.domains
    assert ScopeType.FINANCIAL_MARKET in {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert result.domain_hierarchy.nodes
    assert result.domain_relationships


# 8. Multi-Domain


def test_multidomain_does_not_imply_ambiguity_or_low_confidence():
    result = DomainUnderstandingEngine().understand(
        "How does higher oil prices affect transportation costs?"
    )
    assert len(result.classification.domains) > 1
    assert result.confidence.domain in {DomainConfidence.HIGH, DomainConfidence.MEDIUM}
    assert result.ambiguity.ambiguity_type == AmbiguityType.NONE


@pytest.mark.parametrize(
    ("text", "required_domains"),
    [
        (
            "How does oil affect inflation?",
            {DomainType.COMMODITIES, DomainType.ENERGY, DomainType.ECONOMICS},
        ),
        (
            "How does oil affect airline costs?",
            {DomainType.COMMODITIES, DomainType.ENERGY},
        ),
        (
            "How do interest rates affect the housing market?",
            {DomainType.ECONOMICS, DomainType.REAL_ESTATE},
        ),
        (
            "How does Nigerian regulation affect banks?",
            {DomainType.REGULATION, DomainType.BANKING},
        ),
        (
            "How does a weaker currency affect import costs?",
            {DomainType.FOREX, DomainType.ECONOMICS, DomainType.BUSINESS},
        ),
    ],
)
def test_contextual_multi_domain_requests_are_not_ambiguous(text, required_domains):
    result = DomainUnderstandingEngine().understand(text)
    assert required_domains.issubset(result.classification.domains)
    assert not result.ambiguity.ambiguity_present
    assert not result.requires_clarification


@pytest.mark.parametrize(
    "text",
    [
        "How does oil production affect oil prices?",
        "How does Apple's business affect its stock?",
        "How does regulation affect the banking industry?",
        "How does Nigerian inflation affect businesses?",
    ],
)
def test_contextual_multi_scope_requests_preserve_connected_scopes(text):
    result = DomainUnderstandingEngine().understand(text)
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert len(scopes - {ScopeType.CROSS_DOMAIN}) > 1
    assert not result.ambiguity.ambiguity_present


# 9. Multi-Scope


def test_multiple_scopes_are_not_classified_as_scope_conflict():
    result = DomainUnderstandingEngine().understand(
        "Compare physical gold with gold futures."
    )
    assert not result.ambiguity.ambiguity_present
    assert result.confidence.scope != DomainConfidence.CONFLICTING


# 10. False Positives


def test_negative_or_different_context_terms_are_not_conflicts():
    engine = DomainUnderstandingEngine()
    not_equity = engine.understand("The company has a stockroom.")
    distinct_scopes = engine.understand(
        "Compare the physical oil supply with oil futures."
    )
    local_bank = engine.understand("I went to the bank.")
    local_market = engine.understand("The market near my house is busy.")
    sold_oil = engine.understand("The company sells oil.")
    farmer_trade = engine.understand("The farmer trades wheat.")

    assert not not_equity.ambiguity.ambiguity_present
    assert distinct_scopes.ambiguity.ambiguity_type == AmbiguityType.NONE
    for result in (local_bank, local_market, not_equity, sold_oil, farmer_trade):
        assert ScopeType.FINANCIAL_MARKET not in {
            result.scope_classification.primary_scope,
            *result.scope_classification.secondary_scopes,
        }


# 11. Serialization


def test_nested_ambiguity_confidence_correction_and_evidence_serialize():
    result = DomainUnderstandingEngine().understand("Tell me about oil.")
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["ambiguity"]["possible_domains"]
    assert payload["confidence"]["scope"] in {"low", "unknown"}
    assert payload["evidence"]["domain"] is not None
    assert payload["evidence"]["scope"] is not None


# 12. Regression


def test_sense1_sense2_and_part1_part2_outputs_survive_part3_integration():
    source = INPUT_SENSE.understand("Research gold futures at $2,500 in 2025")
    sense2 = IntentUnderstandingEngine().understand(source)
    result = DomainUnderstandingEngine().understand(sense2)
    assert result.source_input is source
    assert result.source_sense2 is sense2
    assert result.detection.candidates
    assert result.multi_domain.domains
    assert result.scope_detection.evidence
    assert result.scope_context.contexts
