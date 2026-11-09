import pytest

from app.sense.domain.scope.models import EvidenceProvenance, ScopeType
from app.sense.engine import SenseEngine


def _sense(text):
    return SenseEngine().understand(text).domain_sense


def _scopes(result):
    return {
        result.scope_type,
        *result.scope_classification.secondary_scopes,
    }


def _relationships(result, relation):
    return [
        item
        for item in result.scope_classification.relationships
        if item.relation == relation
    ]


@pytest.mark.parametrize(
    ("text", "expected_primary"),
    [
        ("Analyze Apple's stock.", ScopeType.FINANCIAL_MARKET),
        ("Analyze Apple's business operations.", ScopeType.OPERATIONAL),
        ("Analyze Tesla's operations and oil prices.", ScopeType.OPERATIONAL),
        ("Research commercial bank lending.", ScopeType.BUSINESS),
        ("Compare gold and oil markets.", ScopeType.FINANCIAL_MARKET),
    ],
)
def test_primary_scope_uses_request_focus_without_duplicate_secondary(
    text, expected_primary
):
    result = _sense(text)

    assert result.scope_type == expected_primary
    assert result.scope_type not in result.scope_classification.secondary_scopes


def test_named_company_stock_has_local_equity_relationship_and_evidence():
    text = "Analyze Apple's stock."
    result = _sense(text)

    assert {ScopeType.FINANCIAL_MARKET, ScopeType.COMPANY, ScopeType.ASSET}.issubset(
        _scopes(result)
    )
    relationship = _relationships(result, "has_equity")[0]
    assert (relationship.source_subject, relationship.target_subject) == (
        "Apple",
        "stock",
    )
    assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
    assert text[slice(*relationship.source_span)] == relationship.evidence


def test_taxonomy_evidence_stays_spanless_and_distinct_from_source_evidence():
    result = _sense("Analyze gold futures.")
    source_evidence = [
        item
        for item in result.scope_detection.evidence
        if item.provenance == EvidenceProvenance.SOURCE_TEXT
    ]
    taxonomy_evidence = [
        item
        for item in result.scope_detection.evidence
        if item.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
    ]

    assert source_evidence
    assert all(item.source_span is not None for item in source_evidence)
    assert taxonomy_evidence
    assert all(item.source_span is None for item in taxonomy_evidence)


def test_business_operations_remain_operational_and_belong_to_named_company():
    text = "Analyze Apple's business operations."
    result = _sense(text)

    assert result.scope_type == ScopeType.OPERATIONAL
    relationship = _relationships(result, "belongs_to")[0]
    assert relationship.source_subject == "Apple's business operations"
    assert relationship.target_subject == "Apple"
    assert text[slice(*relationship.source_span)] == relationship.evidence


def test_explicit_effect_connects_only_the_evidenced_economic_and_operational_scopes():
    text = "Analyze the effect of Nigerian inflation on business operations."
    result = _sense(text)

    relationship = _relationships(result, "affects")[0]
    assert relationship.source_scope == ScopeType.ECONOMIC
    assert relationship.target_scope == ScopeType.OPERATIONAL
    assert relationship.source_span == (12, 63)
    assert text[slice(*relationship.source_span)] == relationship.evidence
    assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
    assert result.scope_type == ScopeType.CROSS_DOMAIN


def test_cooccurring_operations_and_oil_prices_remain_unresolved():
    text = "Analyze Tesla's operations and oil prices."
    result = _sense(text)

    assert result.scope_type == ScopeType.OPERATIONAL
    assert {ScopeType.FINANCIAL_MARKET, ScopeType.OPERATIONAL}.issubset(_scopes(result))
    assert not _relationships(result, "compares")
    assert not any(
        item.source_subject in {"oil", "oil prices"}
        or item.target_subject in {"oil", "oil prices"}
        for item in result.scope_classification.relationships
    )
    unresolved = result.scope_classification.unresolved_relationships
    assert len(unresolved) == 1
    assert {"Tesla's operations", "oil"}.issubset(set(unresolved[0].subjects))


def test_cross_scope_comparison_uses_actual_operand_subjects():
    text = "Compare Tesla's operations with Apple's stock."
    result = _sense(text)

    relationship = _relationships(result, "compares")[0]
    assert relationship.source_scope == ScopeType.OPERATIONAL
    assert relationship.target_scope == ScopeType.FINANCIAL_MARKET
    assert relationship.source_subject == "Tesla's operations"
    assert relationship.target_subject == "Apple's stock"
    assert text[slice(*relationship.source_span)] == relationship.evidence
    assert result.scope_type == ScopeType.CROSS_DOMAIN


def test_three_subject_request_keeps_local_links_and_unresolved_group():
    text = "Analyze Apple's operations, Microsoft's stock, and gold futures."
    result = _sense(text)

    assert {item.relation for item in result.scope_classification.relationships} >= {
        "belongs_to",
        "has_equity",
        "market_instrument",
    }
    unresolved = result.scope_classification.unresolved_relationships
    assert len(unresolved) == 1
    assert set(unresolved[0].subjects) == {
        "Apple's operations",
        "Microsoft's stock",
        "gold futures",
    }
    for relationship in result.scope_classification.relationships:
        assert relationship.source_span is not None
        assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
        assert text[slice(*relationship.source_span)] == relationship.evidence


def test_three_comparison_operands_keep_independent_explicit_relationships():
    text = "Compare physical gold, gold futures, and gold mining."
    result = _sense(text)
    comparisons = _relationships(result, "compares")

    assert len(comparisons) == 2
    assert {item.target_subject for item in comparisons} == {
        "gold futures",
        "gold mining",
    }
    assert all(
        text[slice(*item.source_span)] == item.evidence
        and item.provenance == EvidenceProvenance.SOURCE_TEXT
        for item in comparisons
    )
    assert not result.scope_classification.unresolved_relationships


def test_geographic_and_market_scopes_do_not_inherit_each_others_hierarchy_subjects():
    result = _sense(
        "Analyze business operations in Nigeria and financial markets in Japan."
    )
    paths = result.scope_hierarchy.paths

    assert any(path.subject == "financial markets in Japan" for path in paths)
    assert any(path.subject == "Nigeria" for path in paths)
    assert any(path.subject == "Japan" for path in paths)
    assert not result.scope_classification.relationships
    assert result.scope_classification.unresolved_relationships
    assert result.scope_context.cross_domain is False
