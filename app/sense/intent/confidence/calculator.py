from app.sense.intent.ambiguity.models import AmbiguityType
from app.sense.intent.confidence.models import (
    ConfidenceAssessment,
    InterpretationConfidence,
)
from app.sense.intent.detection.models import IntentType
from app.sense.intent.models import ConfidenceLevel


class IntentConfidenceCalculator:
    """Maps observed detector evidence to categorical, non-probabilistic confidence."""

    def calculate(self, intent, subintent, task, goal, action, question,
                  conversation, ambiguity) -> ConfidenceAssessment:
        issue_types = {issue.ambiguity_type for issue in ambiguity.issues}
        conflicting = AmbiguityType.CONFLICTING_INTENT in issue_types
        uncertain = ambiguity.is_ambiguous

        primary = self._base(intent.confidence, intent.primary_intent == IntentType.UNKNOWN)
        if conflicting:
            primary = ConfidenceLevel.CONFLICTING
        elif uncertain and intent.primary_intent != IntentType.UNKNOWN:
            primary = ConfidenceLevel.LOW

        secondary = tuple(
            InterpretationConfidence(item.value, primary)
            for item in intent.secondary_intents
        )
        sub_confidence = self._base(
            subintent.confidence, subintent.primary.value == "unknown"
        )
        if conflicting:
            sub_confidence = ConfidenceLevel.CONFLICTING
        elif uncertain:
            sub_confidence = ConfidenceLevel.LOW

        has_task_evidence = bool(task.operation or task.task_type)
        task_confidence = (
            ConfidenceLevel.HIGH if has_task_evidence and not uncertain
            else ConfidenceLevel.LOW if has_task_evidence
            else ConfidenceLevel.UNKNOWN
        )
        goal_confidence = self._base(goal.confidence, goal.primary.value == "unknown")
        action_confidence = self._base(action.confidence, action.primary.value == "unknown")
        question_confidence = self._base(
            question.question_confidence,
            not question.is_question or question.question_type.value == "unknown",
        )
        conversation_confidence = self._base(
            conversation.confidence,
            conversation.intent.value == "unknown",
        )
        ambiguity_confidence = (
            ConfidenceLevel.CONFLICTING if conflicting
            else ConfidenceLevel.LOW if ambiguity.is_ambiguous
            else ConfidenceLevel.HIGH
        )
        return ConfidenceAssessment(
            primary_intent=primary,
            secondary_intents=secondary,
            sub_intent=sub_confidence,
            task=task_confidence,
            user_goal=goal_confidence,
            requested_action=action_confidence,
            question_type=question_confidence,
            conversation_intent=conversation_confidence,
            ambiguity=ambiguity_confidence,
        )

    @staticmethod
    def _base(value, unknown: bool) -> ConfidenceLevel:
        if unknown:
            return ConfidenceLevel.UNKNOWN
        return value