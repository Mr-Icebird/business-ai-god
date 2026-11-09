import pytest

from app.sense.domain.multi_domain.models import DomainRelationshipType
from app.sense.domain.models import DomainType
from app.sense.domain.scope.models import EvidenceProvenance, ScopeType
from app.sense.engine import SenseEngine

_REGRESSION_CASES = (
    (
        "Analyze gold futures.",
        {DomainType.MARKETS, DomainType.COMMODITIES},
        {ScopeType.FINANCIAL_MARKET, ScopeType.ASSET},
        {"market_instrument"},
        (),
        True,
    ),
    (
        "Compare physical gold with gold futures.",
        {DomainType.COMMODITIES},
        {
            ScopeType.FINANCIAL_MARKET,
            ScopeType.PHYSICAL_COMMERCE,
            ScopeType.ASSET,
        },
        {"compares", "market_instrument"},
        (),
        True,
    ),
    (
        "Analyze Apple's stock and Microsoft's stock.",
        {DomainType.MARKETS, DomainType.EQUITIES},
        {ScopeType.FINANCIAL_MARKET, ScopeType.COMPANY, ScopeType.ASSET},
        {"has_equity"},
        (("Apple's stock", "Microsoft's stock"),),
        True,
    ),
    (
        "Compare Apple in the airline industry with Microsoft in the banking industry.",
        {DomainType.BANKING, DomainType.TECHNOLOGY, DomainType.BUSINESS},
        {ScopeType.COMPANY, ScopeType.INDUSTRY},
        {"compares", "company_in_industry"},
        (),
        True,
    ),
    (
        "Compare Nigerian inflation with US interest rates.",
        {DomainType.ECONOMICS},
        {ScopeType.ECONOMIC, ScopeType.GEOGRAPHIC},
        {"compares", "qualifies"},
        (),
        True,
    ),
    (
        "Compare Nigerian inflation with US interest rates and Japanese unemployment.",
        {DomainType.ECONOMICS},
        {ScopeType.ECONOMIC, ScopeType.GEOGRAPHIC},
        {"compares", "qualifies"},
        (),
        True,
    ),
    (
        "Research commercial bank lending.",
        {DomainType.BANKING},
        {ScopeType.BUSINESS},
        set(),
        (),
        False,
    ),
    (
        "Analyze Tesla's operations and oil.",
        {DomainType.OPERATIONS, DomainType.COMMODITIES, DomainType.ENERGY},
        {ScopeType.OPERATIONAL, ScopeType.COMPANY, ScopeType.ASSET},
        {"belongs_to"},
        (("Tesla's operations", "oil"),),
        True,
    ),
    (
        "Analyze Tesla's operations and oil prices in Nigeria.",
        {
            DomainType.OPERATIONS,
            DomainType.MARKETS,
            DomainType.COMMODITIES,
            DomainType.ENERGY,
        },
        {
            ScopeType.OPERATIONAL,
            ScopeType.COMPANY,
            ScopeType.ASSET,
            ScopeType.GEOGRAPHIC,
        },
        {"belongs_to"},
        (("Tesla's operations", "oil", "Nigeria"),),
        True,
    ),
    (
        "Analyze Apple's operations, Microsoft's stock, and gold futures.",
        {
            DomainType.OPERATIONS,
            DomainType.MARKETS,
            DomainType.EQUITIES,
            DomainType.COMMODITIES,
        },
        {
            ScopeType.FINANCIAL_MARKET,
            ScopeType.OPERATIONAL,
            ScopeType.COMPANY,
            ScopeType.ASSET,
        },
        {"belongs_to", "has_equity", "market_instrument"},
        (("Apple's operations", "Microsoft's stock", "gold futures"),),
        True,
    ),
    (
        "Compare Tesla's operations with Apple's operations.",
        {DomainType.OPERATIONS, DomainType.BUSINESS},
        {ScopeType.OPERATIONAL, ScopeType.COMPANY},
        {"compares", "belongs_to"},
        (),
        True,
    ),
    (
        "Analyze oil prices because they affect transportation costs.",
        {DomainType.MARKETS, DomainType.COMMODITIES, DomainType.OPERATIONS},
        {ScopeType.CROSS_DOMAIN, ScopeType.OPERATIONAL, ScopeType.ASSET},
        set(),
        (),
        True,
    ),
)


@pytest.mark.parametrize(
    (
        "text",
        "expected_domains",
        "expected_scopes",
        "expected_relationships",
        "expected_unresolved",
        "expects_hierarchy",
    ),
    _REGRESSION_CASES,
)
def test_requested_regression_cases_keep_local_relationship_evidence(
    text,
    expected_domains,
    expected_scopes,
    expected_relationships,
    expected_unresolved,
    expects_hierarchy,
):
    domain_result = SenseEngine().understand(text).domain_sense
    scopes = {
        domain_result.scope_type,
        *domain_result.scope_classification.secondary_scopes,
    }

    assert expected_domains.issubset(set(domain_result.classification.domains))
    assert expected_scopes.issubset(scopes)
    assert {
        item.relation for item in domain_result.scope_classification.relationships
    }.issuperset(expected_relationships)
    assert {
        item.subjects
        for item in domain_result.scope_classification.unresolved_relationships
    } == set(expected_unresolved)
    assert bool(domain_result.scope_hierarchy.paths) is expects_hierarchy

    for relationship in domain_result.scope_classification.relationships:
        assert relationship.source_span is not None
        assert relationship.evidence == text[slice(*relationship.source_span)]
        assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
    for relationship in domain_result.domain_relationships:
        if relationship.relationship_type == DomainRelationshipType.HIERARCHICAL:
            assert relationship.source_span is None
            assert relationship.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
        else:
            assert relationship.source_span is not None
            assert relationship.evidence == text[slice(*relationship.source_span)]
            assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
    for interaction in domain_result.multi_domain.interactions:
        assert interaction.source_span is not None
        assert interaction.evidence == text[slice(*interaction.source_span)]
        assert interaction.provenance == EvidenceProvenance.SOURCE_TEXT

    assert all(
        item.relationship_type != DomainRelationshipType.CO_OCCURS_WITH
        for item in domain_result.domain_relationships
    )


def test_relationships_do_not_cross_sentence_or_contrast_boundaries():
    text = (
        "Compare Nigerian inflation with US interest rates. "
        "Analyze Tesla's operations and oil."
    )
    result = SenseEngine().understand(text).domain_sense
    relationships = result.scope_classification.relationships

    assert any(item.relation == "compares" for item in relationships)
    assert all(
        item.source_span[0] < text.index(".")
        for item in relationships
        if item.relation == "compares"
    )
    assert {
        item.subjects for item in result.scope_classification.unresolved_relationships
    } == {("Tesla's operations", "oil")}
    assert not result.multi_domain.interactions

    contrast_text = (
        "Oil prices affect transportation costs, but Tesla's operations and oil "
        "remain separate subjects."
    )
    contrast = SenseEngine().understand(contrast_text).domain_sense
    assert len(contrast.multi_domain.interactions) == 1
    interaction = contrast.multi_domain.interactions[0]
    assert interaction.evidence == ("Oil prices affect transportation costs")
    assert contrast_text[slice(*interaction.source_span)] == interaction.evidence
    assert not any(
        relation.source_subject == "Tesla's operations"
        or relation.target_subject == "Tesla's operations"
        for relation in contrast.domain_relationships
    )


def test_unknown_relationship_does_not_remove_subjects_or_scope_evidence():
    text = "Analyze Tesla's operations and oil."
    result = SenseEngine().understand(text).domain_sense

    assert {"Tesla's operations", "oil"}.issubset(
        {
            item.subject
            for item in result.scope_detection.evidence
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
        }
    )
    unresolved = result.scope_classification.unresolved_relationships[0]
    assert unresolved.subjects == ("Tesla's operations", "oil")
    assert all(
        text[slice(*span)] in unresolved.subjects for span in unresolved.source_spans
    )
