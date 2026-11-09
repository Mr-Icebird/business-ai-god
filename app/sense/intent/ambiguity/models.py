from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class AmbiguityType(str, Enum):
    CLEAR_INTENT = "clear_intent"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    MISSING_INTENT = "missing_intent"
    CONFLICTING_INTENT = "conflicting_intent"
    AMBIGUOUS_TASK = "ambiguous_task"
    MISSING_TASK_INFORMATION = "missing_task_information"
    INSUFFICIENT_CONTEXT = "insufficient_context"


@dataclass(frozen=True)
class AmbiguityIssue:
    ambiguity_type: AmbiguityType
    affected: str
    reason: str
    candidates: tuple[str, ...] = field(default_factory=tuple)
    source_span: tuple[int, int] | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    requires_clarification: bool = True


@dataclass(frozen=True)
class AmbiguityResult:
    primary_type: AmbiguityType = AmbiguityType.CLEAR_INTENT
    issues: tuple[AmbiguityIssue, ...] = field(default_factory=tuple)
    is_ambiguous: bool = False
    requires_clarification: bool = False