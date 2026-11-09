from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import AmbiguityInfo, ConfidenceLevel


class IntentType(str, Enum):
    INFORMATION = "information"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    CALCULATION = "calculation"
    PREDICTION = "prediction"
    PLANNING = "planning"
    DECISION_SUPPORT = "decision_support"
    MONITORING = "monitoring"
    ALERT = "alert"
    CREATION = "creation"
    MODIFICATION = "modification"
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"
    CLARIFICATION = "clarification"
    FOLLOW_UP = "follow_up"
    CONTINUATION = "continuation"
    GREETING = "greeting"
    FAREWELL = "farewell"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentDetectionResult:
    primary_intent: IntentType = IntentType.UNKNOWN
    secondary_intents: tuple[IntentType, ...] = field(default_factory=tuple)
    multi_intent: bool = False
    hierarchy: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    ambiguity: AmbiguityInfo = AmbiguityInfo()