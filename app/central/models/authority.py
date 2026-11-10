"""
BAIG Central System — Authority, Permission and Approval models.

Implements the full authority model defined in the Central System specification
(Section 12: Authority, permissions and approvals).

Core principle: Technical ability is not permission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class AuthorityLevel(str, Enum):
    """Authority levels as defined in the specification."""

    OWNER = "owner"
    DELEGATED = "delegated"
    COMPONENT = "component"
    TASK_SCOPED = "task_scoped"


class ApprovalStatus(str, Enum):
    """Lifecycle status of an approval record."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


# Categories that always require explicit owner (or high-level delegated) approval.
APPROVAL_REQUIRED_CATEGORIES = frozenset({
    "real_money",
    "irreversible_data",
    "identity_credentials_security",
    "production_deployment",
    "external_commitment",
    "high_impact_uncertain",
})


@dataclass(frozen=True)
class PermissionGrant:
    """
    A narrow, task-scoped or role-scoped permission grant.

    Approval for one action is not blanket permission for unrelated actions.
    """

    grant_id: str
    level: AuthorityLevel
    action: str
    scope: str
    granted_to: str  # role, component name, or identity
    environment: str = "development"
    limits: dict = field(default_factory=dict)
    conditions: tuple[str, ...] = ()
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    granted_by: str = "system"
    revoked: bool = False

    def is_valid(self, at: Optional[datetime] = None) -> bool:
        """Return True if this grant is still usable."""
        if self.revoked:
            return False
        now = at or datetime.now(timezone.utc)
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True


@dataclass(frozen=True)
class ApprovalRecord:
    """
    Explicit approval record (Section 12.2).

    Must record: approver, action, exact scope, limits, environment,
    expiry, timestamp and conditions.
    """

    approval_id: str
    action: str
    scope: str
    category: str
    status: ApprovalStatus
    requested_by: str
    approver: Optional[str] = None
    environment: str = "development"
    limits: dict = field(default_factory=dict)
    conditions: tuple[str, ...] = ()
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reason: str = ""
    related_task_id: Optional[str] = None

    def is_valid(self, at: Optional[datetime] = None) -> bool:
        """Return True only for a still-usable GRANTED approval."""
        if self.status != ApprovalStatus.GRANTED:
            return False
        now = at or datetime.now(timezone.utc)
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True


@dataclass
class AuthorityContext:
    """
    Snapshot of authority information available for a decision or execution check.
    """

    actor: str
    actor_level: AuthorityLevel
    grants: tuple[PermissionGrant, ...] = ()
    approvals: tuple[ApprovalRecord, ...] = ()
    environment: str = "development"

    def has_valid_grant(self, action: str, scope: str = "*") -> bool:
        for grant in self.grants:
            if not grant.is_valid():
                continue
            if grant.action == action or grant.action == "*":
                if scope == "*" or grant.scope == scope or grant.scope == "*":
                    return True
        return False

    def has_valid_approval(self, action: str, category: str) -> bool:
        for approval in self.approvals:
            if (
                approval.is_valid()
                and approval.action == action
                and approval.category == category
            ):
                return True
        return False


def new_id(prefix: str = "") -> str:
    """Generate a short unique identifier."""
    return f"{prefix}{uuid4().hex[:12]}" if prefix else uuid4().hex[:12]


def requires_explicit_approval(category: str) -> bool:
    """Return True if the category is in the mandatory approval list."""
    return category in APPROVAL_REQUIRED_CATEGORIES
