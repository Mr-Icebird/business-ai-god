"""
BAIG CENTRAL SYSTEM
MASTER — EXECUTION CONTROL MANAGER

Purpose:
Enforce permissions, approvals, identity, scope, environment,
limits and conditions before an operation is authorized.

Central principle:
Technical ability is never treated as permission.

Architecture:
- Identity must be verified through a trusted identity resolver.
- Permission grants and approvals are separate requirements.
- Mandatory approval categories cannot be bypassed.
- Owner identity does not automatically authorize operations.
- Scope and environment must match exactly.
- Unknown limits or conditions fail closed.
- Every authorization decision is recorded.

Specification alignment:
BAIG Central System Sections 7.8, 9, 10, 12, 13 and 15.

IMPORTANT:
This module makes authorization decisions.
It does not execute operations or replace the identity,
security, approval, audit or recovery subsystems.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
# AUTHORIZATION DECISION
# ============================================================

@dataclass(frozen=True)
class AuthorizationDecision:
    """
    Immutable result of an authorization check.

    An allowed decision means the authorization requirements
    checked by this manager were satisfied.

    It does NOT mean the operation was executed successfully.
    """

    allowed: bool
    reason: str

    required_approval: bool = False
    approval_category: Optional[str] = None

    decision_id: str = field(
        default_factory=lambda: new_id("auth_")
    )

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    actor: str = ""
    action: str = ""
    scope: str = ""
    environment: str = ""

    grant_id: Optional[str] = None
    approval_id: Optional[str] = None


# ============================================================
# TRUSTED SERVICE CONTRACTS
# ============================================================

# Returns the authenticated authority level of an actor.
# Returns None if the actor cannot be authenticated.

IdentityResolver = Callable[
    [str],
    Optional[AuthorityLevel]
]


# Verifies that a permission grant was issued by an
# authorized identity with authority to issue that grant.

GrantIssuerValidator = Callable[
    [PermissionGrant],
    bool
]


# Verifies that an approval was issued by an authorized
# approver with authority to approve that category/action.

ApprovalIssuerValidator = Callable[
    [ApprovalRecord],
    bool
]


# ============================================================
# EXECUTION CONTROL MANAGER
# ============================================================

class ExecutionControlManager:
    """
    Central authorization enforcement engine for MASTER.

    Authorization requirements:

    1. Authenticate actor.
    2. Verify trusted permission grant.
    3. Match action, scope and environment.
    4. Enforce applicable limits.
    5. Enforce applicable conditions.
    6. Require explicit approval for mandatory categories.
    7. Record the authorization decision.

    Default behavior is fail-closed.
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

        self._decision_log: list[
            AuthorizationDecision
        ] = []

        self._identity_resolver = identity_resolver

        self._grant_issuer_validator = (
            grant_issuer_validator
        )

        self._approval_issuer_validator = (
            approval_issuer_validator
        )

        self._allow_wildcard_grants = (
            allow_wildcard_grants
        )

    # ========================================================
    # 1. REGISTER PERMISSION GRANTS
    # ========================================================

    def register_grant(
        self,
        grant: PermissionGrant,
    ) -> None:
        """
        Register a permission grant.

        Duplicate grant IDs are rejected.

        A grant is not trusted merely because it has been
        registered. Its issuer must still be validated
        during authorization.
        """

        if not isinstance(grant, PermissionGrant):
            raise TypeError(
                "grant must be a PermissionGrant."
            )

        if not grant.grant_id:
            raise ValueError(
                "Grant ID cannot be empty."
            )

        if grant.grant_id in self._grants:
            raise ValueError(
                f"Grant already exists: {grant.grant_id}"
            )

        if not grant.granted_to:
            raise ValueError(
                "Grant recipient cannot be empty."
            )

        if not grant.granted_by:
            raise ValueError(
                "Grant issuer cannot be empty."
            )

        self._grants[grant.grant_id] = (
            self._copy_grant(grant)
        )

    # ========================================================
    # 2. REGISTER APPROVAL RECORDS
    # ========================================================

    def register_approval(
        self,
        approval: ApprovalRecord,
    ) -> None:
        """
        Register an approval record.

        Registering an approval does not automatically make
        it trusted or valid.

        The approver's authority must be verified separately.
        """

        if not isinstance(approval, ApprovalRecord):
            raise TypeError(
                "approval must be an ApprovalRecord."
            )

        if not approval.approval_id:
            raise ValueError(
                "Approval ID cannot be empty."
            )

        if not approval.requested_by:
            raise ValueError(
                "Approval requester cannot be empty."
            )

        if approval.approval_id in self._approvals:
            raise ValueError(
                f"Approval already exists: "
                f"{approval.approval_id}"
            )

        self._approvals[approval.approval_id] = (
            self._copy_approval(approval)
        )

    # ========================================================
    # 3. DEFENSIVE COPIES
    # ========================================================

    @staticmethod
    def _copy_grant(
        grant: PermissionGrant,
    ) -> PermissionGrant:

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
    def _copy_approval(
        approval: ApprovalRecord,
    ) -> ApprovalRecord:

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

    # ========================================================
    # 4. REVOKE PERMISSION GRANTS
    # ========================================================

    def revoke_grant(
        self,
        grant_id: str,
    ) -> bool:
        """
        Revoke an existing permission grant.

        Returns False if the grant does not exist.
        """

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

    # ========================================================
    # 5. REVOKE APPROVAL RECORDS
    # ========================================================

    def revoke_approval(
        self,
        approval_id: str,
    ) -> bool:
        """
        Revoke an existing approval.

        A revoked approval cannot authorize an operation.
        """

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

    # ========================================================
    # 6. IDENTITY VERIFICATION
    # ========================================================

    def _resolve_identity(
        self,
        actor: str,
    ) -> Optional[AuthorityLevel]:
        """
        Resolve the actor through a trusted identity service.

        No hardcoded owner identity is accepted here.

        An unverified actor is denied.
        """

        if not actor:
            return None

        if self._identity_resolver is None:
            return None

        try:

            level = self._identity_resolver(actor)

            if not isinstance(level, AuthorityLevel):
                return None

            return level

        except Exception:
            return None

    # ========================================================
    # 7. GRANT ISSUER VERIFICATION
    # ========================================================

    def _grant_is_trusted(
        self,
        grant: PermissionGrant,
    ) -> bool:
        """
        Verify that the grant issuer was authorized
        to create the permission grant.
        """

        if self._grant_issuer_validator is None:
            return False

        try:

            return bool(
                self._grant_issuer_validator(grant)
            )

        except Exception:
            return False

    # ========================================================
    # 8. APPROVAL ISSUER VERIFICATION
    # ========================================================

    def _approval_is_trusted(
        self,
        approval: ApprovalRecord,
    ) -> bool:
        """
        Verify that the approval issuer was authorized
        to approve the requested action and category.

        The injected validator must verify the approver's
        identity AND approval authority.
        """

        if self._approval_issuer_validator is None:
            return False

        try:

            return bool(
                self._approval_issuer_validator(approval)
            )

        except Exception:
            return False

    # ========================================================
    # 9. LIMIT VALIDATION
    # ========================================================

    @staticmethod
    def _limits_satisfied(
        approved_limits: Mapping[str, Any],
        requested_limits: Mapping[str, Any],
    ) -> bool:
        """
        Validate numeric upper-bound limits.

        Example:

        Approved:
            {"amount": 10000}

        Requested:
            {"amount": 5000}

        Result:
            ALLOWED

        Requested:
            {"amount": 15000}

        Result:
            DENIED

        Every approved limit must be supplied.
        Unapproved requested limit keys are rejected.

        This implementation supports scalar numeric
        upper bounds only. Currency conversion, nested
        limits, ranges and other limit semantics require
        a typed policy evaluator.
        """

        if not isinstance(approved_limits, Mapping):
            return False

        if not isinstance(requested_limits, Mapping):
            return False

        # Do not allow additional unapproved limits.
        if set(requested_limits) - set(approved_limits):
            return False

        for key, approved_value in approved_limits.items():

            if key not in requested_limits:
                return False

            requested_value = requested_limits[key]

            # Booleans are not accepted as numbers.
            if isinstance(approved_value, bool):
                return False

            if isinstance(requested_value, bool):
                return False

            try:

                approved_number = Decimal(
                    str(approved_value)
                )

                requested_number = Decimal(
                    str(requested_value)
                )

            except (
                InvalidOperation,
                TypeError,
                ValueError,
            ):
                return False

            if not approved_number.is_finite():
                return False

            if not requested_number.is_finite():
                return False

            if requested_number < 0:
                return False

            if approved_number < 0:
                return False

            if requested_number > approved_number:
                return False

        return True

    # ========================================================
    # 10. CONDITION VALIDATION
    # ========================================================

    @staticmethod
    def _conditions_satisfied(
        conditions: tuple[str, ...],
    ) -> bool:
        """
        Conditions require a trusted condition evaluator.

        Until that subsystem is integrated, any non-empty
        condition list causes denial.

        The manager never assumes a condition was satisfied.
        """

        if not conditions:
            return True

        return False

    # ========================================================
    # 11. GRANT MATCHING
    # ========================================================

    def _grant_matches(
        self,
        grant: PermissionGrant,
        actor: str,
        actor_level: AuthorityLevel,
        action: str,
        scope: str,
        environment: str,
    ) -> bool:
        """
        Validate the complete permission grant.

        Requirements:
        - Grant is valid and not revoked.
        - Grant recipient matches the authenticated actor.
        - Authority level matches.
        - Action matches.
        - Scope matches.
        - Environment matches.
        - Issuer is trusted.
        """

        if not grant.is_valid():
            return False

        if grant.granted_to != actor:
            return False

        if grant.level != actor_level:
            return False

        if grant.environment != environment:
            return False

        # Wildcard permissions are prohibited by default.
        if not self._allow_wildcard_grants:

            if grant.action == "*":
                return False

            if grant.scope == "*":
                return False

        if not grant.covers(
            action=action,
            scope=scope,
        ):
            return False

        if not self._grant_is_trusted(grant):
            return False

        return True

    # ========================================================
    # 12. APPROVAL MATCHING
    # ========================================================

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
        """
        Validate the complete approval record.

        Requirements:
        - Approval is GRANTED and not expired.
        - Requester matches the authenticated actor.
        - Approver exists and is not the requester.
        - Approver authority is trusted.
        - Action, scope and category match exactly.
        - Environment matches exactly.
        - Related task does not conflict.
        - Approval conditions are satisfied.
        - Approval limits are respected.
        """

        if not approval.is_valid():
            return False

        if approval.requested_by != actor:
            return False

        if not approval.approver:
            return False

        if approval.approver == actor:
            return False

        if approval.environment != environment:
            return False

        if not approval.covers(
            action=action,
            scope=scope,
            category=category,
        ):
            return False

        if approval.related_task_id not in (
            None,
            task.task_id,
        ):
            return False

        if approval.decided_at is None:
            return False

        if not self._conditions_satisfied(
            approval.conditions
        ):
            return False

        if not self._limits_satisfied(
            approval.limits,
            requested_limits,
        ):
            return False

        if not self._approval_is_trusted(approval):
            return False

        return True

    # ========================================================
    # 13. DECISION CREATION AND LOGGING
    # ========================================================

    def _decision(
        self,
        *,
        allowed: bool,
        reason: str,
        actor: str,
        action: str,
        task: Task,
        required_approval: bool = False,
        category: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> AuthorizationDecision:
        """
        Create and record an authorization decision.

        This in-memory log is a development-level record.
        BAIG's durable audit subsystem must persist it.
        """

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
        )

        self._decision_log.append(decision)

        return decision

    # ========================================================
    # 14. CORE AUTHORIZATION ENGINE
    # ========================================================

    def authorize(
        self,
        task: Task,
        actor: str,
        action: str,
        *,
        category: Optional[str] = None,
        requested_limits: Optional[dict] = None,
    ) -> AuthorizationDecision:
        """
        Authorize one action for one task.

        Mandatory approval categories require BOTH:

        1. A valid permission grant.
        2. A valid explicit approval.

        Owner identity alone never bypasses either requirement.
        """

        if not isinstance(task, Task):
            raise TypeError(
                "task must be a Task instance."
            )

        if not actor or not action:
            return self._decision(
                allowed=False,
                reason="Actor and action are required.",
                actor=actor or "",
                action=action or "",
                task=task,
            )

        # A completed, failed, cancelled or rejected task
        # cannot authorize new execution.
        if task.is_terminal():
            return self._decision(
                allowed=False,
                reason=(
                    "Terminal tasks cannot authorize "
                    "new execution."
                ),
                actor=actor,
                action=action,
                task=task,
            )

        # ----------------------------------------------------
        # STEP 1 — Authenticate actor
        # ----------------------------------------------------

        actor_level = self._resolve_identity(actor)

        if actor_level is None:
            return self._decision(
                allowed=False,
                reason=(
                    "Actor identity is unknown or "
                    "could not be authenticated."
                ),
                actor=actor,
                action=action,
                task=task,
            )

        # ----------------------------------------------------
        # STEP 2 — Validate requested limits
        # ----------------------------------------------------

        if requested_limits is None:
            requested_limits = {}

        if not isinstance(requested_limits, Mapping):
            return self._decision(
                allowed=False,
                reason="Requested limits must be a mapping.",
                actor=actor,
                action=action,
                task=task,
            )

        # ----------------------------------------------------
        # STEP 3 — Determine approval category
        # ----------------------------------------------------

        # A task's recorded approval category cannot
        # be downgraded by a caller.

        effective_category = (
            task.approval_category or category
    )

        if (
            category
            and task.approval_category
            and category != task.approval_category
        ):
            return self._decision(
                allowed=False,
                reason=(
                    "Requested category conflicts with "
                    "the task's approval category."
                ),
                actor=actor,
                action=action,
                task=task,
                category=task.approval_category,
            )

        mandatory_approval = bool(
            effective_category
            and requires_explicit_approval(
                effective_category
            )
        )

        # ----------------------------------------------------
        # STEP 4 — Find a valid permission grant
        # ----------------------------------------------------

        matching_grant = None

        for grant in self._grants.values():

            if not self._grant_matches(
                grant=grant,
                actor=actor,
                actor_level=actor_level,
                action=action,
                scope=task.task_id,
                environment=task.environment,
            ):
                continue

            if not self._limits_satisfied(
                grant.limits,
                requested_limits,
            ):
                continue

            if not self._conditions_satisfied(
                grant.conditions
            ):
                continue

            matching_grant = grant
            break

        if matching_grant is None:
            return self._decision(
                allowed=False,
                reason=(
                    "No trusted permission grant covers "
                    "this actor, action, task scope and "
                    "environment, or its restrictions failed."
                ),
                actor=actor,
                action=action,
                task=task,
                required_approval=mandatory_approval,
                category=effective_category,
            )

        # ----------------------------------------------------
        # STEP 5 — Check mandatory explicit approval
        # ----------------------------------------------------

        if not mandatory_approval:

            return self._decision(
                allowed=True,
                reason=(
                    "Trusted permission grant validated."
                ),
                actor=actor,
                action=action,
                task=task,
                grant_id=matching_grant.grant_id,
            )

        matching_approval = None

        for approval in self._approvals.values():

            if not self._approval_matches(
                approval=approval,
                actor=actor,
                action=action,
                scope=task.task_id,
                category=effective_category,
                environment=task.environment,
                task=task,
                requested_limits=requested_limits,
            ):
                continue

            matching_approval = approval
            break

        if matching_approval is None:

            return self._decision(
                allowed=False,
                reason=(
                    "Mandatory approval is missing, expired, "
                    "revoked, untrusted, out of scope, or its "
                    "limits or conditions failed."
                ),
                actor=actor,
                action=action,
                task=task,
                required_approval=True,
                category=effective_category,
                grant_id=matching_grant.grant_id,
    )

        # ----------------------------------------------------
        # STEP 6 — Authorization successful
        # ----------------------------------------------------

        return self._decision(
            allowed=True,
            reason=(
                "Trusted permission grant and matching "
                "explicit approval validated."
            ),
            actor=actor,
            action=action,
            task=task,
            required_approval=True,
            category=effective_category,
            grant_id=matching_grant.grant_id,
            approval_id=matching_approval.approval_id,
        )

    # ========================================================
    # 15. MASTER TASK READINESS CHECK
    # ========================================================

    def check_task_ready(
        self,
        task: Task,
        actor: str = "master",
    ) -> AuthorizationDecision:
        """
        MASTER uses this method before allowing a task
        to proceed towards READY or RUNNING.

        Rules:

        - Every required permission is checked.
        - Mandatory approval categories cannot be bypassed.
        - A mandatory category with no listed permission
          still requires authorization for 'execute'.
        - One approved action does not authorize another.
        - A task with no protected action receives only
          a readiness result, not an execution grant.
        """

        if not isinstance(task, Task):
            raise TypeError(
                "task must be a Task instance."
            )

        mandatory = bool(
            task.approval_category
            and requires_explicit_approval(
                task.approval_category
            )
        )

        actions = tuple(task.required_permissions)

        # Mandatory approval cannot be skipped merely
        # because required_permissions is empty.
        if not actions and mandatory:
            actions = ("execute",)

        # No protected action is being requested.
        # This is not permission to execute arbitrary actions.
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
            )

        # Check every required action independently.
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
            reason=(
                "Every required action passed authorization."
            ),
            actor=actor,
            action="check_task_ready",
            task=task,
            required_approval=mandatory,
            category=task.approval_category,
        )

    # ========================================================
    # 16. AUTHORIZATION DECISION HISTORY
    # ========================================================

    def get_decision_log(
        self,
    ) -> list[AuthorizationDecision]:
        """
        Return a copy of the decision history.

        This is not a replacement for BAIG's permanent
        audit storage. Decisions must eventually be sent
        to the dedicated audit/record system.
        """

        return list(self._decision_log)

    # ========================================================
    # 17. GRANT AND APPROVAL LOOKUP
    # ========================================================

    def get_grant(
        self,
        grant_id: str,
    ) -> Optional[PermissionGrant]:

        grant = self._grants.get(grant_id)

        if grant is None:
            return None

        return self._copy_grant(grant)

    def get_approval(
        self,
        approval_id: str,
    ) -> Optional[ApprovalRecord]:

        approval = self._approvals.get(approval_id)

        if approval is None:
            return None

        return self._copy_approval(approval)

    def list_grants(self) -> tuple[PermissionGrant, ...]:

        return tuple(
            self._copy_grant(grant)
            for grant in self._grants.values()
        )

    def list_approvals(self) -> tuple[ApprovalRecord, ...]:

        return tuple(
            self._copy_approval(approval)
            for approval in self._approvals.values()
        )
        
