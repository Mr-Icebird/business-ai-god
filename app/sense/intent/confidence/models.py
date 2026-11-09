from dataclasses import dataclass, field

from app.sense.intent.models import ConfidenceLevel


@dataclass(frozen=True)
class InterpretationConfidence:
    interpretation: str
    confidence: ConfidenceLevel


@dataclass(frozen=True)
class ConfidenceAssessment:
    primary_intent: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    secondary_intents: tuple[InterpretationConfidence, ...] = field(default_factory=tuple)
    sub_intent: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    task: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    user_goal: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    requested_action: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    question_type: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    conversation_intent: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    ambiguity: ConfidenceLevel = ConfidenceLevel.UNKNOWN