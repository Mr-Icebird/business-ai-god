from dataclasses import replace

import pytest

import app.sense.engine as sense_engine_module
from app.sense.domain.models import DomainConfidence
from app.sense.engine import SenseEngine
from app.sense.intent.ambiguity.models import (
    AmbiguityIssue as IntentAmbiguityIssue,
    AmbiguityType as IntentAmbiguityType,
)
from app.sense.models import ClarificationDimension

_SCENARIOS = (
    (
        "Analyze Apple's stock.",
        None,
        True,
        False,
        ("domain", "scope"),
    ),
    ("Analyze Apple.", None, True, False, ("domain", "scope")),
    ("Analyze gold futures.", None, False, False, ()),
    (
        "I meant Apple's business operations, not its stock.",
        "Analyze Apple's stock.",
        False,
        False,
        (),
    ),
    (
        "Focus only on Nigerian inflation.",
        "Compare Nigerian inflation with US interest rates.",
        True,
        True,
        ("intent",),
    ),
    (
        "Forget the oil part. Focus on Tesla's operations.",
        "Analyze Tesla's operations and oil.",
        False,
        True,
        (),
    ),
    ("Analyze Apple supply chain.", None, True, False, ("domain",)),
    ("Analyze crude oil prices.", None, True, False, ("scope",)),
    ("The farmer trades wheat.", None, True, True, ("intent",)),
    ("Analyze oil prices in Nigeria.", None, True, False, ("scope",)),
    ("Analyze Apple and oil.", None, True, False, ("domain", "scope")),
    (
        "Actually, Google shares are up.",
        "Analyze Apple's stock.",
        True,
        True,
        ("intent",),
    ),
    ("Actually, Google shares are up.", None, True, True, ("intent",)),
)


@pytest.mark.parametrize(
    ("message", "previous_message", "required", "sense2_required", "dimensions"),
    _SCENARIOS,
)
def test_thirteen_clarification_scenarios_at_top_level(
    message, previous_message, required, sense2_required, dimensions
):
    engine = SenseEngine()
    previous = engine.understand(previous_message) if previous_message else None

    result = engine.understand(message, previous_result=previous)
    serialized = result.to_dict()

    assert result.intent_sense.requires_clarification is sense2_required
    assert result.domain_sense.requires_clarification == (
        result.domain_sense.ambiguity.clarification_required
    )
    assert result.requires_clarification is required
    assert tuple(item.value for item in result.clarification_dimensions) == dimensions
    assert serialized["requires_clarification"] is required
    assert serialized["clarification_dimensions"] == list(dimensions)
    assert serialized["domain_sense"]["requires_clarification"] == (
        result.domain_sense.ambiguity.clarification_required
    )

    if required:
        assert result.clarification_issues
        assert result.clarification_questions
        assert result.clarification_question
        assert all(issue.question for issue in result.clarification_issues)
        assert serialized["clarification_question"] == result.clarification_question
    else:
        assert not result.clarification_issues
        assert not result.clarification_questions
        assert result.clarification_question is None
        assert serialized["clarification_question"] is None


def test_low_confidence_alone_does_not_require_clarification():
    result = SenseEngine().understand("Analyze the farmer trading wheat.")

    assert result.domain_sense.confidence.overall == DomainConfidence.LOW
    assert not result.domain_sense.ambiguity.clarification_required
    assert not result.requires_clarification
    assert result.clarification_question is None


def test_high_confidence_does_not_suppress_unresolved_ambiguity(monkeypatch):
    original_understand = sense_engine_module.DOMAIN_SENSE.understand

    def understand_with_high_confidence(*args, **kwargs):
        result = original_understand(*args, **kwargs)
        assert result.ambiguity.clarification_required
        return replace(
            result,
            confidence=replace(
                result.confidence,
                domain=DomainConfidence.HIGH,
                scope=DomainConfidence.HIGH,
                overall=DomainConfidence.HIGH,
            ),
        )

    monkeypatch.setattr(
        sense_engine_module.DOMAIN_SENSE,
        "understand",
        understand_with_high_confidence,
    )
    result = SenseEngine().understand("Analyze crude oil prices.")

    assert result.domain_sense.confidence.overall == DomainConfidence.HIGH
    assert result.domain_sense.ambiguity.clarification_required
    assert result.requires_clarification
    assert result.clarification_dimensions == (ClarificationDimension.SCOPE,)


def test_multiple_domain_and_scope_issues_remain_separate():
    result = SenseEngine().understand("Analyze Apple and oil.")

    assert result.clarification_dimensions == (
        ClarificationDimension.DOMAIN,
        ClarificationDimension.SCOPE,
    )
    assert [issue.dimension for issue in result.clarification_issues] == [
        ClarificationDimension.DOMAIN,
        ClarificationDimension.SCOPE,
    ]
    assert len(result.clarification_questions) == 2
    assert result.clarification_question.startswith("Please clarify each point:")
    assert result.clarification_issues[0].dimension == ClarificationDimension.DOMAIN
    assert result.clarification_issues[1].dimension == ClarificationDimension.SCOPE


def test_scope_correction_does_not_discard_an_independent_task_issue(monkeypatch):
    original_understand = sense_engine_module.INTENT_SENSE.understand

    def understand_with_independent_task_issue(*args, **kwargs):
        result = original_understand(*args, **kwargs)
        issue = IntentAmbiguityIssue(
            IntentAmbiguityType.AMBIGUOUS_TASK,
            "task.subject",
            "The requested subject is unclear.",
            ("inflation", "interest rates"),
        )
        return replace(
            result,
            ambiguity=replace(
                result.ambiguity,
                issues=result.ambiguity.issues + (issue,),
                is_ambiguous=True,
                requires_clarification=True,
            ),
            requires_clarification=True,
        )

    monkeypatch.setattr(
        sense_engine_module.INTENT_SENSE,
        "understand",
        understand_with_independent_task_issue,
    )
    engine = SenseEngine()
    previous = engine.understand("Compare Nigerian inflation with US interest rates.")
    result = engine.understand(
        "Focus only on Nigerian inflation.",
        previous_result=previous,
    )

    assert result.domain_sense.correction.detected
    assert result.intent_sense.requires_clarification
    assert any(
        issue.ambiguity_type == IntentAmbiguityType.MISSING_INTENT
        for issue in result.intent_sense.ambiguity.issues
    )
    assert result.clarification_dimensions == (
        ClarificationDimension.INTENT,
        ClarificationDimension.TASK,
    )
    assert len(result.clarification_issues) == 2
    assert result.clarification_issues[1].reason == (
        "The requested subject is unclear."
    )
    assert result.requires_clarification


def test_comparison_action_is_not_carried_to_a_single_corrected_subject():
    engine = SenseEngine()
    previous = engine.understand("Compare Nigerian inflation with US interest rates.")
    previous_payload = previous.to_dict()
    result = engine.understand(
        "Focus only on Nigerian inflation.",
        previous_result=previous,
    )

    assert previous.intent_sense.action.primary.value == "compare"
    assert result.intent_sense.action.primary.value == "unknown"
    assert result.intent_sense.task.operation == ()
    assert result.domain_sense.correction.detected
    assert result.intent_sense.requires_clarification
    assert result.requires_clarification
    assert result.clarification_dimensions == (ClarificationDimension.INTENT,)
    assert result.clarification_question == (
        "What would you like me to do with inflation?"
    )
    assert previous.to_dict() == previous_payload
    assert previous.intent_sense.action.primary.value == "compare"


def test_compare_continuation_is_supported_by_current_intent_evidence():
    engine = SenseEngine()
    previous = engine.understand("Compare Nigerian inflation with US interest rates.")
    result = engine.understand(
        "What about Japanese unemployment?",
        previous_result=previous,
    )

    assert result.intent_sense.action.primary.value == "compare"
    assert not result.intent_sense.requires_clarification
    assert not result.requires_clarification
    assert result.clarification_question is None


def test_analysis_action_carries_forward_for_a_matching_scope_correction():
    engine = SenseEngine()
    previous = engine.understand("Analyze Tesla's operations and oil.")
    result = engine.understand(
        "Forget the oil part. Focus on Tesla's operations.",
        previous_result=previous,
    )

    assert previous.intent_sense.action.primary.value == "analyze"
    assert result.domain_sense.correction.detected
    assert result.intent_sense.requires_clarification
    assert not result.requires_clarification
    assert not result.clarification_issues
    assert result.intent_sense.ambiguity.issues == (
        SenseEngine()
        .understand("Forget the oil part. Focus on Tesla's operations.")
        .intent_sense.ambiguity.issues
    )


def test_create_action_is_not_carried_to_a_subject_only_correction():
    engine = SenseEngine()
    previous = engine.understand("Build a website about Nigerian inflation.")
    result = engine.understand(
        "Focus only on Nigerian inflation.",
        previous_result=previous,
    )

    assert previous.intent_sense.action.primary.value == "create"
    assert result.domain_sense.correction.detected
    assert result.intent_sense.action.primary.value == "unknown"
    assert result.intent_sense.requires_clarification
    assert result.requires_clarification
    assert result.clarification_dimensions == (ClarificationDimension.INTENT,)


def test_blank_input_is_an_insufficient_input_no_question_outcome():
    result = SenseEngine().understand("   ")

    assert result.explanation == (
        "The message is empty; no clarification question can be grounded in "
        "its contents."
    )
    assert result.intent_sense.requires_clarification
    assert not result.requires_clarification
    assert not result.clarification_issues
    assert not result.clarification_questions
    assert result.clarification_question is None


def test_punctuation_only_input_does_not_become_clarification_evidence():
    result = SenseEngine().understand("...")

    assert result.intent_sense.requires_clarification
    assert not result.requires_clarification
    assert not result.clarification_issues
    assert not result.clarification_questions
    assert result.clarification_question is None


def test_clarification_serialization_preserves_reasons_and_evidence():
    result = SenseEngine().understand("Analyze crude oil prices.")
    payload = result.to_dict()
    serialized_issue = payload["clarification_issues"][0]

    assert payload["requires_clarification"] is True
    assert payload["clarification_dimensions"] == ["scope"]
    assert payload["clarification_question"] == result.clarification_question
    assert serialized_issue["dimension"] == "scope"
    assert serialized_issue["reason"] == result.clarification_issues[0].reason
    assert serialized_issue["question"] == result.clarification_issues[0].question
    assert serialized_issue["evidence"]
    for evidence in serialized_issue["evidence"]:
        assert evidence["text"] != "commodity domain"
        if evidence["source_span"] is not None:
            assert (
                evidence["source_text"][slice(*evidence["source_span"])]
                == evidence["text"]
            )


def test_serialization_preserves_each_clarification_issue_and_question():
    result = SenseEngine().understand("Analyze Apple and oil.")
    payload = result.to_dict()

    assert payload["requires_clarification"] == result.requires_clarification
    assert payload["clarification_dimensions"] == [
        item.value for item in result.clarification_dimensions
    ]
    assert payload["clarification_questions"] == list(result.clarification_questions)
    assert payload["clarification_question"] == result.clarification_question
    assert len(payload["clarification_issues"]) == len(result.clarification_issues)
    for serialized, issue in zip(
        payload["clarification_issues"], result.clarification_issues
    ):
        assert serialized["dimension"] == issue.dimension.value
        assert serialized["reason"] == issue.reason
        assert serialized["candidates"] == list(issue.candidates)
        assert serialized["question"] == issue.question
        assert len(serialized["evidence"]) == len(issue.evidence)
        for evidence_payload, evidence in zip(serialized["evidence"], issue.evidence):
            assert evidence_payload["text"] == evidence.text
            assert evidence_payload["component"] == evidence.component
            assert evidence_payload["source_span"] == (
                list(evidence.source_span) if evidence.source_span else None
            )
            assert evidence_payload["source_text"] == evidence.source_text
