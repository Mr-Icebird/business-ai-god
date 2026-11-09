import json

import pytest

from app.sense.domain.classification.classifier import DomainClassifier
from app.sense.domain.detection.detector import DomainDetector
from app.sense.domain.hierarchy.resolver import DomainHierarchyResolver
from app.sense.domain.models import DomainConfidence, DomainContext, DomainType
from app.sense.domain.multi_domain.models import DomainRelationshipType
from app.sense.domain.engine import DomainUnderstandingEngine
from app.sense.input.engine import INPUT_SENSE
from app.sense.intent.engine import IntentUnderstandingEngine

EXPECTED_TAXONOMY = {
    "business",
    "finance",
    "markets",
    "economics",
    "trading",
    "accounting",
    "banking",
    "investment",
    "commodities",
    "forex",
    "crypto",
    "equities",
    "bonds",
    "macroeconomics",
    "microeconomics",
    "energy",
    "agriculture",
    "real_estate",
    "technology",
    "geopolitics",
    "regulation",
    "tax",
    "operations",
    "marketing",
    "sales",
    "supply_chain",
}


def test_taxonomy_contains_only_authoritative_domains():
    assert {
        item.value for item in DomainType if item != DomainType.UNKNOWN
    } == EXPECTED_TAXONOMY


@pytest.mark.parametrize(
    ("text", "primary", "required_domains"),
    [
        ("Why did gold fall today?", DomainType.MARKETS, {DomainType.COMMODITIES}),
        (
            "Why did inflation increase?",
            DomainType.ECONOMICS,
            {DomainType.MACROECONOMICS},
        ),
        ("Analyze EURUSD.", DomainType.MARKETS, {DomainType.FOREX, DomainType.TRADING}),
        ("How much revenue did Apple make?", DomainType.BUSINESS, {DomainType.FINANCE}),
        ("Check the banking sector.", DomainType.FINANCE, {DomainType.BANKING}),
        (
            "How does higher oil prices affect transportation costs and logistics companies?",
            DomainType.MARKETS,
            {
                DomainType.ENERGY,
                DomainType.COMMODITIES,
                DomainType.ECONOMICS,
                DomainType.BUSINESS,
                DomainType.OPERATIONS,
                DomainType.SUPPLY_CHAIN,
            },
        ),
        (
            "Compare Bitcoin and gold.",
            DomainType.MARKETS,
            {DomainType.CRYPTO, DomainType.COMMODITIES},
        ),
        (
            "I want to understand how interest rates affect housing.",
            DomainType.ECONOMICS,
            {DomainType.REAL_ESTATE},
        ),
        (
            "How will a weaker naira affect importers?",
            DomainType.FOREX,
            {DomainType.ECONOMICS, DomainType.BUSINESS},
        ),
    ],
)
def test_domain_classification_preserves_primary_and_secondary_domains(
    text, primary, required_domains
):
    result = DomainUnderstandingEngine().understand(text)
    assert result.primary_domain == primary
    assert required_domains.issubset(set(result.classification.domains))


def test_detector_classification_hierarchy_and_multi_domain_are_independent():
    detector = DomainDetector()
    detection = detector.detect("Why did gold fall today?")
    classification = DomainClassifier().classify(detection)
    hierarchy = DomainHierarchyResolver().resolve(classification.domains)
    assert detection.candidates
    assert classification.primary_domain == DomainType.MARKETS
    assert DomainType.COMMODITIES in classification.subdomains
    assert hierarchy.node_for(DomainType.COMMODITIES).parent == DomainType.MARKETS
    assert hierarchy.node_for(DomainType.COMMODITIES).ancestors == (
        DomainType.MARKETS,
        DomainType.FINANCE,
    )


def test_asset_event_question_is_markets_and_commodity_not_generic_commodity_only():
    result = DomainUnderstandingEngine().understand("What is happening with gold?")
    assert result.primary_domain == DomainType.MARKETS
    assert DomainType.COMMODITIES in result.subdomains


def test_hierarchy_resolver_supports_parent_child_and_grandchild_paths():
    resolver = DomainHierarchyResolver()
    assert resolver.parent_of(DomainType.MARKETS) == DomainType.FINANCE
    assert resolver.parent_of(DomainType.ENERGY) == DomainType.COMMODITIES
    assert resolver.ancestors(DomainType.ENERGY) == (
        DomainType.COMMODITIES,
        DomainType.MARKETS,
        DomainType.FINANCE,
    )
    assert DomainType.ENERGY in resolver.descendants(DomainType.MARKETS)


def test_oil_without_context_preserves_ambiguity_and_candidates():
    result = DomainUnderstandingEngine().understand("Tell me about oil.")
    assert result.detection.is_ambiguous
    assert result.multi_domain.is_ambiguous
    assert result.classification.confidence == DomainConfidence.LOW
    assert result.primary_domain == DomainType.UNKNOWN
    assert {DomainType.ENERGY, DomainType.COMMODITIES}.issubset(
        set(result.multi_domain.candidate_domains)
    )


def test_apple_alone_is_not_assumed_to_be_a_technology_company():
    result = DomainUnderstandingEngine().understand("Apple")
    assert result.detection.is_ambiguous
    assert result.classification.confidence == DomainConfidence.LOW
    assert result.primary_domain == DomainType.UNKNOWN
    assert {
        DomainType.BUSINESS,
        DomainType.TECHNOLOGY,
        DomainType.AGRICULTURE,
    }.issubset(set(result.multi_domain.candidate_domains))


def test_fruit_context_resolves_apple_away_from_technology_and_business():
    result = DomainUnderstandingEngine().understand("The apple harvest was excellent.")
    assert result.primary_domain == DomainType.AGRICULTURE
    assert DomainType.TECHNOLOGY not in result.classification.domains
    assert DomainType.BUSINESS not in result.classification.domains


def test_bank_and_market_terms_are_not_automatically_financial():
    detector = DomainDetector()
    river_bank = detector.detect("They sat on the river bank.")
    physical_market = detector.detect("The local market sells fresh produce.")
    assert DomainType.BANKING not in {item.domain for item in river_bank.candidates}
    assert physical_market.is_ambiguous
    assert all(
        item.confidence != DomainConfidence.HIGH for item in physical_market.candidates
    )


def test_trade_as_international_commerce_is_not_automatically_trading():
    result = DomainUnderstandingEngine().understand(
        "The countries trade agricultural goods."
    )
    assert DomainType.TRADING not in result.classification.domains
    assert DomainType.AGRICULTURE in result.classification.domains


def test_multi_domain_relationships_distinguish_hierarchy_and_interaction():
    result = DomainUnderstandingEngine().understand(
        "How would higher oil prices affect Nigerian inflation and logistics costs?"
    )
    relations = result.multi_domain.relationships
    assert any(
        item.relationship_type == DomainRelationshipType.HIERARCHICAL
        for item in relations
    )
    assert any(
        item.relationship_type == DomainRelationshipType.INTERACTS_WITH
        for item in relations
    )
    assert result.multi_domain.interactions
    assert result.multi_domain.primary_domain == result.primary_domain


def test_structured_sense1_market_input_is_consumed_and_preserved():
    source = INPUT_SENSE.understand("Gold chart received", input_type="market_data")
    result = DomainUnderstandingEngine().understand(source)
    assert result.source_input is source
    assert DomainType.MARKETS in result.classification.domains
    assert any(
        signal.source == "sense1_input_type" for signal in result.detection.signals
    )


def test_sense1_currency_and_abbreviation_signals_are_reused():
    source = INPUT_SENSE.understand("BTC traded at $60,000")
    result = DomainUnderstandingEngine().understand(source)
    assert result.source_input is source
    assert DomainType.CRYPTO in result.classification.domains
    assert DomainType.FINANCE in result.classification.domains
    assert any(
        signal.source == "sense1_currency" for signal in result.detection.signals
    )


def test_sense2_task_and_action_context_enrich_domain_result():
    engine = IntentUnderstandingEngine()
    source = engine.understand("Execute this trade.")
    result = DomainUnderstandingEngine().understand(
        "Execute this trade.", sense2_result=source
    )
    assert result.source_sense2 is source
    assert DomainType.TRADING in result.classification.domains
    assert any(signal.source == "sense2_action" for signal in result.detection.signals)


def test_contextual_pronoun_reuses_prior_domain_classification():
    engine = DomainUnderstandingEngine()
    previous = engine.understand("Research gold prices.")
    result = engine.understand(
        "Why did it fall?", context=DomainContext(previous_result=previous)
    )
    assert set(previous.classification.domains).issubset(result.classification.domains)
    assert any(
        signal.source == "previous_domain_context"
        for signal in result.detection.signals
    )


def test_contextual_pronoun_can_use_previous_sense2_or_sense1_context():
    sense2 = IntentUnderstandingEngine().understand("Research gold prices.")
    from_sense2 = DomainUnderstandingEngine().understand(
        "Why did it fall?", context=DomainContext(previous_sense2=sense2)
    )
    previous_input = INPUT_SENSE.understand("Gold price data received")
    from_sense1 = DomainUnderstandingEngine().understand(
        "Why did it fall?", context=DomainContext(previous_input=previous_input)
    )
    assert DomainType.COMMODITIES in from_sense2.classification.domains
    assert DomainType.MARKETS in from_sense1.classification.candidate_domains
    assert from_sense1.detection.is_ambiguous
    assert any(
        signal.source == "previous_upstream_context"
        for signal in from_sense2.detection.signals
    )


def test_empty_and_unknown_input_returns_unknown_with_unknown_confidence():
    engine = DomainUnderstandingEngine()
    empty = engine.understand("")
    unknown = engine.understand("A pleasant afternoon.")
    assert empty.primary_domain == DomainType.UNKNOWN
    assert empty.classification.confidence == DomainConfidence.UNKNOWN
    assert unknown.primary_domain == DomainType.UNKNOWN


def test_domain_output_serializes_to_json_and_retains_structured_fields():
    result = DomainUnderstandingEngine().understand("Analyze EURUSD.")
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["classification"]["primary_domain"] == "markets"
    assert "forex" in payload["multi_domain"]["domains"]
    assert payload["hierarchy"]["nodes"]


def test_irrelevant_currency_amount_does_not_invent_markets():
    source = INPUT_SENSE.understand("I paid $20 for lunch.")
    result = DomainUnderstandingEngine().understand(source)
    assert DomainType.MARKETS not in result.classification.domains
    assert DomainType.FINANCE in result.classification.domains
