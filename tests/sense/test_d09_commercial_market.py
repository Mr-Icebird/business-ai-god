import json

import pytest

from app.sense.domain.ambiguity.models import AmbiguityType
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeContextType,
    ScopeLevel,
    ScopeType,
)
from app.sense.engine import SenseEngine

_CASES = (
    (
        "Analyze a retail business.",
        ("business",),
        ScopeType.BUSINESS,
        {ScopeType.BUSINESS},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the retail market.",
        (),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET, ScopeType.BUSINESS},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Compare two retail companies.",
        ("business",),
        ScopeType.COMPANY,
        {ScopeType.COMPANY, ScopeType.BUSINESS},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze retail consumer demand.",
        (),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.PHYSICAL_COMMERCE},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze smartphone manufacturing.",
        ("technology", "operations"),
        ScopeType.OPERATIONAL,
        {ScopeType.OPERATIONAL, ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the smartphone market.",
        ("technology", "business", "markets"),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Compare smartphone production costs with smartphone retail prices.",
        ("technology",),
        ScopeType.CROSS_DOMAIN,
        {
            ScopeType.CROSS_DOMAIN,
            ScopeType.OPERATIONAL,
            ScopeType.PHYSICAL_COMMERCE,
            ScopeType.COMMERCIAL_MARKET,
        },
        set(),
        {"compares"},
        AmbiguityType.NONE,
    ),
    (
        "Analyze a smartphone manufacturer's revenue.",
        ("technology", "business", "finance"),
        ScopeType.BUSINESS,
        {ScopeType.BUSINESS},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze an e-commerce company.",
        ("business",),
        ScopeType.COMPANY,
        {ScopeType.COMPANY, ScopeType.BUSINESS},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the e-commerce market.",
        (),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET, ScopeType.BUSINESS},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Compare two online marketplaces.",
        (),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the costs of operating an online store.",
        (),
        ScopeType.OPERATIONAL,
        {ScopeType.OPERATIONAL},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze agricultural demand.",
        ("agriculture",),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.PHYSICAL_COMMERCE},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze agricultural produce wholesale trading.",
        ("agriculture",),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.PHYSICAL_COMMERCE},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze crop production costs.",
        (),
        ScopeType.OPERATIONAL,
        {ScopeType.OPERATIONAL, ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the physical transportation of agricultural produce.",
        ("agriculture",),
        ScopeType.PHYSICAL_COMMERCE,
        {ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Compare agricultural supply with consumer demand.",
        ("agriculture",),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.PHYSICAL_COMMERCE},
        {"compares"},
        AmbiguityType.NONE,
    ),
    (
        "Analyze physical gold.",
        ("commodities",),
        ScopeType.PHYSICAL_COMMERCE,
        {ScopeType.PHYSICAL_COMMERCE, ScopeType.ASSET},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze gold futures.",
        ("markets", "commodities"),
        ScopeType.FINANCIAL_MARKET,
        {ScopeType.FINANCIAL_MARKET, ScopeType.ASSET},
        {ScopeType.PHYSICAL_COMMERCE, ScopeType.COMMERCIAL_MARKET},
        {"market_instrument"},
        AmbiguityType.NONE,
    ),
    (
        "Compare physical gold with gold futures.",
        ("commodities",),
        ScopeType.CROSS_DOMAIN,
        {
            ScopeType.CROSS_DOMAIN,
            ScopeType.FINANCIAL_MARKET,
            ScopeType.PHYSICAL_COMMERCE,
            ScopeType.ASSET,
        },
        set(),
        {"compares", "market_instrument"},
        AmbiguityType.NONE,
    ),
    (
        "Analyze gold mining operations.",
        ("markets", "commodities", "operations"),
        ScopeType.OPERATIONAL,
        {ScopeType.OPERATIONAL, ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the gold market.",
        ("markets", "commodities", "business"),
        ScopeType.UNKNOWN,
        {
            ScopeType.UNKNOWN,
            ScopeType.COMMERCIAL_MARKET,
        },
        set(),
        set(),
        AmbiguityType.MULTI_SCOPE_UNCLEAR,
    ),
    (
        "Analyze petroleum distribution.",
        ("energy",),
        ScopeType.PHYSICAL_COMMERCE,
        {ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.FINANCIAL_MARKET, ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze petroleum prices.",
        ("energy",),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the petroleum market.",
        (),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the transportation costs of petroleum.",
        ("operations", "business", "energy"),
        ScopeType.OPERATIONAL,
        {ScopeType.OPERATIONAL, ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze a petroleum distribution company.",
        ("business", "energy"),
        ScopeType.COMPANY,
        {ScopeType.COMPANY, ScopeType.BUSINESS, ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze a logistics company.",
        ("business", "operations"),
        ScopeType.COMPANY,
        {ScopeType.COMPANY, ScopeType.BUSINESS, ScopeType.OPERATIONAL},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze physical shipment costs.",
        (),
        ScopeType.PHYSICAL_COMMERCE,
        {ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the logistics market.",
        ("operations",),
        ScopeType.COMMERCIAL_MARKET,
        {ScopeType.COMMERCIAL_MARKET, ScopeType.OPERATIONAL},
        {ScopeType.FINANCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze the cost of transporting goods.",
        (),
        ScopeType.PHYSICAL_COMMERCE,
        {ScopeType.PHYSICAL_COMMERCE},
        {ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.NONE,
    ),
    (
        "Analyze gold.",
        ("markets", "commodities"),
        ScopeType.ASSET,
        {ScopeType.ASSET},
        {ScopeType.FINANCIAL_MARKET, ScopeType.COMMERCIAL_MARKET},
        set(),
        AmbiguityType.MULTI_SCOPE_UNCLEAR,
    ),
)


@pytest.mark.parametrize(
    (
        "text",
        "expected_domains",
        "expected_primary",
        "expected_scopes",
        "excluded_scopes",
        "expected_relationships",
        "expected_ambiguity",
    ),
    _CASES,
)
def test_commercial_market_scope_is_task_focused_and_evidence_backed(
    text,
    expected_domains,
    expected_primary,
    expected_scopes,
    excluded_scopes,
    expected_relationships,
    expected_ambiguity,
):
    result = SenseEngine().understand(text)
    sense3 = result.domain_sense
    classification = sense3.scope_classification
    scopes = {classification.primary_scope, *classification.secondary_scopes}

    assert tuple(domain.value for domain in sense3.classification.domains) == (
        expected_domains
    )
    assert classification.primary_scope == expected_primary
    assert expected_scopes.issubset(scopes)
    assert not excluded_scopes.intersection(scopes)
    assert {
        relationship.relation for relationship in classification.relationships
    } == expected_relationships
    assert sense3.ambiguity.scope_ambiguity_type == expected_ambiguity
    assert all(
        isinstance(scope, ScopeType) for scope in sense3.ambiguity.possible_scopes
    )

    evidence_subjects = {
        item.subject for item in sense3.scope_detection.evidence if item.subject
    }
    assert evidence_subjects.issubset(set(classification.scope_subjects))
    for item in sense3.scope_detection.evidence:
        if item.provenance == EvidenceProvenance.SOURCE_TEXT:
            assert item.source_span is not None
            assert text[slice(*item.source_span)] == item.evidence
        elif item.provenance == EvidenceProvenance.INTERNAL_TAXONOMY:
            assert item.source_span is None

    for relationship in classification.relationships:
        assert relationship.evidence
        assert relationship.source_span is not None
        assert relationship.provenance == EvidenceProvenance.SOURCE_TEXT
        assert text[slice(*relationship.source_span)] == relationship.evidence
    for relationship in classification.unresolved_relationships:
        for span, source_text in zip(
            relationship.source_spans, relationship.source_texts
        ):
            assert source_text[slice(*span)]
    for path in sense3.scope_hierarchy.paths:
        for node in path.nodes:
            if node.provenance == EvidenceProvenance.SOURCE_TEXT:
                assert node.source_span is not None
                assert text[slice(*node.source_span)]
            elif node.provenance == EvidenceProvenance.INTERNAL_TAXONOMY:
                assert node.source_span is None

    if ScopeType.COMMERCIAL_MARKET in scopes:
        assert ScopeContextType.COMMERCIAL in {
            context.context_type for context in sense3.scope_context.contexts
        }
        assert ScopeLevel.MARKET in classification.scope_levels
        assert any(
            node.level == ScopeLevel.MARKET
            for path in sense3.scope_hierarchy.paths
            for node in path.nodes
        )

    payload = result.to_dict()
    json.dumps(payload)
    serialized_sense3 = payload["domain_sense"]
    assert serialized_sense3["scope_type"] == expected_primary.value
    assert serialized_sense3["scope"]["primary_scope"] == expected_primary.value


def test_agricultural_demand_does_not_create_physical_handling_evidence():
    text = "Analyze agricultural demand."
    result = SenseEngine().understand(text).domain_sense

    assert result.scope_type == ScopeType.COMMERCIAL_MARKET
    assert not any(
        item.scope_type == ScopeType.PHYSICAL_COMMERCE
        for item in result.scope_detection.evidence
    )


def test_commercial_market_and_financial_market_remain_distinct():
    commercial = SenseEngine().understand("Analyze the smartphone market.").domain_sense
    financial = SenseEngine().understand("Analyze gold futures.").domain_sense

    assert commercial.scope_type == ScopeType.COMMERCIAL_MARKET
    assert financial.scope_type == ScopeType.FINANCIAL_MARKET
    assert ScopeType.FINANCIAL_MARKET not in {
        commercial.scope_type,
        *commercial.scope_classification.secondary_scopes,
    }
    assert ScopeType.COMMERCIAL_MARKET not in {
        financial.scope_type,
        *financial.scope_classification.secondary_scopes,
    }


def test_unqualified_gold_market_preserves_candidates_without_forcing_financial_scope():
    result = SenseEngine().understand("Analyze the gold market.").domain_sense

    assert result.scope_type == ScopeType.UNKNOWN
    assert ScopeType.FINANCIAL_MARKET not in {
        result.scope_type,
        *result.scope_classification.secondary_scopes,
    }
    assert result.ambiguity.scope_ambiguity_type == AmbiguityType.MULTI_SCOPE_UNCLEAR
    assert {
        ScopeType.FINANCIAL_MARKET,
        ScopeType.COMMERCIAL_MARKET,
    }.issubset(set(result.ambiguity.possible_scopes))


def test_comparison_relationships_keep_full_operand_subjects():
    text = "Compare smartphone production costs with smartphone retail prices."
    result = SenseEngine().understand(text).domain_sense
    relationship = next(
        item
        for item in result.scope_classification.relationships
        if item.relation == "compares"
    )

    assert relationship.source_subject == "smartphone production costs"
    assert relationship.target_subject == "smartphone retail prices"
