from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class ConstraintType(str, Enum):
    TIME = "time"
    GEOGRAPHIC = "geographic"
    FINANCIAL = "financial"
    DATA = "data"
    OUTPUT_FORMAT = "output_format"
    SCOPE = "scope"
    USER_SPECIFIED = "user_specified"


@dataclass(frozen=True)
class TaskConstraint:
    constraint_id: str
    constraint_type: ConstraintType
    value: str
    operator: str | None = None
    source_text: str = ""
    source_span: tuple[int, int] | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    is_hard: bool | None = None
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConstraintDetectionResult:
    constraints: tuple[TaskConstraint, ...] = field(default_factory=tuple)
    has_conflicts: bool = False