from dataclasses import dataclass, field

from app.sense.intent.action.models import ActionType
from app.sense.intent.models import ConfidenceLevel


@dataclass(frozen=True)
class SubTask:
    task_id: str
    description: str
    objective: str
    operation: ActionType
    subject: tuple[str, ...] = field(default_factory=tuple)
    inputs: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    ordering: int = 0
    parallelizable: bool = False
    completion_condition: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN


@dataclass(frozen=True)
class TaskDependency:
    task_id: str
    depends_on: str
    reason: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


@dataclass(frozen=True)
class TaskPlan:
    tasks: tuple[SubTask, ...] = field(default_factory=tuple)
    dependencies: tuple[TaskDependency, ...] = field(default_factory=tuple)
    parallel_groups: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    overall_objective: str | None = None
    completion_condition: str | None = None
    is_multi_task: bool = False
    is_uncertain: bool = False
    uncertainty_reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DecompositionResult:
    plan: TaskPlan = TaskPlan()