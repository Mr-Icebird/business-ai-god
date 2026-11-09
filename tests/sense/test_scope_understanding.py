import json

import pytest

from app.sense.domain.engine import DomainUnderstandingEngine
from app.sense.domain.models import DomainContext, DomainType
from app.sense.domain.scope.classifier import ScopeClassifier
from app.sense.domain.scope.context import ScopeContextDetector
from app.sense.domain.scope.detector import ScopeDetector
from app.sense.domain.scope.hierarchy import ScopeHierarchyResolver
from app.sense.domain.scope.models import (
    ScopeContextType,
    EvidenceProvenance,
    ScopeLevel,
    ScopeType,
)
from app.sense.input.engine import INPUT_SENSE
from app.sense.intent.engine import IntentUnderstandingEngine


def _understand(text, *, sense2=None, source_input=None, context=None):
    engine = DomainUnderstandingEngine()
    return engine.understand(
        source_input or text,
        sense2_result=sense2,
        context=context,
    )


# 1. Scope Detection


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Analyze EURUSD.", ScopeType.FINANCIAL_MARKET),
        ("Analyze gold futures.", ScopeType.FINANCIAL_MARKET),
        ("How much crude oil does Nigeria produce?", ScopeType.PHYSICAL_COMMERCE),
        ("Why is inflation rising in Nigeria?", ScopeType.ECONOMIC),
        ("How does oil affect transportation costs?", ScopeType.CROSS_DOMAIN),
        ("How is Apple's stock performing?", ScopeType.FINANCIAL_MARKET),
        ("How much revenue did Apple make?", ScopeType.COMPANY),
        ("How does Apple manufacture its products?", ScopeType.OPERATIONAL),
        ("Research the Nigerian banking industry.", ScopeType.INDUSTRY),
        ("How does CBN regulation affect Nigerian banks?", ScopeType.REGULATORY),
        ("How is the airline industry doing?", ScopeType.INDUSTRY),
        ("How does the company reduce operating costs?", ScopeType.OPERATIONAL),
        ("What is the company's expansion strategy?", ScopeType.STRATEGIC),
        ("Compare Nigeria and Ghana.", ScopeType.GEOGRAPHIC),
        ("Compare gold and oil markets.", ScopeType.FINANCIAL_MARKET),
        ("Tell me about oil.", ScopeType.ASSET),
        ("Tell me about gold.", ScopeType.ASSET),
        ("How many crude oil futures were traded?", ScopeType.FINANCIAL_MARKET),
    ],
)
def test_scope_detection_primary_scope(text, expected):
    result = _understand(text)
    assert result.scope_classification.primary_scope == expected


# 2. Scope Classification


def test_physical_oil_production_is_not_financial_market_scope():
    result = _understand("How much crude oil does Nigeria produce?")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert ScopeType.PHYSICAL_COMMERCE in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes
    assert result.classification is not None


def test_company_oil_sales_and_gold_mining_are_physical_not_market_scope():
    sold = _understand("The company sells oil.")
    mining = _understand("How does gold mining work?")
    sold_scopes = {
        sold.scope_classification.primary_scope,
        *sold.scope_classification.secondary_scopes,
    }
    mining_scopes = {
        mining.scope_classification.primary_scope,
        *mining.scope_classification.secondary_scopes,
    }
    assert ScopeType.PHYSICAL_COMMERCE in sold_scopes
    assert ScopeType.FINANCIAL_MARKET not in sold_scopes
    assert {ScopeType.PHYSICAL_COMMERCE, ScopeType.OPERATIONAL}.issubset(mining_scopes)


def test_stock_request_keeps_company_asset_and_market_scopes_distinct():
    result = _understand("How is Apple's stock performing?")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert {ScopeType.COMPANY, ScopeType.FINANCIAL_MARKET, ScopeType.ASSET}.issubset(
        scopes
    )
    assert "Apple" in result.scope_classification.scope_subjects


def test_company_revenue_is_not_automatically_equity_scope():
    result = _understand("How much revenue did Apple make?")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert ScopeType.COMPANY in scopes
    assert ScopeType.BUSINESS in scopes
    assert ScopeType.FINANCIAL_MARKET not in scopes


def test_multiple_scope_subjects_and_boundaries_are_preserved():
    result = _understand("Compare Nigeria and Ghana.")
    assert set(result.scope_classification.scope_subjects) >= {"Nigeria", "Ghana"}
    assert {item.value for item in result.scope_classification.boundaries} >= {
        "Nigeria",
        "Ghana",
    }
    assert all(
        item.level == ScopeLevel.COUNTRY
        for item in result.scope_classification.boundaries
    )


# 3. Scope Hierarchy


def test_market_asset_hierarchy_for_futures():
    result = _understand("Analyze gold futures.")
    levels = {
        node.level for path in result.scope_hierarchy.paths for node in path.nodes
    }
    assert {ScopeLevel.MARKET, ScopeLevel.ASSET}.issubset(levels)
    asset = next(
        node
        for path in result.scope_hierarchy.paths
        for node in path.nodes
        if node.level == ScopeLevel.ASSET
    )
    assert asset.parent_level == ScopeLevel.MARKET


def test_gold_futures_hierarchy_keeps_values_at_their_supported_levels():
    result = _understand("Analyze gold futures.")
    assert len(result.scope_hierarchy.paths) == 1
    path = result.scope_hierarchy.paths[0]

    assert path.subject == "gold"
    assert [
        (node.level, node.value, node.parent_level, node.parent_value)
        for node in path.nodes
    ] == [
        (ScopeLevel.MARKET, None, None, None),
        (ScopeLevel.ASSET, "gold", ScopeLevel.MARKET, None),
        (ScopeLevel.TRANSACTION, "futures", ScopeLevel.ASSET, "gold"),
    ]


def test_physical_gold_and_gold_futures_keep_separate_hierarchy_paths():
    result = _understand("Compare physical gold with gold futures.")
    paths_by_levels = {
        tuple(node.level for node in path.nodes): path
        for path in result.scope_hierarchy.paths
    }

    assert (ScopeLevel.ASSET,) in paths_by_levels
    assert (
        ScopeLevel.MARKET,
        ScopeLevel.ASSET,
        ScopeLevel.TRANSACTION,
    ) in paths_by_levels
    physical_path = paths_by_levels[(ScopeLevel.ASSET,)]
    financial_path = paths_by_levels[
        (ScopeLevel.MARKET, ScopeLevel.ASSET, ScopeLevel.TRANSACTION)
    ]
    assert physical_path.subject == financial_path.subject == "gold"
    assert physical_path.nodes[0].value == "gold"
    assert financial_path.nodes[0].value is None
    assert financial_path.nodes[1].value == "gold"
    assert financial_path.nodes[2].value == "futures"

    evidence = result.scope_detection.evidence
    assert any(
        item.scope_type == ScopeType.PHYSICAL_COMMERCE and item.source_span == (8, 21)
        for item in evidence
    )
    assert any(
        item.scope_type == ScopeType.FINANCIAL_MARKET and item.source_span == (32, 39)
        for item in evidence
    )


def test_company_stock_hierarchy_paths_remain_associated_and_serialize():
    text = "Analyze Apple's stock and Microsoft's stock."
    result = _understand(text)
    stock_paths = [
        path
        for path in result.scope_hierarchy.paths
        if tuple(node.level for node in path.nodes)
        == (ScopeLevel.MARKET, ScopeLevel.ASSET)
    ]

    assert {path.subject for path in stock_paths} == {"Apple", "Microsoft"}
    assert all(
        path.nodes[0].value is None and path.nodes[1].value == "stock"
        for path in stock_paths
    )
    equity_relationships = [
        item
        for item in result.scope_classification.relationships
        if item.relation == "has_equity"
    ]
    assert {
        (item.source_subject, item.target_subject) for item in equity_relationships
    } == {("Apple", "stock"), ("Microsoft", "stock")}
    assert all(
        text[slice(*item.source_span)] == item.evidence for item in equity_relationships
    )
    assert all(
        item.relation != "coexists_with"
        for item in result.scope_classification.relationships
    )

    payload = json.loads(json.dumps(result.to_dict()))
    serialized_stock_paths = [
        path
        for path in payload["scope_hierarchy"]["paths"]
        if [node["level"] for node in path["nodes"]] == ["market", "asset"]
    ]
    assert {path["subject"] for path in serialized_stock_paths} == {
        "Apple",
        "Microsoft",
    }
    assert all(
        path["nodes"][1]["parent_value"] is None for path in serialized_stock_paths
    )


def test_country_hierarchy_paths_keep_geographic_values_separate():
    result = _understand("Compare Nigerian inflation with US interest rates.")
    country_paths = [
        path
        for path in result.scope_hierarchy.paths
        if len(path.nodes) == 1 and path.nodes[0].level == ScopeLevel.COUNTRY
    ]

    assert {(path.subject, path.nodes[0].value) for path in country_paths} == {
        ("Nigerian", "Nigerian"),
        ("US", "US"),
    }


def test_unnamed_companies_do_not_gain_invented_subject_or_industry_paths():
    result = _understand("Compare two companies operating in different industries.")

    assert result.scope_classification.scope_subjects == ("companies",)
    assert not any(
        boundary.level == ScopeLevel.INDUSTRY
        for boundary in result.scope_classification.boundaries
    )
    assert all(
        path.subject not in {"Company A", "Company B"}
        for path in result.scope_hierarchy.paths
    )
    assert (
        len(
            [
                path
                for path in result.scope_hierarchy.paths
                if ScopeLevel.COMPANY in {node.level for node in path.nodes}
            ]
        )
        == 1
    )


def test_commercial_bank_lending_has_supported_business_scope_without_invented_path():
    result = _understand("Research commercial bank lending.")

    evidence = result.scope_detection.evidence
    assert len(evidence) == 1
    assert evidence[0].scope_type == ScopeType.BUSINESS
    assert evidence[0].evidence == "commercial bank lending"
    assert evidence[0].source_span == (9, 32)
    assert evidence[0].subject is None
    assert result.scope_classification.primary_scope == ScopeType.BUSINESS
    assert not result.scope_classification.boundaries
    assert not result.scope_hierarchy.paths


def test_company_industry_associations_require_and_preserve_explicit_subjects():
    text = (
        "Compare Apple in the airline industry with Microsoft in the banking industry."
    )
    result = _understand(text)

    company_evidence = {
        item.subject
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.COMPANY
    }
    assert company_evidence == {"Apple", "Microsoft"}
    assert not any(
        boundary.value == "industry"
        for boundary in result.scope_classification.boundaries
    )

    explicit_relationships = [
        item
        for item in result.scope_classification.relationships
        if item.relation == "company_in_industry"
    ]
    assert {
        (item.source_subject, item.target_subject) for item in explicit_relationships
    } == {
        ("airline industry", "Apple"),
        ("banking industry", "Microsoft"),
    }
    assert all(item.source_span is not None for item in explicit_relationships)
    assert all(
        text[slice(*item.source_span)] == item.evidence
        for item in explicit_relationships
    )
    assert all(
        item.relation != "coexists_with"
        for item in result.scope_classification.relationships
    )

    company_paths = [
        path
        for path in result.scope_hierarchy.paths
        if any(node.level == ScopeLevel.COMPANY for node in path.nodes)
    ]
    assert {
        (
            path.subject,
            next(
                node.value for node in path.nodes if node.level == ScopeLevel.INDUSTRY
            ),
        )
        for path in company_paths
    } == {
        ("Apple", "airline industry"),
        ("Microsoft", "banking industry"),
    }
    assert {
        (
            path.subject,
            next(
                node.parent_value
                for node in path.nodes
                if node.level == ScopeLevel.COMPANY
            ),
        )
        for path in company_paths
    } == {
        ("Apple", "airline industry"),
        ("Microsoft", "banking industry"),
    }


def test_country_economic_subject_associations_use_explicit_modifier_evidence():
    result = _understand("Compare Nigerian inflation with US interest rates.")

    associations = [
        item
        for item in result.scope_classification.relationships
        if item.relation == "qualifies"
    ]
    assert {
        (item.source_subject, item.target_subject, item.evidence)
        for item in associations
    } == {
        ("Nigerian", "inflation", "Nigerian inflation"),
        ("US", "interest rates", "US interest rates"),
    }

    geographic_evidence = {
        item.subject: item.source_span
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.GEOGRAPHIC
    }
    economic_evidence = {
        item.evidence: item.source_span
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.ECONOMIC
    }
    assert geographic_evidence == {"Nigerian": (8, 16), "US": (32, 34)}
    assert economic_evidence == {"inflation": (17, 26), "interest rates": (35, 49)}


def test_country_and_economic_terms_without_modifier_phrase_are_not_associated():
    result = _understand("Compare Nigeria with inflation; US with interest rates.")

    assert not any(
        item.relation == "qualifies"
        for item in result.scope_classification.relationships
    )


def test_unspecified_industries_preserve_both_companies_and_comparison_only():
    text = "Compare Apple and Microsoft in different industries."
    result = _understand(text)

    companies = [
        item
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.COMPANY
    ]
    assert [(item.subject, item.source_span) for item in companies] == [
        ("Apple", (8, 13)),
        ("Microsoft", (18, 27)),
    ]
    assert not any(
        item.scope_type == ScopeType.INDUSTRY
        for item in result.scope_detection.evidence
    )
    comparison = [
        item
        for item in result.scope_classification.relationships
        if item.relation == "compares"
    ]
    assert len(comparison) == 1
    assert (comparison[0].source_subject, comparison[0].target_subject) == (
        "Apple",
        "Microsoft",
    )
    assert comparison[0].evidence == "Compare Apple and Microsoft"
    assert text[slice(*comparison[0].source_span)] == comparison[0].evidence
    assert not result.scope_hierarchy.paths or {
        path.subject
        for path in result.scope_hierarchy.paths
        if path.subject is not None
    } == {"Apple", "Microsoft"}


def test_three_geographic_economic_associations_are_local_and_span_backed():
    text = (
        "Compare Nigerian inflation with US interest rates and Japanese unemployment."
    )
    result = _understand(text)

    geographic = [
        item
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.GEOGRAPHIC
    ]
    assert [(item.subject, item.level, item.source_span) for item in geographic] == [
        ("Nigerian", ScopeLevel.COUNTRY, (8, 16)),
        ("US", ScopeLevel.COUNTRY, (32, 34)),
        ("Japanese", ScopeLevel.COUNTRY, (54, 62)),
    ]
    economic = [
        item
        for item in result.scope_detection.evidence
        if item.scope_type == ScopeType.ECONOMIC
    ]
    assert [(item.evidence, item.source_span) for item in economic] == [
        ("inflation", (17, 26)),
        ("interest rates", (35, 49)),
        ("unemployment", (63, 75)),
    ]
    assert {
        (
            item.source_subject,
            item.target_subject,
            item.evidence,
            item.source_span,
        )
        for item in result.scope_classification.relationships
        if item.relation == "qualifies"
    } == {
        ("Nigerian", "inflation", "Nigerian inflation", (8, 26)),
        ("US", "interest rates", "US interest rates", (32, 49)),
        ("Japanese", "unemployment", "Japanese unemployment", (54, 75)),
    }
    assert all(
        text[slice(*item.source_span)] == item.evidence
        for item in result.scope_classification.relationships
        if item.relation == "qualifies"
    )
    assert all(
        item.relation != "coexists_with"
        for item in result.scope_classification.relationships
    )


def test_scope_evidence_provenance_distinguishes_text_from_taxonomy_metadata():
    text = "Analyze gold futures."
    result = _understand(text)

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
    assert all(
        item.source_span is not None
        and text[slice(*item.source_span)].casefold() == item.evidence.casefold()
        for item in source_evidence
    )
    assert any(item.evidence == "commodity domain" for item in taxonomy_evidence)
    serialized_evidence = result.to_dict()["evidence"]["scope"]
    serialized_taxonomy = [
        item
        for item in serialized_evidence
        if item["provenance"] == EvidenceProvenance.INTERNAL_TAXONOMY.value
    ]
    assert any(item["evidence"] == "commodity domain" for item in serialized_taxonomy)


def test_spanless_taxonomy_evidence_does_not_create_generic_relationships():
    result = _understand("Analyze gold futures.")

    assert all(
        relationship.relation != "coexists_with"
        for relationship in result.scope_classification.relationships
    )
    assert all(
        relationship.source_span is not None
        for relationship in result.scope_classification.relationships
    )


@pytest.mark.parametrize(
    ("text", "expected_levels", "expected_subject"),
    [
        ("Analyze EURUSD.", (ScopeLevel.MARKET, ScopeLevel.ASSET), "EURUSD"),
        ("Analyze Bitcoin.", (ScopeLevel.MARKET, ScopeLevel.ASSET), "Bitcoin"),
        (
            "Analyze gold futures.",
            (ScopeLevel.MARKET, ScopeLevel.ASSET, ScopeLevel.TRANSACTION),
            "gold",
        ),
        ("Research physical oil supply.", (ScopeLevel.ASSET,), "oil"),
        ("Research commercial bank lending.", (), None),
        ("Analyze a company's operations.", (ScopeLevel.COMPANY,), "company"),
    ],
)
def test_scope_hierarchy_single_subject_regressions(
    text, expected_levels, expected_subject
):
    result = _understand(text)

    assert all(
        tuple(node.level for node in path.nodes) == expected_levels
        for path in result.scope_hierarchy.paths
    )
    if expected_levels:
        assert any(
            path.subject == expected_subject for path in result.scope_hierarchy.paths
        )
    else:
        assert not result.scope_hierarchy.paths


def test_country_and_company_hierarchies_are_not_flattened_together():
    result = _understand("Research Nigerian banking industry.")
    paths = result.scope_hierarchy.paths
    assert any(
        any(node.level == ScopeLevel.COUNTRY for node in path.nodes) for path in paths
    )
    assert any(
        any(node.level == ScopeLevel.INDUSTRY for node in path.nodes) for path in paths
    )
    assert all(
        node.parent_level is None
        or node.level
        in {
            ScopeLevel.REGIONAL,
            ScopeLevel.COUNTRY,
            ScopeLevel.STATE_LOCAL,
            ScopeLevel.COMPANY,
            ScopeLevel.PRODUCT,
            ScopeLevel.MARKET,
            ScopeLevel.ASSET,
            ScopeLevel.TRANSACTION,
        }
        for path in paths
        for node in path.nodes
    )


def test_geographic_hierarchy_adds_only_supported_levels():
    result = _understand("Research Nigeria's oil industry.")
    paths = result.scope_hierarchy.paths
    country_paths = [
        path
        for path in paths
        if any(node.level == ScopeLevel.COUNTRY for node in path.nodes)
    ]
    assert country_paths
    assert [node.level for node in country_paths[0].nodes] == [ScopeLevel.COUNTRY]


def test_geographic_scope_is_preserved_beside_economic_scope():
    result = _understand("Why is inflation rising in Nigeria?")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert ScopeType.ECONOMIC in scopes
    assert ScopeType.GEOGRAPHIC in scopes


def test_global_hierarchy_has_regional_market_industry_and_event_branches():
    result = _understand(
        "Global airline industry and gold futures market events today."
    )
    paths = result.scope_hierarchy.paths
    assert any(
        [node.level for node in path.nodes] == [ScopeLevel.GLOBAL, ScopeLevel.INDUSTRY]
        for path in paths
    )
    assert any(
        [node.level for node in path.nodes[:2]]
        == [ScopeLevel.GLOBAL, ScopeLevel.MARKET]
        for path in paths
    )


def test_company_stock_reaction_preserves_individual_event_scope_level():
    result = _understand("How did Apple's stock react to earnings?")
    assert ScopeLevel.COMPANY in result.scope_classification.scope_levels
    assert ScopeLevel.MARKET in result.scope_classification.scope_levels
    assert ScopeLevel.INDIVIDUAL_EVENT in result.scope_classification.scope_levels


# 4. Scope Context


def test_regulatory_geographic_and_business_contexts_coexist():
    result = _understand("How does CBN regulation affect Nigerian banks?")
    contexts = {item.context_type for item in result.scope_context.contexts}
    assert {
        ScopeContextType.REGULATORY,
        ScopeContextType.GEOGRAPHIC,
        ScopeContextType.BUSINESS,
    }.issubset(contexts)


def test_temporal_scope_context_reuses_sense1_and_sense2_constraints():
    source = INPUT_SENSE.understand("Research oil prices in 2025")
    sense2 = IntentUnderstandingEngine().understand(source)
    result = _understand(source, sense2=sense2)
    assert any(
        item.context_type == ScopeContextType.TEMPORAL
        for item in result.scope_context.contexts
    )
    assert any(
        item.evidence.casefold().find("2025") >= 0
        for item in result.scope_context.contexts
    )


# 5. Domain + Scope Integration


def test_domain_and_scope_are_separate_structured_results():
    result = _understand("Analyze EURUSD.")
    assert DomainType.FOREX in result.classification.domains
    assert result.scope_classification.primary_scope == ScopeType.FINANCIAL_MARKET
    assert ScopeType.ASSET in result.scope_classification.secondary_scopes


def test_cross_domain_scope_requires_a_link_between_contexts():
    linked = _understand("How does oil affect transportation costs?")
    unlinked = _understand("Oil prices and airline companies.")
    assert linked.scope_classification.primary_scope == ScopeType.CROSS_DOMAIN
    assert linked.scope_classification.direction == "affect"
    assert unlinked.scope_classification.primary_scope != ScopeType.CROSS_DOMAIN


# 6. SENSE-1 Integration


def test_sense1_dates_currencies_and_input_type_are_consumed_without_reparsing():
    source = INPUT_SENSE.understand(
        "Gold futures at $3,000 in 2025", input_type="market_data"
    )
    result = _understand(source)
    assert result.source_input is source
    assert ScopeType.FINANCIAL_MARKET in {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert any(
        item.context_type == ScopeContextType.TEMPORAL
        for item in result.scope_context.contexts
    )


# 7. SENSE-2 Integration


def test_sense2_task_and_constraints_contribute_scope_context():
    sense2 = IntentUnderstandingEngine().understand(
        "Research Nigerian banking industry in 2025."
    )
    result = _understand("Research Nigerian banking industry in 2025.", sense2=sense2)
    assert result.source_sense2 is sense2
    assert ScopeType.INDUSTRY in {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert any(
        item.context_type == ScopeContextType.TEMPORAL
        for item in result.scope_context.contexts
    )


# 8. Multiple Scopes


def test_company_industry_and_operational_scopes_can_coexist():
    result = _understand("How does Apple manufacture its products?")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert {ScopeType.COMPANY, ScopeType.OPERATIONAL}.issubset(scopes)


def test_named_company_supply_chain_keeps_company_and_operational_boundaries():
    result = _understand("Analyze Apple's supply chain.")
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert ScopeType.COMPANY in scopes
    assert ScopeType.OPERATIONAL in scopes
    assert "Apple" in result.scope_classification.scope_subjects


def test_scope_context_projects_physical_commerce_to_commercial_world():
    result = _understand("How does oil affect transportation costs?")
    contexts = {item.context_type for item in result.scope_context.contexts}
    assert ScopeContextType.COMMERCIAL in contexts
    assert ScopeContextType.OPERATIONAL in contexts
    assert result.scope_context.cross_domain


def test_contextual_follow_up_reuses_previous_scope_without_replacing_domain():
    engine = DomainUnderstandingEngine()
    previous = engine.understand("Research crude oil futures.")
    result = engine.understand(
        "How does this affect airline costs?",
        context=DomainContext(previous_result=previous),
    )
    assert result.scope_classification.primary_scope == ScopeType.CROSS_DOMAIN
    assert ScopeType.FINANCIAL_MARKET in result.scope_classification.secondary_scopes


# 9. False-Positive Protection


@pytest.mark.parametrize(
    ("text", "forbidden"),
    [
        ("I went to the bank.", ScopeType.FINANCIAL_MARKET),
        ("My company has a stockroom.", ScopeType.FINANCIAL_MARKET),
        ("The market near my house is busy.", ScopeType.FINANCIAL_MARKET),
        ("The company sells oil.", ScopeType.FINANCIAL_MARKET),
        ("Apple", ScopeType.COMPANY),
    ],
)
def test_generic_words_do_not_force_a_financial_or_company_scope(text, forbidden):
    result = _understand(text)
    scopes = {
        result.scope_classification.primary_scope,
        *result.scope_classification.secondary_scopes,
    }
    assert forbidden not in scopes


# 10. Natural Language


def test_conversational_forms_preserve_supported_scope():
    cases = {
        "What's happening with oil?": ScopeType.ASSET,
        "What's going on with gold?": ScopeType.ASSET,
        "How is the Nigerian economy doing?": ScopeType.ECONOMIC,
        "What about Apple's business?": ScopeType.COMPANY,
        "Check EURUSD.": ScopeType.FINANCIAL_MARKET,
        "Look into crude oil supply.": ScopeType.PHYSICAL_COMMERCE,
        "What's happening in the market?": ScopeType.UNKNOWN,
        "Tell me about the oil business.": ScopeType.BUSINESS,
    }
    for text, expected in cases.items():
        assert _understand(text).scope_classification.primary_scope == expected


def test_unclear_slang_does_not_invent_scope():
    result = _understand("abeg make we check am")
    assert result.scope_classification.primary_scope == ScopeType.UNKNOWN


# 11. Serialization / Models


def test_scope_result_serializes_to_json_and_preserves_hierarchy_and_evidence():
    result = _understand("How did Apple's stock react to earnings?")
    payload = result.to_dict()
    json.dumps(payload)
    assert (
        payload["scope_classification"]["primary_scope"]
        == ScopeType.FINANCIAL_MARKET.value
    )
    assert payload["scope_detection"]["evidence"]
    assert payload["scope_hierarchy"]["paths"]
    assert payload["scope_context"]["contexts"]


def test_scope_components_are_independently_constructible():
    detector = ScopeDetector()
    detection = detector.detect("Analyze EURUSD.")
    classified = ScopeClassifier().classify(detection, text="Analyze EURUSD.")
    hierarchy = ScopeHierarchyResolver().resolve(classified)
    context = ScopeContextDetector().detect("Analyze EURUSD.")
    assert detection.evidence
    assert classified.primary_scope == ScopeType.FINANCIAL_MARKET
    assert hierarchy.paths
    assert context.contexts


# 12. Regression Tests


def test_scope_fields_do_not_remove_part1_domain_results():
    result = _understand("Analyze EURUSD.")
    assert result.detection.candidates
    assert result.classification.primary_domain == DomainType.MARKETS
    assert result.multi_domain.domains


def test_empty_input_has_empty_scope_without_crashing():
    result = _understand("")
    assert result.scope_classification.primary_scope == ScopeType.UNKNOWN
    assert result.scope_detection.evidence == ()
    assert result.scope_context.contexts == ()
