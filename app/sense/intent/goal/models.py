from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class UserGoal(str, Enum):
    LEARNING = "learning"
    RESEARCH = "research"
    TRADING_RESEARCH = "trading_research"
    INVESTMENT_RESEARCH = "investment_research"
    BUSINESS_RESEARCH = "business_research"
    CURRENT_INFORMATION = "current_information"
    MONITORING = "monitoring"
    DECISION_SUPPORT = "decision_support"
    GENERAL_CURIOSITY = "general_curiosity"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GoalDetectionResult:
    primary: UserGoal = UserGoal.UNKNOWN
    detected: tuple[UserGoal, ...] = field(default_factory=tuple)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN