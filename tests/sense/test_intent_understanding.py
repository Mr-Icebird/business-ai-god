"""Authoritative regression suite for the complete SENSE-2 subsystem."""

import json
import re

import pytest

from app.sense.input.engine import INPUT_SENSE
from app.sense.intent.action.models import ActionType
from app.sense.intent.ambiguity.models import AmbiguityType
from app.sense.intent.confidence.models import ConfidenceAssessment
from app.sense.intent.constraints.detector import ConstraintDetector
from app.sense.intent.constraints.models import ConstraintType
from app.sense.intent.conversation.detector import ConversationIntentDetector
from app.sense.intent.conversation.models import ConversationIntent, IntentContext
from app.sense.intent.correction.models import CorrectionType
from app.sense.intent.decomposition.decomposer import TaskDecomposer
from app.sense.intent.detection.models import IntentType
from app.sense.intent.engine import IntentUnderstandingEngine
from app.sense.intent.goal.models import UserGoal
from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.question.detector import QuestionDetector
from app.sense.intent.question.models import QuestionType
from app.sense.intent.subintent.models import SubIntentType

# 1. Intent Detection


def test_primary_secondary_and_multi_intent_are_preserved():
    result = IntentUnderstandingEngine().understand(
        "Research why gold is falling today and compare it with oil."
    )
    assert (
        result.intent.primary_intent == IntentType.COMPARISON
        or result.intent.primary_intent == IntentType.RESEARCH
    )
    assert result.intent.multi_intent
    assert len(result.intent.secondary_intents) >= 1
    assert result.intent.hierarchy


def test_creation_of_research_plan_is_not_misread_as_research_action():
    result = IntentUnderstandingEngine().understand(
        "Create a trading research plan for gold."
    )
    assert result.intent.primary_intent == IntentType.CREATION
    assert SubIntentType.PLANNING in result.subintent.detected
    assert SubIntentType.RESEARCH not in result.subintent.detected
    assert result.action.primary == ActionType.CREATE
    assert ActionType.RESEARCH not in result.action.actions
    assert "gold" in result.task.subject


def test_building_a_strategy_preserves_creation_and_planning_intent():
    result = IntentUnderstandingEngine().understand("Build a trading strategy.")
    assert result.primary_intent == IntentType.CREATION
    assert IntentType.PLANNING in result.secondary_intents
    assert result.action.primary in {ActionType.CREATE, ActionType.PLAN}


# 2. Sub-Intent Detection


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("What is gold?", SubIntentType.INFORMATION),
        ("Analyze gold against oil.", SubIntentType.ANALYSIS),
        ("Research why gold moved today.", SubIntentType.RESEARCH),
        ("Explain how gold affects inflation.", SubIntentType.EXPLANATION),
        ("Compare gold and oil.", SubIntentType.COMPARISON),
        ("Calculate the return if gold rises 10%.", SubIntentType.CALCULATION),
        ("Predict the price next month.", SubIntentType.PREDICTION),
        ("Plan a trading research project.", SubIntentType.PLANNING),
        ("Should I invest in this fund?", SubIntentType.DECISION_SUPPORT),
        ("Monitor gold.", SubIntentType.MONITORING),
        ("Alert me when gold reaches $3,500.", SubIntentType.ALERT),
        ("Create a market report.", SubIntentType.CREATION),
        ("Modify the existing report.", SubIntentType.MODIFICATION),
        ("Correct that value.", SubIntentType.CORRECTION),
        ("Yes, that's right.", SubIntentType.CONFIRMATION),
        ("No, do not use that estimate.", SubIntentType.NEGATION),
        ("Could you clarify what you mean?", SubIntentType.CLARIFICATION),
        ("What about oil?", SubIntentType.FOLLOW_UP),
        ("Continue.", SubIntentType.CONTINUATION),
        ("Hello BAIG.", SubIntentType.GREETING),
        ("Goodbye for now.", SubIntentType.FAREWELL),
    ],
)
def test_supported_subintents(text, expected):
    result = IntentUnderstandingEngine().understand(text)
    assert result.subintent.primary == expected


# 3. Task Detection


def test_multi_operation_task_extracts_multiple_subjects_and_outputs():
    result = IntentUnderstandingEngine().understand(
        "Research why gold is falling today and compare it with oil."
    )
    assert {"gold", "oil"}.issubset(set(result.task.subject))
    assert ActionType.RESEARCH in result.task.operation
    assert ActionType.COMPARE in result.task.operation
    assert "research findings" in result.task.outputs
    assert "comparison" in result.task.outputs
    assert result.task.objective
    assert result.task.completion_condition


def test_task_constraints_are_retained():
    result = IntentUnderstandingEngine().understand(
        "Compare gold and oil using monthly returns, under $500."
    )
    assert "using monthly returns" in result.task.constraints
    assert "under $500" in result.task.constraints


def test_calculation_keeps_quantities_as_inputs_not_subjects():
    result = IntentUnderstandingEngine().understand("Calculate 5% of 200.")
    assert result.action.primary == ActionType.CALCULATE
    assert result.task.inputs
    assert not any(item in result.task.subject for item in ("5", "200"))


# 4. User Goal Detection


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Explain gold to me because I am learning about commodities.",
            UserGoal.LEARNING,
        ),
        (
            "Research gold because I am investigating a trading strategy.",
            UserGoal.TRADING_RESEARCH,
        ),
        (
            "Research this company for investment research.",
            UserGoal.INVESTMENT_RESEARCH,
        ),
        ("Research this market for business research.", UserGoal.BUSINESS_RESEARCH),
        ("Research gold.", UserGoal.RESEARCH),
        ("What is happening to gold today?", UserGoal.CURRENT_INFORMATION),
        ("Monitor this account.", UserGoal.MONITORING),
        ("Should I choose this option?", UserGoal.DECISION_SUPPORT),
        ("I am curious about gold.", UserGoal.GENERAL_CURIOSITY),
    ],
)
def test_goal_detection(text, expected):
    assert IntentUnderstandingEngine().understand(text).goal.primary == expected


def test_financial_topic_does_not_imply_trading_or_investment_goal():
    result = IntentUnderstandingEngine().understand("What is gold?")
    assert result.goal.primary == UserGoal.UNKNOWN


# 5. Action Detection


def test_why_question_does_not_invent_research_action_or_goal():
    result = IntentUnderstandingEngine().understand("Why did gold fall?")
    assert result.subintent.primary == SubIntentType.EXPLANATION
    assert result.action.actions == ()
    assert result.goal.primary == UserGoal.UNKNOWN


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Explain the result.", ActionType.EXPLAIN),
        ("Calculate the return.", ActionType.CALCULATE),
        ("Research gold.", ActionType.RESEARCH),
        ("Compare gold and oil.", ActionType.COMPARE),
        ("Analyze the report.", ActionType.ANALYZE),
        ("Plan a review.", ActionType.PLAN),
        ("Create a chart.", ActionType.CREATE),
        ("Modify the chart.", ActionType.MODIFY),
        ("Monitor the price.", ActionType.MONITOR),
        ("Alert me at the threshold.", ActionType.ALERT),
        ("Execute the trade.", ActionType.EXECUTE),
    ],
)
def test_action_detection(text, expected):
    assert expected in IntentUnderstandingEngine().understand(text).action.actions


def test_execution_request_is_an_intent_and_action_not_a_subintent():
    result = IntentUnderstandingEngine().understand("Execute the trade.")
    assert result.intent.primary_intent == IntentType.EXECUTION
    assert result.action.primary == ActionType.EXECUTE
    assert result.subintent.primary == SubIntentType.UNKNOWN


@pytest.mark.parametrize(
    ("text", "expected_intent", "expected_action"),
    [
        ("Execute this trade.", IntentType.EXECUTION, ActionType.EXECUTE),
        (
            "Why has gold been moving so much?",
            IntentType.EXPLANATION,
            ActionType.UNKNOWN,
        ),
        (
            "I need to know what is driving gold.",
            IntentType.INFORMATION,
            ActionType.UNKNOWN,
        ),
        (
            "Can you look into what happened to oil?",
            IntentType.RESEARCH,
            ActionType.RESEARCH,
        ),
        ("pls research btc", IntentType.RESEARCH, ActionType.RESEARCH),
        ("abeg check gold", IntentType.RESEARCH, ActionType.RESEARCH),
    ],
)
def test_indirect_and_colloquial_requests_keep_request_meaning(
    text, expected_intent, expected_action
):
    result = IntentUnderstandingEngine().understand(text)
    assert result.primary_intent == expected_intent
    assert result.action.primary == expected_action


@pytest.mark.parametrize(
    "text",
    [
        "I read a research report about gold.",
        "I compared these companies yesterday.",
        "I analyzed oil prices last week.",
        "I looked into the report yesterday.",
        "I researched gold yesterday.",
    ],
)
def test_completed_action_mentions_are_not_current_requests(text):
    result = IntentUnderstandingEngine().understand(text)
    assert result.action.actions == ()
    assert result.task.operation == ()
    assert result.task.subject == ()


def test_refinement_is_not_mislabeled_as_content_creation():
    result = IntentUnderstandingEngine().understand("Make it shorter.")
    assert result.conversation.intent == ConversationIntent.REFINEMENT
    assert result.action.primary == ActionType.MODIFY
    assert result.primary_intent.value != "creation"
    assert result.requires_clarification


# 6. Question Understanding


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("What is gold?", QuestionType.WHAT),
        ("Why did gold fall?", QuestionType.WHY),
        ("How does inflation affect rates?", QuestionType.HOW),
        ("When did oil prices rise?", QuestionType.WHEN),
        ("Where is the company headquartered?", QuestionType.WHERE),
        ("Who owns the company?", QuestionType.WHO),
        ("Which market is affected?", QuestionType.WHICH),
        ("How much did revenue increase?", QuestionType.HOW_MUCH),
        ("How many units were sold?", QuestionType.HOW_MANY),
        ("If rates rise, what happens to gold?", QuestionType.CONDITIONAL),
    ],
)
def test_question_types(text, expected):
    result = QuestionDetector().detect(text)
    assert result.question_type == expected
    assert result.is_question


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Can you explain why gold fell?", QuestionType.WHY),
        ("Tell me how inflation affects businesses.", QuestionType.HOW),
        ("I want to know when the company reported the result.", QuestionType.WHEN),
        ("I'd like to know where the office is.", QuestionType.WHERE),
    ],
)
def test_indirect_question_types(text, expected):
    assert QuestionDetector().detect(text).question_type == expected


@pytest.mark.parametrize(
    "text",
    [
        "What happens if rates fall?",
        "What would happen if rates fall?",
    ],
)
def test_trailing_conditional_question_is_classified_as_conditional(text):
    assert QuestionDetector().detect(text).question_type == QuestionType.CONDITIONAL


def test_conditional_question_does_not_collapse_to_information_intent():
    result = IntentUnderstandingEngine().understand("What would happen if rates fall?")
    assert result.question.question_type == QuestionType.CONDITIONAL
    assert result.primary_intent.value == "prediction"


def test_question_statement_and_unknown_type_are_distinguished():
    detector = QuestionDetector()
    statement = detector.detect("I know why gold fell.")
    unknown = detector.detect("Is gold rising?")
    assert not statement.is_question
    assert statement.question_type == QuestionType.UNKNOWN
    assert unknown.is_question
    assert unknown.question_type == QuestionType.UNKNOWN
    assert unknown.question_confidence == ConfidenceLevel.LOW


def test_non_question_exclamation_is_not_misclassified_as_what_question():
    result = QuestionDetector().detect("What a day!")
    assert not result.is_question
    assert result.question_type == QuestionType.UNKNOWN


def test_multiple_question_cues_preserve_ambiguity():
    result = QuestionDetector().detect("When and where did the company report?")
    assert result.question_type == QuestionType.WHEN
    assert result.question_ambiguity.is_ambiguous
    assert result.question_ambiguity.candidates == (
        QuestionType.WHEN,
        QuestionType.WHERE,
    )


def test_question_confidence_and_span_are_represented():
    result = QuestionDetector().detect("Why did gold fall?")
    assert result.question_confidence == ConfidenceLevel.HIGH
    assert result.source_span is not None
    assert result.matched_text == "Why"


def test_question_is_new_request_but_plain_statement_is_unknown():
    detector = ConversationIntentDetector()
    assert detector.detect("What is gold?").intent == ConversationIntent.NEW_REQUEST
    assert detector.detect("Gold fell today.").intent == ConversationIntent.UNKNOWN
    assert (
        detector.detect("I finished my research yesterday.").intent
        == ConversationIntent.UNKNOWN
    )
    assert (
        detector.detect("I want to know when the company reported results.").intent
        == ConversationIntent.NEW_REQUEST
    )


# 7. Conversation Intent


def test_ambiguous_deictic_question_is_clarification_with_context():
    result = ConversationIntentDetector().detect(
        "Can you explain that?", IntentContext(previous_user_message="Research gold.")
    )
    assert result.intent == ConversationIntent.CLARIFICATION


def test_topical_explanation_question_is_not_a_contextual_clarification():
    previous = IntentUnderstandingEngine().understand("Research oil.")
    result = IntentUnderstandingEngine().understand(
        "Can you explain why gold fell?",
        context=IntentContext(previous_result=previous),
    )
    assert result.conversation.intent == ConversationIntent.NEW_REQUEST


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Research gold.", ConversationIntent.NEW_REQUEST),
        ("What about oil?", ConversationIntent.FOLLOW_UP),
        ("Continue the research.", ConversationIntent.CONTINUATION),
        ("Can you explain that?", ConversationIntent.UNKNOWN),
        ("I meant Brent, not WTI.", ConversationIntent.CORRECTION),
        ("Yes, that's what I meant.", ConversationIntent.CONFIRMATION),
        ("No.", ConversationIntent.NEGATION),
        ("No, don't do that.", ConversationIntent.REJECTION),
        ("Make it shorter.", ConversationIntent.REFINEMENT),
        ("Actually, forget gold. Let's look at oil.", ConversationIntent.TOPIC_SWITCH),
    ],
)
def test_conversation_intents(text, expected):
    result = ConversationIntentDetector().detect(text)
    assert result.intent == expected


def test_follow_up_uses_available_previous_context():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research gold.")
    result = engine.understand(
        "What about oil?",
        context=IntentContext(
            previous_result=previous, previous_user_message="Research gold."
        ),
    )
    assert result.conversation.intent == ConversationIntent.FOLLOW_UP
    assert result.conversation.related_to_previous
    assert result.conversation.previous_interpretation == "Research gold."
    assert result.task.subject == ("oil",)
    assert result.action.primary == ActionType.RESEARCH
    assert result.decomposition.plan.tasks[0].subject == ("oil",)


def test_follow_up_preserves_prior_typed_task_constraints():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research gold using official sources only.")
    result = engine.understand(
        "What about oil?", context=IntentContext(previous_result=previous)
    )
    assert any(
        item.value == "using official sources only"
        for item in result.constraints.constraints
    )


def test_previous_message_only_can_supply_follow_up_operation():
    result = IntentUnderstandingEngine().understand(
        "What about oil?",
        context=IntentContext(previous_user_message="Research gold."),
    )
    assert result.conversation.intent == ConversationIntent.FOLLOW_UP
    assert result.task.operation == (ActionType.RESEARCH,)
    assert result.task.subject == ("oil",)
    assert not result.requires_clarification


def test_explanation_follow_up_does_not_overwrite_current_intent_with_old_operation():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research Apple services revenue.")
    result = engine.understand(
        "Why did it do that?", context=IntentContext(previous_result=previous)
    )
    assert result.conversation.intent == ConversationIntent.FOLLOW_UP
    assert result.primary_intent.value == "explanation"
    assert result.task.subject == previous.task.subject


def test_now_compare_it_with_new_subject_resolves_both_comparison_entities():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research gold.")
    result = engine.understand(
        "Now compare it with silver.", context=IntentContext(previous_result=previous)
    )
    assert result.conversation.intent == ConversationIntent.FOLLOW_UP
    assert result.action.primary == ActionType.COMPARE
    assert {"gold", "silver"}.issubset(set(result.task.subject))


def test_continuation_keeps_previous_context_link():
    previous = IntentUnderstandingEngine().understand("Research gold.")
    result = IntentUnderstandingEngine().understand(
        "Continue the research.",
        context=IntentContext(previous_result=previous),
    )
    assert result.conversation.intent == ConversationIntent.CONTINUATION
    assert result.conversation.related_to_previous
    assert result.conversation.previous_interpretation == "Research gold."


def test_topic_switch_exposes_old_and_new_topics():
    result = ConversationIntentDetector().detect(
        "Actually, forget gold. Let's look at oil.",
        IntentContext(previous_user_message="Research gold."),
    )
    assert result.topic_switch_from == "gold"
    assert result.topic_switch_to == "oil"
    assert result.related_to_previous


def test_contextless_first_message_is_supported():
    result = IntentUnderstandingEngine().understand("Research gold.")
    assert result.conversation.intent == ConversationIntent.NEW_REQUEST
    assert not result.conversation.context_available


def test_previous_input_can_supply_conversation_context():
    from app.sense.input.engine import INPUT_SENSE

    previous_input = INPUT_SENSE.understand("Research oil.")
    result = ConversationIntentDetector().detect(
        "What about gold?", IntentContext(previous_input=previous_input)
    )
    assert result.context_available
    assert result.previous_interpretation == "Research oil."


# 8. Multi-Task Decomposition


def test_single_task_decomposition():
    plan = (
        TaskDecomposer()
        .decompose(
            "Research gold.",
            IntentUnderstandingEngine().understand("Research gold.").task,
        )
        .plan
    )
    assert len(plan.tasks) == 1
    assert not plan.is_multi_task


def test_independent_research_tasks_are_parallelizable():
    result = IntentUnderstandingEngine().understand("Research gold and research oil.")
    plan = result.decomposition.plan
    assert len(plan.tasks) == 2
    assert all(not task.dependencies for task in plan.tasks)
    assert plan.parallel_groups == (("task-1", "task-2"),)
    assert all(task.parallelizable for task in plan.tasks)


def test_sequential_calculation_then_explanation_has_dependency():
    result = IntentUnderstandingEngine().understand(
        "Calculate my return and then explain whether the result is good."
    )
    plan = result.decomposition.plan
    assert [task.operation for task in plan.tasks] == [
        ActionType.CALCULATE,
        ActionType.EXPLAIN,
    ]
    assert plan.tasks[1].dependencies == ("task-1",)
    assert plan.dependencies[0].depends_on == "task-1"


def test_multi_intent_decomposition_preserves_parallel_inputs_and_synthesis():
    result = IntentUnderstandingEngine().understand(
        "Research oil supply, research demand, compare them, then explain the effect on prices."
    )
    tasks = result.decomposition.plan.tasks
    assert [task.operation for task in tasks] == [
        ActionType.RESEARCH,
        ActionType.RESEARCH,
        ActionType.COMPARE,
        ActionType.EXPLAIN,
    ]
    assert {"oil supply", "demand"}.issubset(set(tasks[2].subject))
    assert set(tasks[2].dependencies) == {"task-1", "task-2"}
    assert set(tasks[3].dependencies) == {"task-3"}


def test_unrelated_tasks_are_not_given_invented_dependencies():
    plan = (
        IntentUnderstandingEngine()
        .understand("Research gold and explain inflation.")
        .decomposition.plan
    )
    assert len(plan.tasks) == 2
    assert all(not item.dependencies for item in plan.tasks)
    assert plan.parallel_groups == (("task-1", "task-2"),)


def test_research_comparison_and_report_form_ordered_plan():
    result = IntentUnderstandingEngine().understand(
        "Research gold, compare it with oil, and create a report."
    )
    plan = result.decomposition.plan
    assert [task.operation for task in plan.tasks] == [
        ActionType.RESEARCH,
        ActionType.COMPARE,
        ActionType.CREATE,
    ]
    assert plan.tasks[1].dependencies == ("task-1",)
    assert plan.tasks[2].dependencies == ("task-1", "task-2")
    assert plan.is_multi_task


def test_plan_noun_in_created_research_plan_is_not_a_separate_task():
    plan = (
        IntentUnderstandingEngine()
        .understand("Create a trading research plan for gold.")
        .decomposition.plan
    )
    assert [task.operation for task in plan.tasks] == [ActionType.CREATE]


def test_mixed_research_analysis_comparison_is_decomposed():
    plan = (
        IntentUnderstandingEngine()
        .understand(
            "Research why gold fell, analyze the drivers, and compare it with oil."
        )
        .decomposition.plan
    )
    assert [task.operation for task in plan.tasks] == [
        ActionType.RESEARCH,
        ActionType.ANALYZE,
        ActionType.COMPARE,
    ]
    assert len(plan.tasks) == 3


def test_unresolved_sequence_is_marked_uncertain():
    plan = (
        IntentUnderstandingEngine()
        .understand("Research gold and then continue.")
        .decomposition.plan
    )
    assert plan.is_uncertain
    assert plan.uncertainty_reasons


# 9. Task Constraints


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Use 2025 data.", ConstraintType.TIME),
        ("Only look at the last 30 days.", ConstraintType.TIME),
        ("Use data before 2020.", ConstraintType.TIME),
        ("Look after the announcement.", ConstraintType.TIME),
        ("Use data within 3 months.", ConstraintType.TIME),
        ("Research in Nigeria.", ConstraintType.GEOGRAPHIC),
        ("For the US market.", ConstraintType.GEOGRAPHIC),
        ("African markets only.", ConstraintType.GEOGRAPHIC),
        ("Europe only.", ConstraintType.GEOGRAPHIC),
        ("Keep the budget under ₦50,000.", ConstraintType.FINANCIAL),
        ("Research with a $1,000 budget.", ConstraintType.FINANCIAL),
        ("Risk no more than 2%.", ConstraintType.FINANCIAL),
        ("Market cap above $1 billion.", ConstraintType.FINANCIAL),
        ("Use official sources only.", ConstraintType.DATA),
        ("Don't use social media.", ConstraintType.DATA),
        ("Use live data.", ConstraintType.DATA),
        ("Use the data I provided.", ConstraintType.DATA),
        ("Give me a table.", ConstraintType.OUTPUT_FORMAT),
        ("Return JSON.", ConstraintType.OUTPUT_FORMAT),
        ("Make it a PDF.", ConstraintType.OUTPUT_FORMAT),
        ("Keep it short.", ConstraintType.OUTPUT_FORMAT),
        ("Explain it like I'm 15.", ConstraintType.OUTPUT_FORMAT),
        ("Gold only.", ConstraintType.SCOPE),
        ("Don't include crypto.", ConstraintType.SCOPE),
        ("Compare only these two companies.", ConstraintType.SCOPE),
        ("Avoid making recommendations.", ConstraintType.USER_SPECIFIED),
        ("Do not use unverified estimates.", ConstraintType.USER_SPECIFIED),
        ("Focus on Nigeria.", ConstraintType.GEOGRAPHIC),
    ],
)
def test_constraint_types(text, expected):
    result = ConstraintDetector().detect(text)
    assert expected in {item.constraint_type for item in result.constraints}


def test_multiple_constraints_preserve_spans_and_hardness():
    result = ConstraintDetector().detect(
        "Use the last 30 days, in Nigeria, and return JSON only."
    )
    assert {item.constraint_type for item in result.constraints} >= {
        ConstraintType.TIME,
        ConstraintType.GEOGRAPHIC,
        ConstraintType.OUTPUT_FORMAT,
    }
    assert all(item.source_span and item.source_text for item in result.constraints)
    assert any(item.is_hard is True for item in result.constraints)


def test_explicit_live_and_historical_data_constraints_conflict():
    result = ConstraintDetector().detect("Use live data and historical data.")
    assert result.has_conflicts
    assert all(item.conflicts_with for item in result.constraints)


def test_inclusion_and_exclusion_constraints_conflict():
    result = ConstraintDetector().detect("Gold only, and don't include gold.")
    assert result.has_conflicts
    assert all(item.conflicts_with for item in result.constraints)


def test_no_constraints_is_an_empty_result():
    result = ConstraintDetector().detect("Explain gold.")
    assert result.constraints == ()
    assert not result.has_conflicts


def test_factual_geography_and_year_are_not_automatically_constraints():
    result = ConstraintDetector().detect("Revenue increased in Nigeria in 2025.")
    assert result.constraints == ()


def test_temporal_values_are_constraints_not_task_subjects():
    result = IntentUnderstandingEngine().understand(
        "Research gold prices in 2025 and compare them with 2024."
    )
    assert "gold prices" in result.task.subject
    assert "2025" not in " ".join(result.task.subject)
    assert "2024" not in " ".join(result.task.subject)
    assert {"2025", "2024"}.issubset(
        {
            re.search(r"20\d{2}", item.value).group()
            for item in result.constraints.constraints
            if re.search(r"20\d{2}", item.value)
        }
    )
    assert not result.constraints.has_conflicts
    assert not result.requires_clarification


def test_after_january_year_constraint_preserves_full_temporal_phrase():
    result = ConstraintDetector().detect("Use only information after January 2024.")
    assert any(
        "after january 2024" in item.value.casefold() for item in result.constraints
    )


# 10. Ambiguity


def test_comparison_pronoun_without_local_or_previous_target_requires_clarification():
    result = IntentUnderstandingEngine().understand("Compare it with silver.")
    assert result.requires_clarification
    assert result.ambiguity.primary_type.value in {
        "missing_task_information",
        "insufficient_context",
    }


def test_clear_and_missing_intent_are_distinguished():
    engine = IntentUnderstandingEngine()
    clear = engine.understand("Research gold.")
    missing = engine.understand("Gold, perhaps.")
    assert clear.ambiguity.primary_type == AmbiguityType.CLEAR_INTENT
    assert not clear.requires_clarification
    assert missing.ambiguity.primary_type == AmbiguityType.MISSING_INTENT
    assert missing.requires_clarification


def test_contextless_follow_up_has_multiple_intent_candidates():
    result = IntentUnderstandingEngine().understand("What about oil?")
    assert result.ambiguity.primary_type == AmbiguityType.AMBIGUOUS_INTENT
    issue = next(
        item
        for item in result.ambiguity.issues
        if item.ambiguity_type == AmbiguityType.AMBIGUOUS_INTENT
    )
    assert {"information", "analysis", "research"}.issubset(issue.candidates)
    assert result.requires_clarification
    assert result.confidence.primary_intent == ConfidenceLevel.LOW


def test_follow_up_with_previous_context_resolves_context_ambiguity():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research gold.")
    result = engine.understand(
        "What about oil?", context=IntentContext(previous_result=previous)
    )
    assert result.conversation.related_to_previous
    assert result.ambiguity.primary_type == AmbiguityType.CLEAR_INTENT


def test_conflicting_positive_and_negative_intent_is_exposed():
    result = IntentUnderstandingEngine().understand(
        "Research oil but don't research it."
    )
    assert result.ambiguity.primary_type == AmbiguityType.CONFLICTING_INTENT
    assert result.requires_clarification
    assert result.confidence.primary_intent == ConfidenceLevel.CONFLICTING
    assert result.confidence.ambiguity == ConfidenceLevel.CONFLICTING


def test_single_negated_operation_is_not_a_conflicting_intent():
    result = IntentUnderstandingEngine().understand("Don't research oil.")
    assert result.ambiguity.primary_type != AmbiguityType.CONFLICTING_INTENT


def test_opposite_operations_on_different_subjects_are_not_a_conflict():
    result = IntentUnderstandingEngine().understand(
        "Research oil but don't research gold."
    )
    assert result.ambiguity.primary_type != AmbiguityType.CONFLICTING_INTENT


def test_comparison_without_targets_requires_clarification():
    result = IntentUnderstandingEngine().understand("Compare these.")
    assert result.ambiguity.primary_type == AmbiguityType.MISSING_TASK_INFORMATION
    assert result.requires_clarification


def test_unresolved_reference_is_insufficient_context():
    result = IntentUnderstandingEngine().understand("What happened?")
    assert any(
        issue.ambiguity_type == AmbiguityType.INSUFFICIENT_CONTEXT
        for issue in result.ambiguity.issues
    )
    assert result.requires_clarification


@pytest.mark.parametrize("text", ["Research it.", "Analyze that.", "Compare those."])
def test_unresolved_task_pronouns_require_context(text):
    result = IntentUnderstandingEngine().understand(text)
    assert result.requires_clarification
    assert result.ambiguity.primary_type == AmbiguityType.MISSING_TASK_INFORMATION


def test_alternative_task_operations_are_marked_ambiguous():
    result = IntentUnderstandingEngine().understand("Research or analyze oil?")
    assert any(
        issue.ambiguity_type == AmbiguityType.AMBIGUOUS_TASK
        for issue in result.ambiguity.issues
    )
    assert result.requires_clarification


def test_unknown_input_is_not_given_false_confidence():
    result = IntentUnderstandingEngine().understand("Gold, perhaps.")
    assert result.subintent.primary == SubIntentType.UNKNOWN
    assert result.intent.primary_intent == IntentType.UNKNOWN
    assert result.intent.confidence == ConfidenceLevel.UNKNOWN
    assert result.intent.ambiguity.is_ambiguous


# 11. Confidence


def test_confidence_exposes_high_medium_low_unknown_and_conflicting():
    engine = IntentUnderstandingEngine()
    explicit = engine.understand("Research gold.")
    indirect_question = engine.understand("Can you explain why gold fell?")
    uncertain = engine.understand("What about oil?")
    unknown = engine.understand("Gold, perhaps.")
    conflict = engine.understand("Research gold but don't research it.")

    assert explicit.confidence.primary_intent == ConfidenceLevel.HIGH
    assert indirect_question.confidence.question_type == ConfidenceLevel.MEDIUM
    assert uncertain.confidence.primary_intent == ConfidenceLevel.LOW
    assert unknown.confidence.primary_intent == ConfidenceLevel.UNKNOWN
    assert conflict.confidence.primary_intent == ConfidenceLevel.CONFLICTING


def test_confidence_is_propagated_for_major_components():
    result = IntentUnderstandingEngine().understand("Research gold.")
    assert isinstance(result.confidence, ConfidenceAssessment)
    assert result.confidence.sub_intent == ConfidenceLevel.HIGH
    assert result.confidence.task == ConfidenceLevel.HIGH
    assert result.confidence.requested_action == ConfidenceLevel.HIGH
    assert result.confidence.conversation_intent != ConfidenceLevel.UNKNOWN


# 12. Correction & Updating


def test_correction_links_replacement_to_previous_task():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research WTI.")
    result = engine.understand(
        "I meant Brent.",
        context=IntentContext(
            previous_result=previous, previous_user_message="Research WTI."
        ),
    )
    correction = result.conversation.correction
    assert result.conversation.intent == ConversationIntent.CORRECTION
    assert result.conversation.related_to_previous
    assert correction.previous_value == "WTI"
    assert correction.replacement_value == "Brent"
    assert correction.previous_interpretation == "Research WTI."


def test_correction_without_context_does_not_invent_previous_interpretation():
    result = ConversationIntentDetector().detect("I meant Brent.")
    assert result.intent == ConversationIntent.CORRECTION
    assert not result.related_to_previous
    assert result.correction.relation == "unlinked_correction"
    assert result.correction.previous_interpretation is None


def test_intent_replacement_updates_task_operation():
    previous, updated = _correct(
        "Research oil prices.", "Actually, compare oil and gold."
    )
    assert updated.correction.correction_type == CorrectionType.INTENT_REPLACEMENT
    assert updated.task.operation == (ActionType.COMPARE,)
    assert updated.primary_intent == IntentType.COMPARISON
    assert previous.task.operation == (ActionType.RESEARCH,)


def test_refinement_updates_output_constraint_and_preserves_active_operation():
    previous, updated = _correct("Analyze Bitcoin.", "Make it shorter.")
    assert updated.correction.is_correction
    assert updated.correction.correction_type == CorrectionType.CONSTRAINT_MODIFICATION
    assert updated.task.operation == previous.task.operation
    assert updated.action == previous.action
    assert any(
        "shorter" in item.value.casefold() for item in updated.constraints.constraints
    )


def _correct(previous_text, current_text):
    engine = IntentUnderstandingEngine()
    previous = engine.understand(previous_text)
    current = engine.understand(
        current_text,
        context=IntentContext(
            previous_result=previous,
            previous_user_message=previous_text,
        ),
    )
    return previous, current


def test_correction_of_correction_updates_only_replaced_subject():
    engine = IntentUnderstandingEngine()
    first = engine.understand("Research gold.")
    second = engine.understand(
        "No, research silver.", context=IntentContext(previous_result=first)
    )
    third = engine.understand(
        "Actually, research copper.", context=IntentContext(previous_result=second)
    )
    assert third.correction.is_correction
    assert third.task.subject == ("copper",)
    assert third.task.operation == first.task.operation
    assert third.decomposition.plan.tasks[0].subject == ("copper",)


def test_owner_correction_replaces_entity_and_preserves_operation():
    previous, updated = _correct("Research gold.", "No, I meant silver.")
    assert updated.correction.is_correction
    assert updated.correction.correction_type == CorrectionType.TASK_MODIFICATION
    assert updated.task.subject == ("silver",)
    assert updated.task.operation == previous.task.operation == (ActionType.RESEARCH,)
    assert updated.primary_intent == previous.primary_intent == IntentType.RESEARCH
    assert updated.conversation.intent.value == "correction"
    assert updated.correction.previous_interpretation == previous.task.objective
    assert updated.decomposition.plan.tasks[0].subject == ("silver",)


def test_no_prefixed_imperative_can_correct_previous_subject():
    previous, updated = _correct("Research gold.", "No, research silver.")
    assert updated.correction.is_correction
    assert updated.task.operation == previous.task.operation
    assert updated.task.subject == ("silver",)
    assert updated.conversation.intent.value == "correction"


def test_time_constraint_correction_replaces_only_the_old_year():
    previous, updated = _correct("Research gold in 2025.", "Use 2024 instead.")
    assert updated.correction.correction_type == CorrectionType.CONSTRAINT_MODIFICATION
    values = [item.value for item in updated.constraints.constraints]
    assert any("2024" in value for value in values)
    assert not any("2025" in value for value in values)
    assert updated.task.subject == previous.task.subject
    assert updated.task.operation == previous.task.operation


def test_reinterpretation_drops_stale_analysis_action():
    previous, updated = _correct("Analyze Bitcoin.", "I only want the current price.")
    assert updated.correction.correction_type == CorrectionType.REINTERPRETATION
    assert previous.action.primary == ActionType.ANALYZE
    assert updated.action.primary == ActionType.UNKNOWN
    assert updated.task.operation == ()
    assert updated.task.subject == previous.task.subject
    assert updated.primary_intent == IntentType.INFORMATION
    assert not any(item.value == "I only" for item in updated.constraints.constraints)


def test_comparison_entity_correction_replaces_both_targets():
    previous, updated = _correct(
        "Compare Nigeria and Ghana.", "I meant Nigeria and Kenya."
    )
    assert updated.correction.is_correction
    assert set(previous.task.subject) == {"Nigeria", "Ghana"}
    assert set(updated.task.subject) == {"Nigeria", "Kenya"}
    assert updated.task.operation == previous.task.operation


def test_correction_preserves_unaffected_goal_and_constraints():
    previous, updated = _correct(
        "Research gold because I am learning, using official sources only.",
        "I meant silver.",
    )
    assert updated.task.subject == ("silver",)
    assert updated.goal == previous.goal
    assert updated.constraints.constraints == previous.constraints.constraints


def test_constraint_correction_preserves_other_constraints_of_same_type():
    previous, updated = _correct(
        "Research gold in 2025 with a $1,000 budget.",
        "Use 2024 instead.",
    )
    assert any("2024" in item.value for item in updated.constraints.constraints)
    assert any(
        "budget" in item.value.casefold() for item in updated.constraints.constraints
    )
    assert not any("2025" in item.value for item in updated.constraints.constraints)


def test_correction_marker_without_material_change_is_not_applied():
    previous, current = _correct("Research gold.", "Actually, I have another question.")
    assert not current.correction.is_correction
    assert current.task.subject != previous.task.subject or current.task.subject == ()


def test_no_without_correction_evidence_is_not_misclassified_as_correction():
    engine = IntentUnderstandingEngine()
    previous = engine.understand("Research gold.")
    result = engine.understand(
        "No, the price fell today.", context=IntentContext(previous_result=previous)
    )
    assert not result.correction.is_correction
    assert result.conversation.intent.value != "correction"


def test_correction_without_context_is_not_applied_as_an_update():
    result = IntentUnderstandingEngine().understand("I meant silver.")
    assert not result.correction.is_correction


def test_correction_can_use_previous_sense1_input_as_available_context():
    previous_input = INPUT_SENSE.understand("Research gold.")
    result = IntentUnderstandingEngine().understand(
        "I meant silver.",
        context=IntentContext(previous_input=previous_input),
    )
    assert result.correction.is_correction
    assert result.correction.previous_interpretation == "Research gold."


# 13. Output Contract


def test_output_contract_exposes_required_structured_fields():
    result = IntentUnderstandingEngine().understand(
        "Research why gold moved today and compare it with oil."
    )
    assert result.primary_intent == result.intent.primary_intent
    assert result.secondary_intents == result.intent.secondary_intents
    assert result.sub_intent is result.subintent
    assert result.objective == result.task.objective
    assert result.user_goal is result.goal
    assert result.requested_action is result.action
    assert result.question_type == result.question.question_type
    assert result.constraints is not None
    assert result.subtasks == result.decomposition.plan.tasks
    assert result.dependencies == result.decomposition.plan.dependencies
    assert result.ambiguity is not None
    assert result.confidence is not None
    assert isinstance(result.requires_clarification, bool)
    assert result.explanation.startswith("Intent:")


def test_serialized_contract_is_json_compatible_and_preserves_sense1_result():
    source = INPUT_SENSE.understand("Research gold at $2,500.")
    result = IntentUnderstandingEngine().understand(source)
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["source_input"]["raw_input"] == source.raw_input
    assert payload["primary_intent"] == result.primary_intent.value
    assert "ambiguity" in payload and "confidence" in payload


# 14. Cross-component / Integration Tests


def test_sense1_result_is_preserved_and_used_as_task_input():
    sense1 = INPUT_SENSE.understand("Research gold today at $3,500.")
    result = IntentUnderstandingEngine().understand(sense1)
    assert result.source_input is sense1
    assert result.raw_text == sense1.raw_input
    assert "today" in result.normalized_text.casefold()
    assert any("3,500" in value for value in result.task.inputs)


def test_negated_research_is_not_decomposed_as_an_executable_task():
    result = IntentUnderstandingEngine().understand(
        "Research gold but do not research it."
    )
    assert result.ambiguity.primary_type.value == "conflicting_intent"
    assert [task.operation for task in result.subtasks] == [ActionType.RESEARCH]


def test_task_constraints_and_decomposition_are_separate_results():
    result = IntentUnderstandingEngine().understand(
        "Research gold using official sources only."
    )
    assert result.constraints.constraints
    assert result.task.constraints == ("using official sources only",)
    assert result.decomposition.plan.tasks


def test_multitask_intent_and_decomposition_coexist():
    result = IntentUnderstandingEngine().understand(
        "Research gold and compare it with oil."
    )
    assert result.intent.multi_intent
    assert result.decomposition.plan.is_multi_task


def test_multitask_plan_confidence_and_ambiguity_coexist():
    result = IntentUnderstandingEngine().understand("Research or analyze oil?")
    assert result.decomposition.plan.is_multi_task
    assert result.confidence.task == ConfidenceLevel.LOW
    assert result.ambiguity.primary_type == AmbiguityType.AMBIGUOUS_TASK


def test_explicit_entity_mentions_can_be_integrated():
    result = IntentUnderstandingEngine().understand(
        "Compare these assets.", entity_mentions=("gold", "oil")
    )
    assert result.task.subject == ("gold", "oil")


def test_common_abbreviation_and_conjunction_variants_preserve_entities():
    result = IntentUnderstandingEngine().understand("can u compare gold n silver")
    assert result.action.primary == ActionType.COMPARE
    assert {"gold", "silver"}.issubset(result.task.subject)


def test_compound_research_and_explanation_keeps_both_operations():
    result = IntentUnderstandingEngine().understand(
        "Research gold and explain why it moved."
    )
    assert result.intent.multi_intent
    assert result.action.actions == (ActionType.RESEARCH, ActionType.EXPLAIN)


def test_part2_fields_coexist_with_part1_without_overwriting():
    result = IntentUnderstandingEngine().understand("Why did gold fall?")
    assert result.question.question_type == QuestionType.WHY
    assert result.intent.primary_intent.value == "explanation"
    assert result.action.actions == ()
    assert result.task is not None
    assert result.conversation.intent == ConversationIntent.NEW_REQUEST


def test_prior_entity_context_resolves_sense1_reference_without_modifying_sense1():
    result = IntentUnderstandingEngine().understand(
        "Why did it do that?",
        context=IntentContext(previous_entity_mentions=("Apple", "services revenue")),
    )
    assert result.task.subject == ("Apple", "services revenue")
    assert not result.requires_clarification


def test_sense1_previous_message_and_entity_mentions_resolve_follow_up_question():
    previous_input = INPUT_SENSE.understand("Apple increased services revenue.")
    result = IntentUnderstandingEngine().understand(
        "Why did it do that?",
        context=IntentContext(
            previous_input=previous_input,
            previous_entity_mentions=("Apple", "services revenue"),
        ),
    )
    assert result.conversation.related_to_previous
    assert result.task.subject == ("Apple", "services revenue")
    assert result.primary_intent.value == "explanation"
    assert not result.requires_clarification


def test_explicit_multiple_requests_are_preserved_not_collapsed():
    result = IntentUnderstandingEngine().understand(
        "Tell me about oil and research oil prices."
    )
    assert result.intent.multi_intent
    assert len(result.secondary_intents) >= 1
    assert result.ambiguity.primary_type == AmbiguityType.CLEAR_INTENT
