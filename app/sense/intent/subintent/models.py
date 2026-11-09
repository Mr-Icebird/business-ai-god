from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class SubIntentType(str, Enum):
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
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SubIntentDetectionResult:
    primary: SubIntentType = SubIntentType.UNKNOWN
    detected: tuple[SubIntentType, ...] = field(default_factory=tuple)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN