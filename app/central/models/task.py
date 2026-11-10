"""
BAIG Central System — Task and Workflow models.

Implements the task lifecycle described in the Central System specification
(Sections 7, 10 and 15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.central.models.authority import new_id


class TaskStatus(str, Enum):
    """Task lifecycle states aligned with the specification."""

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


@dataclass
class TaskTransition:
    """Record of a single status change."""

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
    dependencies: tuple[str, ...] = ()          # other task_ids that must complete first
    required_permissions: tuple[str, ...] = ()  # action names that need grants/approvals
    approval_category: Optional[str] = None
    authority_status: str = "none"              # recommendation / delegated / approval_required / granted
    environment: str = "development"
    payload: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    transitions: list[TaskTransition] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def transition(
        self,
        to_status: TaskStatus,
        actor: str,
        reason: str = "",
        references: Optional[dict] = None,
    ) -> None:
        """Record a status change with full audit information."""
        now = datetime.now(timezone.utc)
        self.transitions.append(
            TaskTransition(
                from_status=self.status,
                to_status=to_status,
                at=now,
                actor=actor,
                reason=reason,
                references=references or {},
            )
        )
        self.status = to_status
        self.updated_at = now

    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
        }


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
