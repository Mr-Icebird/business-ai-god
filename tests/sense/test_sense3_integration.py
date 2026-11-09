import json

from app.sense.domain.models import DomainContext, DomainType
from app.sense.domain.scope.models import ScopeType
from app.sense.engine import SenseEngine
from app.sense.models import ConversationEvent, IntentType


def test_normal_business_request_reaches_sense3_with_upstream_results():
    result = SenseEngine().understand("How much revenue did Apple make?")

    assert result.domain_sense is not None
    assert result.input_sense is result.domain_sense.source_input
    assert result.intent_sense is result.domain_sense.source_sense2
    assert result.domain_sense.raw_text == "How much revenue did Apple make?"
    assert DomainType.BUSINESS in result.domain_sense.classification.domains


def test_forex_request_has_domain_and_scope_interpretation():
    result = SenseEngine().understand("Analyze EURUSD.")

    assert result.domain_sense is not None
    assert DomainType.FOREX in result.domain_sense.classification.domains
    assert result.domain_sense.scope_type == ScopeType.FINANCIAL_MARKET


def test_physical_oil_supply_is_not_classified_as_financial_market():
    request = "How much crude oil does Nigeria produce?"
    result = SenseEngine().understand(request)
    domain_result = result.domain_sense

    assert domain_result is not None
    scopes = {
        domain_result.scope_type,
        *domain_result.scope_classification.secondary_scopes,
    }
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes


def test_multi_domain_request_preserves_domain_relationships():
    result = SenseEngine().understand(
        "How does higher oil prices affect transportation costs and "
        "logistics companies?"
    )
    domain_result = result.domain_sense

    assert domain_result is not None
    assert {
        DomainType.ENERGY,
        DomainType.ECONOMICS,
        DomainType.BUSINESS,
        DomainType.OPERATIONS,
        DomainType.SUPPLY_CHAIN,
    }.issubset(set(domain_result.classification.domains))
    assert domain_result.domain_relationships
    assert domain_result.multi_domain.interactions


def test_correction_uses_explicit_previous_domain_interpretation():
    engine = SenseEngine()
    previous = engine.understand("Research oil futures.")

    corrected = engine.understand(
        "I mean physical oil supply.",
        domain_context=DomainContext(previous_result=previous.domain_sense),
    )
    domain_result = corrected.domain_sense

    assert domain_result is not None
    assert domain_result.correction.detected
    assert domain_result.correction.evidence == "I mean physical oil supply."
    assert domain_result.confidence is not None
    assert ScopeType.PHYSICAL_COMMERCE in {
        domain_result.scope_type,
        *domain_result.scope_classification.secondary_scopes,
    }
    assert ScopeType.FINANCIAL_MARKET not in {
        domain_result.scope_type,
        *domain_result.scope_classification.secondary_scopes,
    }


def test_owner_corrections_flow_through_top_level_sense_engine():
    engine = SenseEngine()
    scenarios = (
        ("Research Apple.", "I mean Apple stock.", DomainType.EQUITIES, None),
        (
            "Research oil futures.",
            "I mean physical oil supply.",
            None,
            ScopeType.PHYSICAL_COMMERCE,
        ),
        (
            "Research gold.",
            "I mean gold futures.",
            None,
            ScopeType.FINANCIAL_MARKET,
        ),
    )

    for previous_text, correction_text, expected_domain, expected_scope in scenarios:
        previous = engine.understand(previous_text)
        corrected = engine.understand(correction_text, previous_result=previous)
        domain_result = corrected.domain_sense
        assert domain_result is not None
        assert domain_result.correction.detected
        assert domain_result.correction.evidence == correction_text
        if expected_domain is not None:
            assert expected_domain in domain_result.classification.domains
        if expected_scope is not None:
            scopes = {
                domain_result.scope_type,
                *domain_result.scope_classification.secondary_scopes,
            }
            assert expected_scope in scopes
            if expected_scope == ScopeType.PHYSICAL_COMMERCE:
                assert ScopeType.FINANCIAL_MARKET not in scopes


def test_request_without_previous_context_runs_without_inventing_context():
    result = SenseEngine().understand("I mean oil futures.")

    assert result.domain_sense is not None
    assert result.domain_sense.correction is not None
    assert not result.domain_sense.correction.detected
    assert not any(
        signal.source == "previous_domain_context"
        for signal in result.domain_sense.detection.signals
    )


def test_existing_sense1_sense2_and_legacy_outputs_are_preserved():
    result = SenseEngine().understand("Research gold today at $3,500.")

    assert result.intent == IntentType.RESEARCH
    assert result.message == "Research gold today at $3,500."
    assert "gold" in result.entities
    assert result.conversation_event == ConversationEvent.NONE
    assert result.input_sense.raw_input == result.message
    assert result.intent_sense.source_input is result.input_sense
    sense1_normalized = result.input_sense.normalized_text
    assert result.intent_sense.normalized_text == sense1_normalized
    assert result.domain_sense.source_input is result.input_sense
    assert result.domain_sense.source_sense2 is result.intent_sense

    payload = result.to_dict()
    json.dumps(payload)
    assert payload["domain_sense"]["evidence"]["domain"]
    assert payload["domain_sense"]["confidence"] is not None
