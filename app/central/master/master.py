"""
BAIG MASTER — Coordination & Operations Core

Implements the responsibilities defined in the Central System specification §7.
MASTER organizes work; it does not decide truth.

This version respects Section 2 principles:
- No hidden transitions
- Clear recording of actor and reason
- Safe handling of invalid transitions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.central.master.execution_control import AuthorizationDecision, ExecutionControlManager
from app.central.models.authority import new_id
from app.central.models.task import (
    Task,
    TaskPriority,
    TaskStatus,
    Workflow,
    create_task,
)


@dataclass
class ComponentInfo:
    """Runtime view of a registered component."""

    name: str
    display_name: str
    status: str = "planned"          # planned / initialized / operational / disabled / error
    capabilities: tuple[str, ...] = ()
    last_heartbeat: Optional[datetime] = None


class Master:
    """
    Central coordination and operations core.

    Responsibilities:
    - Route work and manage component handoffs
    - Maintain tasks, priorities, dependencies and status
    - Enforce permissions and approvals (via ExecutionControlManager)
    - Monitor health and produce operational records
    """

    def __init__(self):
        self.execution_control = ExecutionControlManager()
        self._tasks: dict[str, Task] = {}
        self._workflows: dict[str, Workflow] = {}
        self._components: dict[str, ComponentInfo] = {}
        self._register_core_components()

    # ------------------------------------------------------------------
    # Component registry
    # ------------------------------------------------------------------

    def _register_core_components(self) -> None:
        core = [
            ("sense", "SENSE", ("input_understanding", "intent", "domain_scope")),
            ("brain", "BRAIN", ("reasoning", "decision", "planning")),
            ("memory", "Memory System", ("conversation_memory",)),
            ("knowledge", "Knowledge System", ("methods", "validated_lessons")),
            ("entity", "Entity & World Intelligence", ("entity_resolution",)),
            ("research", "Research Engine", ("evidence_collection",)),
            ("analysis", "Universal Analysis Engine", ("analysis",)),
            ("hypothesis", "Hypothesis Engine", ("hypothesis_lifecycle",)),
            ("testing", "Testing Lab", ("validation", "backtest")),
            ("financial", "Financial Intelligence", ("portfolio", "transactions")),
            ("aaf", "Agent & Assistant Factory", ("agent_lifecycle",)),
            ("security", "Cybersecurity", ("threat_detection", "isolation")),
            ("bisg", "BISG", ("independent_recovery",)),
            ("software_dev", "Software Development", ("code_change", "deployment")),
        ]
        for name, display, caps in core:
            self._components[name] = ComponentInfo(
                name=name,
                display_name=display,
                status="operational" if name in ("sense", "brain") else "planned",
                capabilities=caps,
            )

    def get_component(self, name: str) -> Optional[ComponentInfo]:
        return self._components.get(name)

    def list_components(self) -> list[ComponentInfo]:
        return list(self._components.values())

    def set_component_status(self, name: str, status: str) -> bool:
        comp = self._components.get(name)
        if not comp:
            return False
        comp.status = status
        comp.last_heartbeat = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def create_task(
        self,
        title: str,
        *,
        correlation_id: Optional[str] = None,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: str = "system",
        required_permissions: tuple[str, ...] = (),
        approval_category: Optional[str] = None,
        environment: str = "development",
        payload: Optional[dict] = None,
        parent_task_id: Optional[str] = None,
        dependencies: tuple[str, ...] = (),
    ) -> Task:
        task = create_task(
            title=title,
            correlation_id=correlation_id,
            description=description,
            priority=priority,
            created_by=created_by,
            required_permissions=required_permissions,
            approval_category=approval_category,
            environment=environment,
            payload=payload,
            parent_task_id=parent_task_id,
        )
        task.dependencies = dependencies
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def transition_task(
        self,
        task_id: str,
        to_status: TaskStatus,
        actor: str,
        reason: str = "",
    ) -> Optional[Task]:
        """
        Attempt to change a task's status.
        Invalid transitions are rejected and logged as a failed attempt.
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None

        try:
            task.transition(to_status, actor=actor, reason=reason)
            return task
        except ValueError as e:
            # Invalid transition — do not change state
            # In a full system this would also be written to the audit log
            print(f"[MASTER] Transition rejected: {e}")
            return None

    # ------------------------------------------------------------------
    # Authorization gate (the critical safety path)
    # ------------------------------------------------------------------

    def authorize_task(self, task_id: str, actor: str, action: str) -> AuthorizationDecision:
        task = self._tasks.get(task_id)
        if task is None:
            return AuthorizationDecision(
                allowed=False,
                reason=f"Task {task_id} not found",
                actor=actor,
                action=action,
            )
        return self.execution_control.authorize(task, actor, action)

    def try_make_ready(self, task_id: str, actor: str = "master") -> AuthorizationDecision:
        """
        Attempt to move a task to READY after checking dependencies and authority.
        Respects Section 2 principles (no hidden transitions, clear reasons).
        """
        task = self._tasks.get(task_id)
        if task is None:
            return AuthorizationDecision(
                allowed=False,
                reason="Task not found",
                actor=actor,
                action="try_make_ready",
            )

        # Dependency check
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != TaskStatus.COMPLETED:
                self.transition_task(
                    task_id,
                    TaskStatus.BLOCKED,
                    actor=actor,
                    reason=f"Waiting for dependency {dep_id}",
                )
                return AuthorizationDecision(
                    allowed=False,
                    reason=f"Dependency {dep_id} not completed",
                    actor=actor,
                    action="try_make_ready",
                    scope=task_id,
                )

        # Authority check
        decision = self.execution_control.check_task_ready(task, actor=actor)

        if not decision.allowed:
            if decision.required_approval:
                self.transition_task(
                    task_id,
                    TaskStatus.AWAITING_APPROVAL,
                    actor=actor,
                    reason=decision.reason,
                )
            else:
                self.transition_task(
                    task_id,
                    TaskStatus.BLOCKED,
                    actor=actor,
                    reason=decision.reason,
                )
            return decision

        # All checks passed
        success = self.transition_task(
            task_id,
            TaskStatus.READY,
            actor=actor,
            reason="All checks passed",
        )

        if success is None:
            return AuthorizationDecision(
                allowed=False,
                reason="Failed to transition task to READY (invalid transition)",
                actor=actor,
                action="try_make_ready",
                scope=task_id,
            )

        return decision

    # ------------------------------------------------------------------
    # Operational status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "component": "MASTER",
            "status": "operational",
            "tasks": {
                "total": len(self._tasks),
                "by_status": {
                    s.value: len([t for t in self._tasks.values() if t.status == s])
                    for s in TaskStatus
                },
            },
            "components": {
                name: {"display_name": c.display_name, "status": c.status}
                for name, c in self._components.items()
            },
        }


# Singleton used by the rest of BAIG
MASTER = Master()
