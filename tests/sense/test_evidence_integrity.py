import json

import pytest

from app.sense.domain.detection.models import DomainSignal
from app.sense.domain.evidence import validate_source_span
from app.sense.domain.models import DomainConfidence, DomainType, EvidenceProvenance
from app.sense.domain.scope.models import ScopeEvidence, ScopeType
from app.sense.engine import SenseEngine


def _sense(text, previous=None):
    return SenseEngine().understand(text, previous_result=previous)


def _assert_span(source_text, span, expected=None):
    validate_source_span(source_text, span, expected)


def _assert_current_source_evidence(result):
    current_text = result.domain_sense.normalized_text
    for signal in result.domain_sense.detection.signals:
        if signal.source_span is not None:
            assert signal.provenance == EvidenceProvenance.SOURCE_TEXT
            assert signal.source_text == current_text
            _assert_span(signal.source_text, signal.source_span, signal.evidence)

    for evidence in result.domain_sense.scope_detection.evidence:
        if evidence.provenance == EvidenceProvenance.SOURCE_TEXT:
            assert evidence.source_span is not None
            assert evidence.source_text == current_text
            _assert_span(evidence.source_text, evidence.source_span, evidence.evidence)
        elif evidence.source_span is not None:
            _assert_span(evidence.source_text, evidence.source_span, evidence.evidence)

    for relationship in result.domain_sense.scope_classification.relationships:
        if relationship.source_span is not None:
            _assert_span(
                relationship.source_text,
                relationship.source_span,
                relationship.evidence,
            )

    for boundary in result.domain_sense.scope_classification.boundaries:
        if boundary.source_span is not None:
            _assert_span(
                boundary.source_text,
                boundary.source_span,
                boundary.evidence,
            )

    for context in result.domain_sense.scope_context.contexts:
        if context.source_span is not None:
            _assert_span(context.source_text, context.source_span, context.evidence)

    for path in result.domain_sense.scope_hierarchy.paths:
        for node in path.nodes:
            if node.source_span is not None:
                _assert_span(node.source_text, node.source_span)

    for relationship in result.domain_sense.domain_relationships:
        if relationship.source_span is not None:
            _assert_span(
                relationship.source_text,
                relationship.source_span,
                relationship.evidence,
            )

    for interaction in result.domain_sense.multi_domain.interactions:
        _assert_span(
            interaction.source_text,
            interaction.source_span,
            interaction.evidence,
        )

    for unresolved in result.domain_sense.scope_classification.unresolved_relationships:
        for source_text, span in zip(unresolved.source_texts, unresolved.source_spans):
            _assert_span(source_text, span)


@pytest.mark.parametrize(
    ("span", "evidence"),
    [
        ((-1, 1), "a"),
        ((1, 1), ""),
        ((1, 4), "bc"),
        ((0, 4), "abcd"),
    ],
)
def test_invalid_or_mismatched_spans_are_rejected(span, evidence):
    with pytest.raises(ValueError):
        ScopeEvidence(
            ScopeType.ASSET,
            evidence,
            "explicit_scope_cue",
            DomainConfidence.HIGH,
            source_span=span,
            source_text="abc",
        )


def test_spans_require_their_declared_source_text():
    with pytest.raises(ValueError, match="requires its source text"):
        DomainSignal(
            DomainType.COMMODITIES,
            "oil",
            "commodity_term",
            DomainConfidence.HIGH,
            source_span=(0, 3),
        )


def test_repeated_terms_keep_distinct_exact_half_open_spans():
    text = "Analyze oil prices and oil prices."
    result = _sense(text)
    evidence = [
        item
        for item in result.domain_sense.scope_detection.evidence
        if item.scope_type == ScopeType.FINANCIAL_MARKET
        and item.evidence == "oil prices"
    ]

    assert [item.source_span for item in evidence] == [(8, 18), (23, 33)]
    for item in evidence:
        assert item.source_text == text
        _assert_span(item.source_text, item.source_span, item.evidence)


def test_multiple_clauses_keep_relationship_spans_local_to_current_message():
    text = (
        "Compare Nigerian inflation with US interest rates. "
        "Analyze Tesla's operations and oil."
    )
    result = _sense(text)
    relationships = result.domain_sense.scope_classification.relationships

    comparison = next(item for item in relationships if item.relation == "compares")
    assert comparison.source_text == text
    assert text[slice(*comparison.source_span)] == comparison.evidence
    assert comparison.source_span[1] <= text.index(".")
    _assert_current_source_evidence(result)


def test_inherited_context_retains_its_own_source_and_provenance():
    previous = _sense("Oil prices affect transportation costs.")
    current_text = "How does it affect business operations?"
    result = _sense(current_text, previous)
    inherited = [
        item
        for item in result.domain_sense.scope_detection.evidence
        if item.provenance == EvidenceProvenance.UPSTREAM_CONTEXT
        and item.source == "previous_scope_context"
        and item.source_span is not None
    ]

    assert inherited
    assert all(
        item.source_text == previous.domain_sense.normalized_text for item in inherited
    )
    assert all(item.source_text != current_text for item in inherited)
    for item in inherited:
        _assert_span(item.source_text, item.source_span, item.evidence)
    _assert_current_source_evidence(result)


@pytest.mark.parametrize(
    ("previous_text", "current_text", "excluded_scopes", "excluded_terms"),
    [
        (
            "Analyze Apple's stock.",
            "I meant Apple's business operations, not its stock.",
            {ScopeType.FINANCIAL_MARKET, ScopeType.ASSET},
            {"stock"},
        ),
        (
            "Analyze gold futures.",
            "Actually, I mean physical gold.",
            {ScopeType.FINANCIAL_MARKET},
            {"futures"},
        ),
        (
            "Compare Nigerian inflation with US interest rates.",
            "Focus only on Nigerian inflation.",
            set(),
            {"US", "interest rates"},
        ),
        (
            "Analyze Tesla's operations and oil.",
            "Forget the oil part. Focus on Tesla's operations.",
            {ScopeType.ASSET},
            {"oil"},
        ),
    ],
)
def test_corrections_separate_active_evidence_from_history(
    previous_text, current_text, excluded_scopes, excluded_terms
):
    previous = _sense(previous_text)
    result = _sense(current_text, previous)
    domain_result = result.domain_sense
    active_scopes = {
        domain_result.scope_type,
        *domain_result.scope_classification.secondary_scopes,
    }

    assert domain_result.correction.detected
    assert not excluded_scopes.intersection(active_scopes)
    assert not any(
        term.casefold() in f"{item.evidence} {item.subject or ''}".casefold()
        for term in excluded_terms
        for item in domain_result.scope_detection.evidence
        if item.provenance == EvidenceProvenance.SOURCE_TEXT
    )
    assert all(
        item.provenance != EvidenceProvenance.UPSTREAM_CONTEXT
        or item.source_text != previous.domain_sense.normalized_text
        for item in domain_result.scope_detection.evidence
    )
    assert all(
        item.source_text == domain_result.normalized_text
        for item in domain_result.scope_detection.evidence
        if item.provenance == EvidenceProvenance.SOURCE_TEXT
    )
    assert domain_result.correction.previous_scope_evidence
    assert all(
        item.provenance
        in {EvidenceProvenance.HISTORICAL, EvidenceProvenance.INTERNAL_TAXONOMY}
        for item in domain_result.correction.previous_scope_evidence
    )
    for item in domain_result.correction.previous_scope_evidence:
        if item.source_span is not None:
            _assert_span(item.source_text, item.source_span, item.evidence)

    _assert_current_source_evidence(result)
    payload = result.to_dict()
    json.dumps(payload)
    serialized_history = payload["domain_sense"]["correction"]["history"]
    assert serialized_history
    assert serialized_history[-1]["evidence_provenance"] == "source_text"
    historical_items = serialized_history[-1]["previous_scope_evidence"]
    assert historical_items
    assert all(
        item["provenance"] == "historical"
        for item in historical_items
        if item["provenance"] != "internal_taxonomy"
    )


def test_focus_only_correction_keeps_only_the_current_subject_in_hierarchy():
    previous = _sense("Compare Nigerian inflation with US interest rates.")
    result = _sense("Focus only on Nigerian inflation.", previous).domain_sense

    assert result.correction.detected
    assert "US" not in result.scope_classification.scope_subjects
    assert "interest rates" not in result.scope_classification.scope_subjects
    assert all(
        node.source_text == result.normalized_text
        for path in result.scope_hierarchy.paths
        for node in path.nodes
        if node.source_span is not None
    )


def test_negated_corrected_scope_term_does_not_remain_ambiguous():
    previous = _sense("Analyze Apple's stock.")
    result = _sense(
        "I meant Apple's business operations, not its stock.", previous
    ).domain_sense

    assert not result.ambiguity.ambiguity_present
    assert "Unresolved scope term: stock" not in result.ambiguity.evidence


def test_taxonomy_and_hierarchy_relationship_provenance_remain_explicit():
    result = _sense("Analyze gold futures.")
    domain_result = result.domain_sense
    taxonomy_evidence = [
        item
        for item in domain_result.scope_detection.evidence
        if item.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
    ]

    assert taxonomy_evidence
    assert all(
        item.source_span is None and item.source_text is None
        for item in taxonomy_evidence
    )
    assert domain_result.scope_hierarchy.paths
    assert all(
        node.parent_provenance == EvidenceProvenance.INTERNAL_TAXONOMY
        for path in domain_result.scope_hierarchy.paths
        for node in path.nodes
    )
    assert all(
        node.provenance
        in {
            EvidenceProvenance.SOURCE_TEXT,
            EvidenceProvenance.INTERNAL_TAXONOMY,
        }
        for path in domain_result.scope_hierarchy.paths
        for node in path.nodes
    )
    assert all(
        node.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
        for node in domain_result.hierarchy.nodes
    )


def test_current_and_taxonomy_relationships_serialize_with_distinct_provenance():
    result = _sense("Analyze gold futures.")
    payload = result.to_dict()["domain_sense"]

    market_instrument = next(
        item
        for item in payload["scope_classification"]["relationships"]
        if item["relation"] == "market_instrument"
    )
    assert market_instrument["provenance"] == "source_text"
    assert market_instrument["source_text"] == result.domain_sense.normalized_text
    assert (
        market_instrument["source_text"][slice(*market_instrument["source_span"])]
        == market_instrument["evidence"]
    )
    taxonomy_relationships = [
        item
        for item in payload["domain_relationships"]
        if item["provenance"] == "internal_taxonomy"
    ]
    assert all(
        item["source_span"] is None and item["source_text"] is None
        for item in taxonomy_relationships
    )
