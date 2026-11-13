"""
BAIG MASTER — Coordinated with corrected Execution Control

Consumes:
- AuthorizationOutcome + reason_code from execution_control
- Individual decisions from the decision log for durable audit

Rules:
- Every individual authorization decision is durably audited
- Audit failure blocks consequential authorization / transitions
- Per-task locking around readiness + transitions
- Callers receive copies, not live mutable objects
"""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.central.audit.ledger import AUDIT_LEDGER, AuditWriteError
from app.central.master.execution_control import (
    AuthorizationDecision,
    AuthorizationOutcome,
    ExecutionControlManager,
)
from app.central.models.task import (
    Task,
    TaskPriority,
    TaskStatus,
    create_task,
)


ALLOWED_COMPONENT_STATUSES = frozenset({
    "planned", "initialized", "operational", "disabled", "error",
})


@dataclass(frozen=True)
class ComponentView:
    name: str
    display_name: str
    status: str
    capabilities: tuple[str, ...]
    last_heartbeat: Optional[datetime]


@dataclass
class ComponentInfo:
    name: str
    display_name: str
    status: str = "planned"
    capabilities: tuple[str, ...] = ()
    last_heartbeat: Optional[datetime] = None

    def view(self) -> ComponentView:
        return ComponentView(
            name=self.name,
            display_name=self.display_name,
            status=self.status,
            capabilities=self.capabilities,
            last_heartbeat=self.last_heartbeat,
        )


class Master:
    def __init__(self):
        self._execution_control = ExecutionControlManager()
        self._tasks: dict[str, Task] = {}
        self._components: dict[str, ComponentInfo] = {}
        self._task_locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._register_core_components()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_task_lock(self, task_id: str) -> threading.RLock:
        with self._locks_guard:
            if task_id not in self._task_locks:
                self._task_locks[task_id] = threading.RLock()
            return self._task_locks[task_id]

    def _audit_authorization_decision(
        self,
        decision: AuthorizationDecision,
        *,
        task: Optional[Task] = None,
    ) -> bool:
        """
        Persist one authorization decision.
        Returns True on success, False on audit failure.
        """
        try:
            AUDIT_LEDGER.record_authorization(
                actor=decision.actor or "unknown",
                action=decision.action or "unknown",
                auth_outcome=decision.outcome.value,
                reason=decision.reason or "",
                task_id=(
                    task.task_id if task is not None
                    else (decision.scope or None)
                ),
                correlation_id=getattr(task, "correlation_id", None) if task else None,
                environment=(
                    task.environment if task is not None
                    else (decision.environment or "development")
                ),
                decision_id=decision.decision_id,
                grant_id=decision.grant_id,
                approval_id=decision.approval_id,
                details={
                    "reason_code": decision.reason_code,
                    "approval_category": decision.approval_category,
                    "required_approval": decision.required_approval,
                    "scope": decision.scope,
                    "checked_at": decision.checked_at.isoformat(),
                },
            )
            return True
        except AuditWriteError:
            return False

    def _audit_recent_decisions_since(
        self,
        start_index: int,
        task: Task,
    ) -> bool:
        """
        Durably audit every decision appended since start_index.
        If any write fails, return False (fail closed).
        """
        log = self._execution_control.get_decision_log()
        for decision in log[start_index:]:
            if not self._audit_authorization_decision(decision, task=task):
                return False
        return True

    # ------------------------------------------------------------------
    # Components
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
                status="planned",
                capabilities=caps,
            )

    def get_component(self, name: str) -> Optional[ComponentView]:
        comp = self._components.get(name)
        return comp.view() if comp else None

    def list_components(self) -> list[ComponentView]:
        return [c.view() for c in self._components.values()]

    def set_component_status(self, name: str, status: str) -> bool:
        if status not in ALLOWED_COMPONENT_STATUSES:
            return False
        comp = self._components.get(name)
        if not comp:
            return False

        old_status = comp.status
        try:
            AUDIT_LEDGER.record(
                event_type="component.status_change",
                actor="master",
                action="set_component_status",
                outcome="success",
                target_type="component",
                target_id=name,
                old_state=old_status,
                new_state=status,
                reason=f"Component {name} status changed",
            )
        except AuditWriteError:
            return False

        comp.status = status
        comp.last_heartbeat = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def _validate_dependencies(
        self,
        task_id: str,
        dependencies: tuple[str, ...],
        parent_task_id: Optional[str],
    ) -> None:
        if task_id in dependencies:
            raise ValueError("Task cannot depend on itself")
        if parent_task_id is not None and parent_task_id == task_id:
            raise ValueError("Task cannot be its own parent")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("Duplicate dependencies are not allowed")

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
        self._validate_dependencies(task.task_id, dependencies, parent_task_id)

        try:
            AUDIT_LEDGER.record(
                event_type="system.event",
                actor=created_by,
                action="create_task",
                outcome="success",
                target_type="task",
                target_id=task.task_id,
                task_id=task.task_id,
                correlation_id=task.correlation_id,
                reason=f"Task created: {title}",
                environment=environment,
            )
        except AuditWriteError as e:
            raise AuditWriteError(
                f"Task creation rejected because audit write failed: {e}"
            ) from e

        self._tasks[task.task_id] = task
        return deepcopy(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        task = self._tasks.get(task_id)
        return deepcopy(task) if task else None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return [deepcopy(t) for t in tasks]

    def transition_task(
        self,
        task_id: str,
        to_status: TaskStatus,
        actor: str,
        reason: str = "",
    ) -> Optional[Task]:
        if not isinstance(to_status, TaskStatus):
            raise TypeError("to_status must be a TaskStatus enum value")
        if not actor or not str(actor).strip():
            raise ValueError("actor is required for task transitions")

        lock = self._get_task_lock(task_id)
        with lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return self._transition_locked(task, to_status, actor, reason)

    def _transition_locked(
        self,
        task: Task,
        to_status: TaskStatus,
        actor: str,
        reason: str = "",
    ) -> Optional[Task]:
        from_status = task.status

        if not task.can_transition_to(to_status):
            try:
                AUDIT_LEDGER.record(
                    event_type="task.transition",
                    actor=actor,
                    action="transition",
                    outcome="rejected",
                    target_type="task",
                    target_id=task.task_id,
                    task_id=task.task_id,
                    correlation_id=task.correlation_id,
                    old_state=from_status.value,
                    new_state=to_status.value,
                    reason=reason or "Invalid transition rejected",
                    environment=task.environment,
                )
            except AuditWriteError:
                pass
            return None

        try:
            AUDIT_LEDGER.record_transition(
                actor=actor,
                task_id=task.task_id,
                from_status=from_status.value,
                to_status=to_status.value,
                reason=reason or "No reason provided",
                correlation_id=task.correlation_id,
                outcome="success",
                environment=task.environment,
            )
        except AuditWriteError:
            return None

        try:
            task.transition(to_status, actor=actor, reason=reason)
        except ValueError:
            return None

        return task

    # ------------------------------------------------------------------
    # Authorization gateway
    # ------------------------------------------------------------------

    def authorize_task(
        self,
        task_id: str,
        actor: str,
        action: str,
    ) -> AuthorizationDecision:
        task = self._tasks.get(task_id)
        if task is None:
            decision = AuthorizationDecision(
                allowed=False,
                reason=f"Task {task_id} not found",
                actor=actor,
                action=action,
                outcome=AuthorizationOutcome.DENY,
                reason_code="TASK_NOT_FOUND",
            )
            self._audit_authorization_decision(decision, task=None)
            return decision

        before = len(self._execution_control.get_decision_log())
        decision = self._execution_control.authorize(task, actor, action)

        # Audit every decision produced by this call (usually one)
        if not self._audit_recent_decisions_since(before, task):
            return AuthorizationDecision(
                allowed=False,
                reason="Authorization audit write failed; operation blocked",
                actor=actor,
                action=action,
                scope=task_id,
                outcome=AuthorizationOutcome.DENY,
                reason_code="AUDIT_WRITE_FAILED",
            )
        return decision

    def try_make_ready(
        self,
        task_id: str,
        actor: str = "master",
    ) -> AuthorizationDecision:
        if not actor or not str(actor).strip():
            return AuthorizationDecision(
                allowed=False,
                reason="actor is required",
                actor=actor or "unknown",
                action="try_make_ready",
                outcome=AuthorizationOutcome.DENY,
                reason_code="MISSING_ACTOR",
            )

        lock = self._get_task_lock(task_id)
        with lock:
            task = self._tasks.get(task_id)
            if task is None:
                return AuthorizationDecision(
                    allowed=False,
                    reason="Task not found",
                    actor=actor,
                    action="try_make_ready",
                    outcome=AuthorizationOutcome.DENY,
                    reason_code="TASK_NOT_FOUND",
                )

            # Dependencies
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if dep is None or dep.status != TaskStatus.COMPLETED:
                    self._transition_locked(
                        task,
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
                        outcome=AuthorizationOutcome.DENY,
                        reason_code="DEPENDENCY_NOT_READY",
                    )

            # Full readiness authorization (produces individual decisions)
            before = len(self._execution_control.get_decision_log())
            decision = self._execution_control.check_task_ready(task, actor=actor)

            # Durably audit EVERY individual decision produced
            if not self._audit_recent_decisions_since(before, task):
                return AuthorizationDecision(
                    allowed=False,
                    reason="Readiness authorization audit write failed; operation blocked",
                    actor=actor,
                    action="try_make_ready",
                    scope=task_id,
                    outcome=AuthorizationOutcome.DENY,
                    reason_code="AUDIT_WRITE_FAILED",
                )

            if not decision.allowed:
                if decision.outcome == AuthorizationOutcome.REQUIRE_APPROVAL:
                    self._transition_locked(
                        task,
                        TaskStatus.AWAITING_APPROVAL,
                        actor=actor,
                        reason=decision.reason or "Approval required",
                    )
                else:
                    self._transition_locked(
                        task,
                        TaskStatus.BLOCKED,
                        actor=actor,
                        reason=decision.reason or "Authorization denied",
                    )
                return decision

            success = self._transition_locked(
                task,
                TaskStatus.READY,
                actor=actor,
                reason="All checks passed",
            )
            if success is None:
                return AuthorizationDecision(
                    allowed=False,
                    reason="Failed to transition task to READY",
                    actor=actor,
                    action="try_make_ready",
                    scope=task_id,
                    outcome=AuthorizationOutcome.DENY,
                    reason_code="TRANSITION_FAILED",
                )
            return decision

    # ------------------------------------------------------------------
    # Status
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
                name: {
                    "display_name": c.display_name,
                    "status": c.status,
                }
                for name, c in self._components.items()
            },
        }


MASTER = Master()
