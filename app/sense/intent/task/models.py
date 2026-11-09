from dataclasses import dataclass, field

from app.sense.intent.action.models import ActionType
from app.sense.intent.subintent.models import SubIntentType


@dataclass(frozen=True)
class TaskDetectionResult:
    task_type: tuple[SubIntentType, ...] = field(default_factory=tuple)
    objective: str | None = None
    subject: tuple[str, ...] = field(default_factory=tuple)
    operation: tuple[ActionType, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    inputs: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    completion_condition: str | None = None