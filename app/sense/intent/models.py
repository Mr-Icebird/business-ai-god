from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.sense.input.models import InputUnderstandingResult
    from app.sense.intent.action.models import ActionDetectionResult
    from app.sense.intent.ambiguity.models import AmbiguityResult
    from app.sense.intent.constraints.models import ConstraintDetectionResult
    from app.sense.intent.conversation.models import ConversationDetectionResult
    from app.sense.intent.confidence.models import ConfidenceAssessment
    from app.sense.intent.correction.models import CorrectionDetectionResult
    from app.sense.intent.decomposition.models import DecompositionResult
    from app.sense.intent.decomposition.models import SubTask, TaskDependency
    from app.sense.intent.detection.models import IntentDetectionResult
    from app.sense.intent.detection.models import IntentType
    from app.sense.intent.goal.models import GoalDetectionResult
    from app.sense.intent.question.models import QuestionDetectionResult
    from app.sense.intent.question.models import QuestionType
    from app.sense.intent.subintent.models import SubIntentDetectionResult
    from app.sense.intent.task.models import TaskDetectionResult


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class AmbiguityInfo:
    is_ambiguous: bool = False
    candidates: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True)
class Sense2Result:
    """Complete SENSE-2 intent result with component-level outputs preserved."""

    source_input: InputUnderstandingResult | None
    raw_text: str
    normalized_text: str
    intent: IntentDetectionResult
    subintent: SubIntentDetectionResult
    task: TaskDetectionResult
    goal: GoalDetectionResult
    action: ActionDetectionResult
    question: QuestionDetectionResult | None = None
    conversation: ConversationDetectionResult | None = None
    decomposition: DecompositionResult | None = None
    constraints: ConstraintDetectionResult | None = None
    ambiguity: AmbiguityResult | None = None
    confidence: ConfidenceAssessment | None = None
    correction: CorrectionDetectionResult | None = None
    requires_clarification: bool = False
    explanation: str = ""

    @property
    def primary_intent(self) -> IntentType:
        return self.intent.primary_intent

    @property
    def secondary_intents(self) -> tuple[IntentType, ...]:
        return self.intent.secondary_intents

    @property
    def sub_intent(self) -> SubIntentDetectionResult:
        return self.subintent

    @property
    def objective(self) -> str | None:
        return self.task.objective

    @property
    def user_goal(self) -> GoalDetectionResult:
        return self.goal

    @property
    def requested_action(self) -> ActionDetectionResult:
        return self.action

    @property
    def question_type(self) -> QuestionType | None:
        return self.question.question_type if self.question else None

    @property
    def subtasks(self) -> tuple[SubTask, ...]:
        return self.decomposition.plan.tasks if self.decomposition else ()

    @property
    def dependencies(self) -> tuple[TaskDependency, ...]:
        return self.decomposition.plan.dependencies if self.decomposition else ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result while keeping nested interpretations structured."""
        return {
            "primary_intent": _serialize(self.primary_intent),
            "secondary_intents": _serialize(self.secondary_intents),
            "sub_intent": _serialize(self.sub_intent),
            "task": _serialize(self.task),
            "objective": self.objective,
            "user_goal": _serialize(self.user_goal),
            "requested_action": _serialize(self.requested_action),
            "question_type": _serialize(self.question_type),
            "constraints": _serialize(self.constraints),
            "subtasks": _serialize(self.subtasks),
            "dependencies": _serialize(self.dependencies),
            "ambiguity": _serialize(self.ambiguity),
            "confidence": _serialize(self.confidence),
            "correction": _serialize(self.correction),
            "requires_clarification": self.requires_clarification,
            "explanation": self.explanation,
            "source_input": _serialize(self.source_input),
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "question": _serialize(self.question),
            "conversation": _serialize(self.conversation),
            "decomposition": _serialize(self.decomposition),
        }


def build_explanation(result: Sense2Result) -> str:
    parts = [f"Intent: {result.primary_intent.value}."]
    if result.objective:
        parts.append(f"Task: {result.objective}")
    if result.confidence:
        parts.append(f"Confidence: {result.confidence.primary_intent.value}.")
    if result.ambiguity and result.ambiguity.is_ambiguous:
        parts.append(
            "Clarification is required."
            if result.requires_clarification
            else "Interpretation is ambiguous."
        )
    return " ".join(parts)


def _serialize(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _serialize(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


SenseIntentResult = Sense2Result
