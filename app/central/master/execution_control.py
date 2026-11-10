"""
MASTER — Execution Control Manager

Enforces the full authority model before any work is allowed to proceed.
Technical ability is never treated as permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.central.models.authority import (
    APPROVAL_REQUIRED_CATEGORIES,
    ApprovalRecord,
    ApprovalStatus,
    AuthorityContext,
    AuthorityLevel,
    PermissionGrant,
    requires_explicit_approval,
)
from app.central.models.task import Task, TaskStatus


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of an execution-control check."""

    allowed: bool
    reason: str
    required_approval: bool = False
    approval_category: Optional[str] = None
    decision_id: str = ""
    checked_at: datetime = None  # type: ignore

    def __post_init__(self):
        if self.checked_at is None:
            object.__setattr__(self, "checked_at", datetime.now(timezone.utc))


class ExecutionControlManager:
    """
    Ensures operations meet permission, approval, scope and precondition rules
    (Central System Specification §7.8).
    """

    def __init__(self):
        self._grants: dict[str, PermissionGrant] = {}
        self._approvals: dict[str, ApprovalRecord] = {}

    # ------------------------------------------------------------------
    # Grant & Approval management
    # ------------------------------------------------------------------

    def register_grant(self, grant: PermissionGrant) -> None:
        self._grants[grant.grant_id] = grant

    def register_approval(self, approval: ApprovalRecord) -> None:
        self._approvals[approval.approval_id] = approval

    def revoke_grant(self, grant_id: str) -> bool:
        grant = self._grants.get(grant_id)
        if grant is None:
            return False
        # frozen dataclass — replace with revoked copy
        revoked = PermissionGrant(
            grant_id=grant.grant_id,
            level=grant.level,
            action=grant.action,
            scope=grant.scope,
            granted_to=grant.granted_to,
            environment=grant.environment,
            limits=grant.limits,
            conditions=grant.conditions,
            granted_at=grant.granted_at,
            expires_at=grant.expires_at,
            granted_by=grant.granted_by,
            revoked=True,
        )
        self._grants[grant_id] = revoked
        return True

    def get_authority_context(self, actor: str, environment: str = "development") -> AuthorityContext:
        """Build a snapshot of currently valid grants and approvals for an actor."""
        valid_grants = tuple(
            g for g in self._grants.values()
            if g.granted_to in (actor, "*") and g.is_valid() and g.environment in (environment, "*")
        )
        valid_approvals = tuple(
            a for a in self._approvals.values()
            if a.is_valid() and a.environment in (environment, "*")
        )
        # Simple heuristic for actor level — can be replaced by a real identity service later
        level = AuthorityLevel.OWNER if actor in ("owner", "Mr-Icebird") else AuthorityLevel.COMPONENT
        return AuthorityContext(
            actor=actor,
            actor_level=level,
            grants=valid_grants,
            approvals=valid_approvals,
            environment=environment,
        )

    # ------------------------------------------------------------------
    # Core authorization check
    # ------------------------------------------------------------------

    def authorize(
        self,
        task: Task,
        actor: str,
        action: str,
        *,
        category: Optional[str] = None,
    ) -> AuthorizationDecision:
        """
        Decide whether the requested action is allowed for this task.

        Returns an AuthorizationDecision that MASTER must respect.
        """
        category = category or task.approval_category
        ctx = self.get_authority_context(actor, task.environment)

        # 1. Owner can do almost anything (still subject to law/platform limits)
        if ctx.actor_level == AuthorityLevel.OWNER:
            return AuthorizationDecision(
                allowed=True,
                reason="Owner authority",
                required_approval=False,
            )

        # 2. Does this category always require explicit approval?
        if category and requires_explicit_approval(category):
            if ctx.has_valid_approval(action, category):
                return AuthorizationDecision(
                    allowed=True,
                    reason=f"Valid approval found for category '{category}'",
                    required_approval=True,
                    approval_category=category,
                )
            return AuthorizationDecision(
                allowed=False,
                reason=f"Category '{category}' requires explicit approval that is missing or invalid",
                required_approval=True,
                approval_category=category,
            )

        # 3. Check for a valid task-scoped or delegated grant
        if ctx.has_valid_grant(action, scope=task.task_id) or ctx.has_valid_grant(action, scope="*"):
            return AuthorizationDecision(
                allowed=True,
                reason=f"Valid permission grant for action '{action}'",
            )

        # 4. Component-level authority (very limited — only its own declared responsibilities)
        if ctx.actor_level == AuthorityLevel.COMPONENT:
            # In the full system this would consult a capability registry.
            # For now we deny by default for safety.
            return AuthorizationDecision(
                allowed=False,
                reason=f"Component '{actor}' has no grant for action '{action}'",
            )

        return AuthorizationDecision(
            allowed=False,
            reason=f"No valid authority found for actor '{actor}' to perform '{action}'",
        )

    def check_task_ready(self, task: Task, actor: str = "master") -> AuthorizationDecision:
        """
        Convenience method used by MASTER before moving a task to READY/RUNNING.
        """
        if not task.required_permissions and not task.approval_category:
            return AuthorizationDecision(allowed=True, reason="No special permissions required")

        # Check every required permission
        for action in task.required_permissions:
            decision = self.authorize(task, actor, action, category=task.approval_category)
            if not decision.allowed:
                return decision

        return AuthorizationDecision(allowed=True, reason="All required permissions satisfied")
