import json

import pytest

from app.sense.domain.ambiguity.models import AmbiguityType
from app.sense.domain.engine import DomainUnderstandingEngine
from app.sense.domain.models import DomainType
from app.sense.domain.multi_domain.models import DomainRelationshipType
from app.sense.domain.scope.models import ScopeType
from app.sense.engine import SenseEngine

_DOMAIN_CASES = (
    (
        "Analyze how rising oil prices affect airline operating costs.",
        {
            DomainType.COMMODITIES,
            DomainType.ECONOMICS,
            DomainType.ENERGY,
            DomainType.OPERATIONS,
        },
    ),
    (
        "Explain how interest rates affect housing markets.",
        {DomainType.ECONOMICS, DomainType.REAL_ESTATE},
    ),
    (
        "Analyze how currency depreciation increases import costs.",
        {DomainType.ACCOUNTING, DomainType.ECONOMICS, DomainType.BUSINESS},
    ),
    (
        "Research how agricultural production affects food inflation.",
        {DomainType.AGRICULTURE, DomainType.ECONOMICS},
    ),
    (
        "Explain how energy prices affect manufacturing.",
        {DomainType.ENERGY, DomainType.OPERATIONS},
    ),
)

_SCOPE_CASES = (
    (
        "Analyze how Nigerian inflation affects businesses.",
        {ScopeType.GEOGRAPHIC, ScopeType.ECONOMIC, ScopeType.BUSINESS},
    ),
    (
        "Research how foreign exchange restrictions affect import transactions.",
        {
            ScopeType.FINANCIAL_MARKET,
            ScopeType.ECONOMIC,
            ScopeType.BUSINESS,
        },
    ),
    (
        "Analyze how regulation affects Nigerian commercial banks.",
        {ScopeType.REGULATORY, ScopeType.GEOGRAPHIC},
    ),
    (
        "Explain how gold mining affects local employment.",
        {ScopeType.PHYSICAL_COMMERCE, ScopeType.ASSET},
    ),
    (
        "Analyze how a company's operations affect its profitability.",
        {ScopeType.COMPANY, ScopeType.OPERATIONAL, ScopeType.BUSINESS},
    ),
)


@pytest.mark.parametrize(("text", "expected_domains"), _DOMAIN_CASES)
def test_related_domain_requests_keep_supported_relationships(text, expected_domains):
    result = DomainUnderstandingEngine().understand(text)

    assert expected_domains.issubset(set(result.classification.domains))
    assert not result.ambiguity.ambiguity_present
    assert not result.multi_domain.is_ambiguous
    assert result.multi_domain.interactions
    assert any(
        item.relationship_type == DomainRelationshipType.INTERACTS_WITH
        and item.evidence
        for item in result.multi_domain.relationships
    )


@pytest.mark.parametrize(("text", "expected_scopes"), _SCOPE_CASES)
def test_related_scope_requests_preserve_scopes_and_evidence(text, expected_scopes):
    result = DomainUnderstandingEngine().understand(text)
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }

    assert expected_scopes.issubset(scopes)
    assert not result.ambiguity.ambiguity_present
    assert result.scope_detection.evidence
    assert all(
        relationship.evidence
        for relationship in result.scope_classification.relationships
    )


def test_scope_relationships_keep_subject_associations():
    result = DomainUnderstandingEngine().understand(
        "Analyze how a company's operations affect its profitability."
    )

    assert any(
        relationship.target_scope == ScopeType.COMPANY
        and relationship.target_subject == "company"
        for relationship in result.scope_classification.relationships
    )


@pytest.mark.parametrize(
    ("text", "expected_scopes", "excluded_scopes"),
    [
        (
            "Research physical oil supply.",
            {ScopeType.PHYSICAL_COMMERCE, ScopeType.ASSET},
            {ScopeType.FINANCIAL_MARKET},
        ),
        (
            "Analyze oil futures.",
            {ScopeType.FINANCIAL_MARKET, ScopeType.ASSET},
            {ScopeType.PHYSICAL_COMMERCE},
        ),
        (
            "Compare physical gold with gold futures.",
            {
                ScopeType.PHYSICAL_COMMERCE,
                ScopeType.FINANCIAL_MARKET,
                ScopeType.ASSET,
            },
            set(),
        ),
        (
            "Research gold mining.",
            {ScopeType.PHYSICAL_COMMERCE, ScopeType.ASSET},
            {ScopeType.FINANCIAL_MARKET},
        ),
    ],
)
def test_asset_scope_respects_physical_and_financial_cues(
    text, expected_scopes, excluded_scopes
):
    result = DomainUnderstandingEngine().understand(text)
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }

    assert expected_scopes.issubset(scopes)
    assert not excluded_scopes.intersection(scopes)
    assert not result.ambiguity.ambiguity_present


def test_crude_oil_prices_preserve_unresolved_scope_alternatives():
    result = DomainUnderstandingEngine().understand("Analyze crude oil prices.")

    assert result.ambiguity.scope_ambiguity_type == AmbiguityType.MULTI_SCOPE_UNCLEAR
    assert {
        ScopeType.FINANCIAL_MARKET,
        ScopeType.PHYSICAL_COMMERCE,
    }.issubset(set(result.ambiguity.possible_scopes))
    assert ScopeType.ASSET in {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }


@pytest.mark.parametrize(
    "text",
    [
        "Analyze Apple.",
        "Research Amazon.",
        "Research the bank.",
        "Research stock.",
        "Research interest.",
        "Research rate.",
        "Research exchange.",
        "Research capital.",
        "Analyze the market.",
        "Research energy.",
    ],
)
def test_short_generic_terms_keep_scope_alternatives(text):
    result = DomainUnderstandingEngine().understand(text)

    assert result.ambiguity.ambiguity_present
    assert result.ambiguity.clarification_required
    assert result.ambiguity.possible_scopes
    assert result.ambiguity.evidence
    assert result.ambiguity.possible_interpretations


@pytest.mark.parametrize(
    "text",
    [
        "Research Apple stock.",
        "Research Amazon AWS cloud services.",
        "Research commercial bank lending.",
        "Explain how interest rates affect housing markets.",
        "Research how foreign exchange restrictions affect import transactions.",
        "Analyze capital allocation for investment.",
        "Analyze housing market trends.",
        "Explain how energy prices affect manufacturing.",
    ],
)
def test_contextual_cues_resolve_generic_terms(text):
    result = DomainUnderstandingEngine().understand(text)

    assert not result.ambiguity.ambiguity_present
    assert not result.multi_domain.is_ambiguous


def test_valid_plurality_and_separate_ambiguity_are_both_preserved():
    result = DomainUnderstandingEngine().understand(
        "Oil prices affect airline costs. Research Amazon."
    )

    assert result.multi_domain.interactions
    assert result.ambiguity.ambiguity_present
    assert result.ambiguity.scope_ambiguity_type == AmbiguityType.MULTI_SCOPE_UNCLEAR
    assert result.ambiguity.possible_scopes


def test_valid_scopes_and_incomplete_subject_information_coexist():
    result = DomainUnderstandingEngine().understand("Compare physical oil with gold.")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }

    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.ASSET in scopes
    assert result.ambiguity.scope_ambiguity_type == AmbiguityType.MULTI_SCOPE_UNCLEAR
    assert ScopeType.FINANCIAL_MARKET in result.ambiguity.possible_scopes


def test_distinct_subjects_keep_evidence_attached_to_scope_relationships():
    result = DomainUnderstandingEngine().understand(
        "Analyze Apple's operations and gold futures in Nigeria."
    )

    assert any(
        item.scope_type == ScopeType.COMPANY and item.subject == "Apple"
        for item in result.scope_detection.evidence
    )
    assert any(
        item.scope_type == ScopeType.ASSET and item.subject == "gold"
        for item in result.scope_detection.evidence
    )
    assert any(
        relationship.target_scope == ScopeType.COMPANY
        and relationship.target_subject == "Apple"
        for relationship in result.scope_classification.relationships
    )
    assert any(
        relationship.target_scope == ScopeType.ASSET
        and relationship.target_subject == "gold"
        for relationship in result.scope_classification.relationships
    )


def test_plurality_relationships_survive_an_independent_domain_conflict():
    result = DomainUnderstandingEngine().understand(
        "Oil prices affect airline costs. Research Apple fruit stock."
    )

    assert result.ambiguity.ambiguity_type == AmbiguityType.DOMAIN_CONFLICT
    assert result.ambiguity.conflicting_domains
    assert result.ambiguity.conflict_evidence
    assert result.multi_domain.interactions
    assert result.ambiguity.evidence


def test_scope_conflict_and_independent_scope_ambiguity_are_both_reported():
    result = DomainUnderstandingEngine().understand(
        "The financial-market scope only conflicts with physical-commerce "
        "scope only; research the bank."
    )

    assert result.ambiguity.ambiguity_type == AmbiguityType.SCOPE_CONFLICT
    assert result.ambiguity.conflicting_scopes
    assert result.ambiguity.scope_ambiguity_type in {
        AmbiguityType.SCOPE_AMBIGUOUS,
        AmbiguityType.MULTI_SCOPE_UNCLEAR,
    }
    assert result.ambiguity.conflict_evidence
    assert result.ambiguity.evidence


def test_ambiguity_plurality_and_existing_confidence_correction_serialize():
    sense = SenseEngine()
    previous = sense.understand("Research oil futures.")
    corrected = sense.understand(
        "I mean physical oil supply.", previous_result=previous
    )
    current = sense.understand("How do oil prices affect interest rates?")
    corrected_result = corrected.domain_sense
    domain_result = current.domain_sense
    payload = current.to_dict()

    assert corrected_result is not None
    assert corrected_result.correction.history
    assert domain_result is not None
    assert domain_result.confidence is not None
    assert domain_result.correction is not None
    assert payload["domain_sense"]["ambiguity"]["domain_ambiguity_type"]
    assert payload["domain_sense"]["multi_domain"]["interactions"]
    json.dumps(payload)
