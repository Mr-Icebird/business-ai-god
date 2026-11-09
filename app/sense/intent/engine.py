from dataclasses import replace
import re

from app.sense.input.models import InputUnderstandingResult
from app.sense.intent.ambiguity.detector import AmbiguityDetector
from app.sense.intent.action.detector import ActionDetector
from app.sense.intent.confidence.calculator import IntentConfidenceCalculator
from app.sense.intent.constraints.detector import ConstraintDetector
from app.sense.intent.conversation.detector import ConversationIntentDetector
from app.sense.intent.conversation.models import IntentContext
from app.sense.intent.correction.detector import IntentCorrectionDetector
from app.sense.intent.correction.updater import IntentCorrectionUpdater
from app.sense.intent.decomposition.decomposer import TaskDecomposer
from app.sense.intent.detection.detector import IntentDetector
from app.sense.intent.goal.detector import GoalDetector
from app.sense.intent.models import Sense2Result, build_explanation
from app.sense.intent.question.detector import QuestionDetector
from app.sense.intent.subintent.detector import SubIntentDetector
from app.sense.intent.task.detector import TaskDetector


class IntentUnderstandingEngine:
    """Coordinates the independent SENSE-2 Part-1 and Part-2 detectors."""

    def __init__(
        self,
        intent_detector: IntentDetector | None = None,
        subintent_detector: SubIntentDetector | None = None,
        task_detector: TaskDetector | None = None,
        goal_detector: GoalDetector | None = None,
        action_detector: ActionDetector | None = None,
        question_detector: QuestionDetector | None = None,
        conversation_detector: ConversationIntentDetector | None = None,
        decomposer: TaskDecomposer | None = None,
        constraint_detector: ConstraintDetector | None = None,
        ambiguity_detector: AmbiguityDetector | None = None,
        confidence_calculator: IntentConfidenceCalculator | None = None,
        correction_detector: IntentCorrectionDetector | None = None,
        correction_updater: IntentCorrectionUpdater | None = None,
    ) -> None:
        self.intent_detector = intent_detector or IntentDetector()
        self.subintent_detector = subintent_detector or SubIntentDetector()
        self.task_detector = task_detector or TaskDetector()
        self.goal_detector = goal_detector or GoalDetector()
        self.action_detector = action_detector or ActionDetector()
        self.question_detector = question_detector or QuestionDetector()
        self.conversation_detector = conversation_detector or ConversationIntentDetector()
        self.decomposer = decomposer or TaskDecomposer()
        self.constraint_detector = constraint_detector or ConstraintDetector()
        self.ambiguity_detector = ambiguity_detector or AmbiguityDetector()
        self.confidence_calculator = confidence_calculator or IntentConfidenceCalculator()
        self.correction_detector = correction_detector or IntentCorrectionDetector()
        self.correction_updater = correction_updater or IntentCorrectionUpdater()

    def understand(
        self,
        value: str | InputUnderstandingResult,
        *,
        entity_mentions: tuple[str, ...] = (),
        context: IntentContext | None = None,
    ) -> Sense2Result:
        source_input = value if isinstance(value, InputUnderstandingResult) else None
        raw_text = source_input.raw_input if source_input else str(value)
        normalized_text = (
            source_input.normalized_text or raw_text
            if source_input else raw_text
        )
        prior_action = None
        prior_intent = None
        prior_goal = None
        prior_task = None
        prior_text = None
        if context is not None:
            if context.previous_result is not None:
                previous_result = context.previous_result
                prior_action = previous_result.action
                prior_intent = previous_result.intent
                prior_goal = previous_result.goal
                prior_task = previous_result.task
            else:
                prior_text = (
                    context.previous_input.normalized_text or context.previous_input.raw_input
                    if context.previous_input is not None
                    else context.previous_user_message
                )
                if prior_text:
                    prior_subintent = self.subintent_detector.detect(prior_text)
                    prior_action = self.action_detector.detect(prior_text)
                    prior_intent = self.intent_detector.detect(
                        prior_text, prior_subintent, prior_action
                    )
                    prior_goal = self.goal_detector.detect(prior_text)
                    prior_task = self.task_detector.detect(
                        prior_text, prior_subintent, prior_action,
                        context.previous_input,
                        context.previous_entity_mentions,
                    )
        context_subjects: tuple[str, ...] = ()
        if context is not None and re.search(r"\b(?:it|that|those|them)\b", normalized_text, re.IGNORECASE):
            if context.previous_entity_mentions:
                context_subjects = context.previous_entity_mentions
            elif prior_task is not None:
                context_subjects = prior_task.subject
        subintent = self.subintent_detector.detect(normalized_text)
        action = self.action_detector.detect(normalized_text)
        intent = self.intent_detector.detect(normalized_text, subintent, action)
        goal = self.goal_detector.detect(normalized_text)
        task = self.task_detector.detect(
            normalized_text, subintent, action, source_input, entity_mentions,
            context_subjects,
        )
        question = self.question_detector.detect(normalized_text)
        conversation = self.conversation_detector.detect(normalized_text, context)
        if (
            conversation.intent.value == "follow_up"
            and subintent.primary.value == "follow_up"
            and prior_task is not None
            and prior_task.operation
            and not action.actions
        ):
            action = prior_action
            intent = prior_intent
            goal = prior_goal if goal.primary.value == "unknown" else goal
            task = replace(
                task,
                task_type=prior_task.task_type,
                operation=prior_task.operation,
                constraints=tuple(dict.fromkeys(task.constraints + prior_task.constraints)),
                outputs=prior_task.outputs,
                completion_condition=prior_task.completion_condition,
            )
        decomposition = self.decomposer.decompose(normalized_text, task)
        constraints = self.constraint_detector.detect(normalized_text)
        if (
            conversation.intent.value == "follow_up"
            and context is not None
            and context.previous_result is not None
        ):
            constraints = self.constraint_detector.combine(
                context.previous_result.constraints,
                constraints,
                text=normalized_text,
            )
        result = Sense2Result(
            source_input=source_input,
            raw_text=raw_text,
            normalized_text=normalized_text,
            intent=intent,
            subintent=subintent,
            task=task,
            goal=goal,
            action=action,
            question=question,
            conversation=conversation,
            decomposition=decomposition,
            constraints=constraints,
        )
        correction = self.correction_detector.detect(normalized_text, result, context)
        result = self.correction_updater.update(result, context, correction)
        if correction.is_correction:
            decomposition_text = result.task.objective or normalized_text
            result = replace(
                result,
                decomposition=self.decomposer.decompose(decomposition_text, result.task),
            )
        ambiguity = self.ambiguity_detector.detect(
            normalized_text, result.intent, result.task, result.conversation, context
        )
        confidence = self.confidence_calculator.calculate(
            result.intent, result.subintent, result.task, result.goal,
            result.action, result.question, result.conversation, ambiguity,
        )
        result = replace(
            result,
            ambiguity=ambiguity,
            confidence=confidence,
            correction=correction,
            requires_clarification=ambiguity.requires_clarification,
        )
        return replace(result, explanation=build_explanation(result))


INTENT_SENSE = IntentUnderstandingEngine()