from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class ActionType(str, Enum):
    EXPLAIN = "explain"
    CALCULATE = "calculate"
    RESEARCH = "research"
    COMPARE = "compare"
    ANALYZE = "analyze"
    PLAN = "plan"
    CREATE = "create"
    MODIFY = "modify"
    MONITOR = "monitor"
    ALERT = "alert"
    EXECUTE = "execute"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ActionDetectionResult:
    primary: ActionType = ActionType.UNKNOWN
    actions: tuple[ActionType, ...] = field(default_factory=tuple)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN