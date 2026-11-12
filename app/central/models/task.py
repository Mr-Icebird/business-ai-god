"""
BAIG Central System — Task and Workflow models.

Implements the task lifecycle with stronger enforcement of
Section 2 and Final Specification invariants:

- No hidden / invalid transitions
- Every state change records actor, reason, time, previous and new state
- RECEIVED can move to BLOCKED or AWAITING_APPROVAL (lifecycle fix)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.central.models.authority import new_id


class TaskStatus(str, Enum):
    """Task lifecycle states aligned with the Final Specification."""

    RECEIVED = "received"
    VALIDATING = "validating"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# Allowed transitions (from_status → set of allowed to_status)
# Fixed to support proper dependency and authorization gating
ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.RECEIVED: {
        TaskStatus.VALIDATING,
        TaskStatus.BLOCKED,              # Fixed: needed for dependency checks
        TaskStatus.AWAITING_APPROVAL,    # Fixed: needed for early authority checks
        TaskStatus.REJECTED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VALIDATING: {
        TaskStatus.PLANNED,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.BLOCKED,
        TaskStatus.REJECTED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PLANNED: {
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.READY,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.AWAITING_APPROVAL: {
        TaskStatus.READY,
        TaskStatus.REJECTED,
        TaskStatus.CANCELLED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.READY: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELLED,
        TaskStatus.PAUSED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
        TaskStatus.PAUSED,
        TaskStatus.RETRYING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.READY,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
        TaskStatus.VALIDATING,           # Allow re-validation after unblock
    },
    TaskStatus.PAUSED: {
        TaskStatus.READY,
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.RETRYING: {
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.BLOCKED,
    },
    # Terminal states — no further transitions allowed
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.REJECTED: set(),
}


@dataclass
class TaskTransition:
    """Record of a single status change (supports traceability)."""

    from_status: TaskStatus
    to_status: TaskStatus
    at: datetime
    actor: str
    reason: str = ""
    references: dict = field(default_factory=dict)


@dataclass
class Task:
    """
    Tracked unit of work with scope, status, authority, dependencies and outcome.

    Enforces:
    - Stable ID
    - Recorded transitions with actor + reason + timestamp
    - Invalid transitions are rejected
    """

    task_id: str
    correlation_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.RECEIVED
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    assigned_component: Optional[str] = None
    parent_task_id: Optional[str] = None
    dependencies: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    approval_category: Optional[str] = None
    authority_status: str = "none"
    environment: str = "development"
    payload: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    transitions: list[TaskTransition] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def can_transition_to(self, to_status: TaskStatus) -> bool:
        """Return True if the transition is allowed."""
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        return to_status in allowed

    def transition(
        self,
        to_status: TaskStatus,
        actor: str,
        reason: str = "",
        references: Optional[dict] = None,
    ) -> None:
        """
        Record a status change with full audit information.

        Raises ValueError if the transition is not allowed.
        This enforces the "No hidden transition" invariant.
        """
        if not actor:
            raise ValueError("Transition actor is required.")

        if not self.can_transition_to(to_status):
            raise ValueError(
                f"Invalid transition: {self.status.value} → {to_status.value} "
                f"is not allowed for task {self.task_id}."
            )

        now = datetime.now(timezone.utc)

        self.transitions.append(
            TaskTransition(
                from_status=self.status,
                to_status=to_status,
                at=now,
                actor=actor,
                reason=reason or "No reason provided",
                references=references or {},
            )
        )

        self.status = to_status
        self.updated_at = now

    def is_terminal(self) -> bool:
        """Return True if the task is in a final state."""
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
        }

    def is_active(self) -> bool:
        """Return True if the task can still make progress."""
        return not self.is_terminal()


@dataclass
class Workflow:
    """Ordered or branched collection of related tasks."""

    workflow_id: str
    title: str
    correlation_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    task_ids: list[str] = field(default_factory=list)
    status: str = "active"  # active / completed / failed / cancelled
    metadata: dict = field(default_factory=dict)


def create_task(
    title: str,
    correlation_id: Optional[str] = None,
    description: str = "",
    priority: TaskPriority = TaskPriority.NORMAL,
    created_by: str = "system",
    required_permissions: tuple[str, ...] = (),
    approval_category: Optional[str] = None,
    environment: str = "development",
    payload: Optional[dict] = None,
    parent_task_id: Optional[str] = None,
) -> Task:
    """Factory for a new Task with generated identifiers."""
    task_id = new_id("task_")
    return Task(
        task_id=task_id,
        correlation_id=correlation_id or new_id("corr_"),
        title=title,
        description=description,
        priority=priority,
        created_by=created_by,
        required_permissions=required_permissions,
        approval_category=approval_category,
        environment=environment,
        payload=payload or {},
        parent_task_id=parent_task_id,
    )
