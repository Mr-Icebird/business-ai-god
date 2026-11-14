"""
BAIG CENTRAL SYSTEM
MASTER — EXECUTION CONTROL MANAGER

Purpose:
Enforce permissions, approvals, identity, scope, environment,
limits and conditions before an operation is authorized.

Central principle:
Technical ability is never treated as permission.

Focused correction:
- Explicit AuthorizationOutcome (ALLOW / DENY / REQUIRE_APPROVAL / INDETERMINATE)
- Machine-readable reason_code on every decision
- Individual decisions remain available for durable audit by MASTER
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from app.central.models.authority import (
    ApprovalRecord,
    ApprovalStatus,
    AuthorityLevel,
    PermissionGrant,
    requires_explicit_approval,
    new_id,
)
from app.central.models.task import Task


# ============================================================
# AUTHORIZATION OUTCOME
# ============================================================

class AuthorizationOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    INDETERMINATE = "INDETERMINATE"


# ============================================================
# AUTHORIZATION DECISION
# ============================================================

@dataclass(frozen=True)
class AuthorizationDecision:
    """
    Immutable result of an authorization check.

    allowed=True only when outcome is ALLOW.
    This decision does NOT mean the operation was executed.
    """

    allowed: bool
    reason: str

    required_approval: bool = False
    approval_category: Optional[str] = None

    decision_id: str = field(default_factory=lambda: new_id("auth_"))
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    actor: str = ""
    action: str = ""
    scope: str = ""
    environment: str = ""

    grant_id: Optional[str] = None
    approval_id: Optional[str] = None

    outcome: AuthorizationOutcome = AuthorizationOutcome.DENY
    reason_code: str = "UNSPECIFIED"


# ============================================================
# TRUSTED SERVICE CONTRACTS
# ============================================================

IdentityResolver = Callable[[str], Optional[AuthorityLevel]]
GrantIssuerValidator = Callable[[PermissionGrant], bool]
ApprovalIssuerValidator = Callable[[ApprovalRecord], bool]


# ============================================================
# EXECUTION CONTROL MANAGER
# ============================================================

class ExecutionControlManager:
    """
    Central authorization enforcement engine for MASTER.
    Default behaviour is fail-closed.
    """

    def __init__(
        self,
        *,
        identity_resolver: Optional[IdentityResolver] = None,
        grant_issuer_validator: Optional[GrantIssuerValidator] = None,
        approval_issuer_validator: Optional[ApprovalIssuerValidator] = None,
        allow_wildcard_grants: bool = False,
    ) -> None:
        self._grants: dict[str, PermissionGrant] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._decision_log: list[AuthorizationDecision] = []
        self._identity_resolver = identity_resolver
        self._grant_issuer_validator = grant_issuer_validator
        self._approval_issuer_validator = approval_issuer_validator
        self._allow_wildcard_grants = allow_wildcard_grants

    # --------------------------------------------------------
    # Registration
    # --------------------------------------------------------

    def register_grant(self, grant: PermissionGrant) -> None:
        if not isinstance(grant, PermissionGrant):
            raise TypeError("grant must be a PermissionGrant.")
        if not grant.grant_id:
            raise ValueError("Grant ID cannot be empty.")
        if grant.grant_id in self._grants:
            raise ValueError(f"Grant already exists: {grant.grant_id}")
        if not grant.granted_to:
            raise ValueError("Grant recipient cannot be empty.")
        if not grant.granted_by:
            raise ValueError("Grant issuer cannot be empty.")
        self._grants[grant.grant_id] = self._copy_grant(grant)

    def register_approval(self, approval: ApprovalRecord) -> None:
        if not isinstance(approval, ApprovalRecord):
            raise TypeError("approval must be an ApprovalRecord.")
        if not approval.approval_id:
            raise ValueError("Approval ID cannot be empty.")
        if not approval.requested_by:
            raise ValueError("Approval requester cannot be empty.")
        if approval.approval_id in self._approvals:
            raise ValueError(f"Approval already exists: {approval.approval_id}")
        self._approvals[approval.approval_id] = self._copy_approval(approval)

    @staticmethod
    def _copy_grant(grant: PermissionGrant) -> PermissionGrant:
        return PermissionGrant(
            grant_id=grant.grant_id,
            level=grant.level,
            action=grant.action,
            scope=grant.scope,
            granted_to=grant.granted_to,
            environment=grant.environment,
            limits=deepcopy(grant.limits),
            conditions=tuple(grant.conditions),
            granted_at=grant.granted_at,
            expires_at=grant.expires_at,
            granted_by=grant.granted_by,
            revoked=grant.revoked,
        )

    @staticmethod
    def _copy_approval(approval: ApprovalRecord) -> ApprovalRecord:
        return ApprovalRecord(
            approval_id=approval.approval_id,
            action=approval.action,
            scope=approval.scope,
            category=approval.category,
            status=approval.status,
            requested_by=approval.requested_by,
            approver=approval.approver,
            environment=approval.environment,
            limits=deepcopy(approval.limits),
            conditions=tuple(approval.conditions),
            requested_at=approval.requested_at,
            decided_at=approval.decided_at,
            expires_at=approval.expires_at,
            reason=approval.reason,
            related_task_id=approval.related_task_id,
        )

    def revoke_grant(self, grant_id: str) -> bool:
        grant = self._grants.get(grant_id)
        if grant is None:
            return False
        if grant.revoked:
            return True
        self._grants[grant_id] = PermissionGrant(
            grant_id=grant.grant_id,
            level=grant.level,
            action=grant.action,
            scope=grant.scope,
            granted_to=grant.granted_to,
            environment=grant.environment,
            limits=deepcopy(grant.limits),
            conditions=tuple(grant.conditions),
            granted_at=grant.granted_at,
            expires_at=grant.expires_at,
            granted_by=grant.granted_by,
            revoked=True,
        )
        return True

    def revoke_approval(self, approval_id: str) -> bool:
        approval = self._approvals.get(approval_id)
        if approval is None:
            return False
        if approval.status == ApprovalStatus.REVOKED:
            return True
        self._approvals[approval_id] = ApprovalRecord(
            approval_id=approval.approval_id,
            action=approval.action,
            scope=approval.scope,
            category=approval.category,
            status=ApprovalStatus.REVOKED,
            requested_by=approval.requested_by,
            approver=approval.approver,
            environment=approval.environment,
            limits=deepcopy(approval.limits),
            conditions=tuple(approval.conditions),
            requested_at=approval.requested_at,
            decided_at=datetime.now(timezone.utc),
            expires_at=approval.expires_at,
            reason=approval.reason,
            related_task_id=approval.related_task_id,
        )
        return True

    # --------------------------------------------------------
    # Identity / issuer verification
    # --------------------------------------------------------

    def _resolve_identity(self, actor: str) -> Optional[AuthorityLevel]:
        if not actor or self._identity_resolver is None:
            return None
        try:
            level = self._identity_resolver(actor)
            if not isinstance(level, AuthorityLevel):
                return None
            return level
        except Exception:
            return None

    def _grant_is_trusted(self, grant: PermissionGrant) -> bool:
        if self._grant_issuer_validator is None:
            return False
        try:
            return bool(self._grant_issuer_validator(grant))
        except Exception:
            return False

    def _approval_is_trusted(self, approval: ApprovalRecord) -> bool:
        if self._approval_issuer_validator is None:
            return False
        try:
            return bool(self._approval_issuer_validator(approval))
        except Exception:
            return False

    # --------------------------------------------------------
    # Limits / conditions
    # --------------------------------------------------------

    @staticmethod
    def _limits_satisfied(
        approved_limits: Mapping[str, Any],
        requested_limits: Mapping[str, Any],
    ) -> bool:
        if not isinstance(approved_limits, Mapping):
            return False
        if not isinstance(requested_limits, Mapping):
            return False
        if set(requested_limits) - set(approved_limits):
            return False

        for key, approved_value in approved_limits.items():
            if key not in requested_limits:
                return False
            requested_value = requested_limits[key]
            if isinstance(approved_value, bool) or isinstance(requested_value, bool):
                return False
            try:
                approved_number = Decimal(str(approved_value))
                requested_number = Decimal(str(requested_value))
            except (InvalidOperation, TypeError, ValueError):
                return False
            if not approved_number.is_finite() or not requested_number.is_finite():
                return False
            if requested_number < 0 or approved_number < 0:
                return False
            if requested_number > approved_number:
                return False
        return True

    @staticmethod
    def _conditions_satisfied(conditions: tuple[str, ...]) -> bool:
        # Until a trusted condition evaluator is integrated, non-empty conditions deny.
        return not conditions

    # --------------------------------------------------------
    # Matching
    # --------------------------------------------------------

    def _grant_matches(
        self,
        grant: PermissionGrant,
        actor: str,
        actor_level: AuthorityLevel,
        action: str,
        scope: str,
        environment: str,
    ) -> bool:
        if not grant.is_valid():
            return False
        if grant.granted_to != actor:
            return False
        if grant.level != actor_level:
            return False
        if grant.environment != environment:
            return False
        if not self._allow_wildcard_grants:
            if grant.action == "*" or grant.scope == "*":
                return False
        if not grant.covers(action=action, scope=scope):
            return False
        if not self._grant_is_trusted(grant):
            return False
        return True

    def _approval_matches(
        self,
        approval: ApprovalRecord,
        actor: str,
        action: str,
        scope: str,
        category: str,
        environment: str,
        task: Task,
        requested_limits: Mapping[str, Any],
    ) -> bool:
        if not approval.is_valid():
            return False
        if approval.requested_by != actor:
            return False
        if not approval.approver or approval.approver == actor:
            return False
        if approval.environment != environment:
            return False
        if not approval.covers(action=action, scope=scope, category=category):
            return False
        if approval.related_task_id not in (None, task.task_id):
            return False
        if approval.decided_at is None:
            return False
        if not self._conditions_satisfied(approval.conditions):
            return False
        if not self._limits_satisfied(approval.limits, requested_limits):
            return False
        if not self._approval_is_trusted(approval):
            return False
        return True

    # --------------------------------------------------------
    # Decision factory
    # --------------------------------------------------------

    def _decision(
        self,
        *,
        allowed: bool,
        reason: str,
        actor: str,
        action: str,
        task: Task,
        outcome: AuthorizationOutcome,
        reason_code: str,
        required_approval: bool = False,
        category: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> AuthorizationDecision:
        decision = AuthorizationDecision(
            allowed=allowed,
            reason=reason,
            required_approval=required_approval,
            approval_category=category,
            actor=actor,
            action=action,
            scope=task.task_id,
            environment=task.environment,
            grant_id=grant_id,
            approval_id=approval_id,
            outcome=outcome,
            reason_code=reason_code,
        )
        self._decision_log.append(decision)
        return decision

    # --------------------------------------------------------
    # Core authorization
    # --------------------------------------------------------

    def authorize(
        self,
        task: Task,
        actor: str,
        action: str,
        *,
        category: Optional[str] = None,
        requested_limits: Optional[dict] = None,
    ) -> AuthorizationDecision:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task instance.")

        if not actor or not action:
            return self._decision(
                allowed=False,
                reason="Actor and action are required.",
                actor=actor or "",
                action=action or "",
                task=task,
                outcome=AuthorizationOutcome.DENY,
                reason_code="MISSING_ACTOR_OR_ACTION",
            )

        if task.is_terminal():
            return self._decision(
                allowed=False,
                reason="Terminal tasks cannot authorize new execution.",
                actor=actor,
                action=action,
                task=task,
                outcome=AuthorizationOutcome.DENY,
                reason_code="TERMINAL_TASK",
            )

        actor_level = self._resolve_identity(actor)
        if actor_level is None:
            return self._decision(
                allowed=False,
                reason="Actor identity could not be verified.",
                actor=actor,
                action=action,
                task=task,
                outcome=AuthorizationOutcome.INDETERMINATE,
                reason_code="IDENTITY_UNVERIFIED",
            )

        requested_limits = requested_limits or {}
        environment = task.environment
        scope = task.task_id
        mandatory = bool(
            category and requires_explicit_approval(category)
        )

        # Find a matching trusted grant
        matched_grant: Optional[PermissionGrant] = None
        for grant in self._grants.values():
            if self._grant_matches(
                grant, actor, actor_level, action, scope, environment
            ):
                if grant.limits and not self._limits_satisfied(
                    grant.limits, requested_limits
                ):
                    continue
                if not self._conditions_satisfied(grant.conditions):
                    continue
                matched_grant = grant
                break

        if matched_grant is None:
            return self._decision(
                allowed=False,
                reason="No valid permission grant covers this action and scope.",
                actor=actor,
                action=action,
                task=task,
                outcome=AuthorizationOutcome.DENY,
                reason_code="MISSING_OR_INVALID_GRANT",
                required_approval=mandatory,
                category=category,
            )

        # Mandatory approval path
        if mandatory:
            matched_approval: Optional[ApprovalRecord] = None
            for approval in self._approvals.values():
                if self._approval_matches(
                    approval,
                    actor,
                    action,
                    scope,
                    category or "",
                    environment,
                    task,
                    requested_limits,
                ):
                    matched_approval = approval
                    break

            if matched_approval is None:
                return self._decision(
                    allowed=False,
                    reason="Mandatory approval is outstanding or invalid.",
                    actor=actor,
                    action=action,
                    task=task,
                    outcome=AuthorizationOutcome.REQUIRE_APPROVAL,
                    reason_code="APPROVAL_REQUIRED",
                    required_approval=True,
                    category=category,
                    grant_id=matched_grant.grant_id,
                )

            return self._decision(
                allowed=True,
                reason="Valid grant and mandatory approval satisfied.",
                actor=actor,
                action=action,
                task=task,
                outcome=AuthorizationOutcome.ALLOW,
                reason_code="GRANT_AND_APPROVAL_VALID",
                required_approval=True,
                category=category,
                grant_id=matched_grant.grant_id,
                approval_id=matched_approval.approval_id,
            )

        # Non-mandatory path — grant alone is sufficient
        return self._decision(
            allowed=True,
            reason="Valid permission grant covers this action and scope.",
            actor=actor,
            action=action,
            task=task,
            outcome=AuthorizationOutcome.ALLOW,
            reason_code="GRANT_VALID",
            grant_id=matched_grant.grant_id,
        )
 
    def check_task_ready(
        self,
        task: Task,
        actor: str = "master",
    ) -> AuthorizationDecision:
        """
        Check every required permission independently.

        Returns the first failing decision, or a final ALLOW
        aggregate when every required action passes.

        Individual decisions remain available for durable audit.
        """
        if not isinstance(task, Task):
            raise TypeError("task must be a Task instance.")

        mandatory = bool(
            task.approval_category
            and requires_explicit_approval(task.approval_category)
        )

        actions = tuple(task.required_permissions)

        if not actions and mandatory:
            actions = ("execute",)

        if not actions:
            return self._decision(
                allowed=True,
                reason=(
                    "No special permissions or mandatory "
                    "approval category required for readiness."
                ),
                actor=actor,
                action="check_task_ready",
                task=task,
                outcome=AuthorizationOutcome.ALLOW,
                reason_code="NO_PROTECTED_ACTIONS",
            )

        for action in actions:
            decision = self.authorize(
                task=task,
                actor=actor,
                action=action,
                category=task.approval_category,
            )

            if not decision.allowed:
                return decision

        return self._decision(
            allowed=True,
            reason="Every required action passed authorization.",
            actor=actor,
            action="check_task_ready",
            task=task,
            outcome=AuthorizationOutcome.ALLOW,
            reason_code="ALL_REQUIRED_ACTIONS_ALLOWED",
            required_approval=mandatory,
            category=task.approval_category,
        )
        
    # --------------------------------------------------------
    # Lookup helpers
    # --------------------------------------------------------

    def get_decision_log(self) -> list[AuthorizationDecision]:
        return list(self._decision_log)

    def get_recent_decisions(self, n: int = 20) -> list[AuthorizationDecision]:
        if n <= 0:
            return []
        return list(self._decision_log[-n:])

    def get_grant(self, grant_id: str) -> Optional[PermissionGrant]:
        grant = self._grants.get(grant_id)
        return self._copy_grant(grant) if grant else None

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        approval = self._approvals.get(approval_id)
        return self._copy_approval(approval) if approval else None

    def list_grants(self) -> tuple[PermissionGrant, ...]:
        return tuple(self._copy_grant(g) for g in self._grants.values())

    def list_approvals(self) -> tuple[ApprovalRecord, ...]:
        return tuple(self._copy_approval(a) for a in self._approvals.values())
