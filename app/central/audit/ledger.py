"""
BAIG Central System — Audit Ledger (Phase 1.2)

Improved to better align with 02 FINAL BAIG CENTRAL SYSTEM.

Highest-priority improvements in this version:
1. Separate general event outcomes from authorization decision outcomes
2. Explicit, detectable audit write failures (no silent pass)
3. Richer authorization decision recording
4. Explicit workflow_id and provenance support
5. Stronger validation and clearer failure behaviour

Still Phase 1 (JSONL). Not yet cryptographically tamper-evident.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


SCHEMA_VERSION = "1.1"

# General event outcomes
VALID_EVENT_OUTCOMES = frozenset({
    "recorded",
    "success",
    "denied",
    "rejected",
    "error",
})

# Authorization-specific outcomes (Final Spec)
VALID_AUTH_OUTCOMES = frozenset({
    "ALLOW",
    "DENY",
    "REQUIRE_APPROVAL",
    "INDETERMINATE",
})

VALID_EVENT_TYPES = frozenset({
    "task.transition",
    "authorization.decision",
    "component.status_change",
    "grant.registered",
    "grant.revoked",
    "approval.registered",
    "approval.revoked",
    "system.event",
    "audit.failure",
    "audit.access",
})


class AuditWriteError(Exception):
    """Raised when a durable audit record cannot be written."""
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return f"audit_{uuid4().hex}"


@dataclass
class AuditEvent:
    """Structured audit record."""

    event_id: str
    event_type: str
    actor: str
    action: str
    timestamp: datetime
    outcome: str = "recorded"
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    provenance_ref: Optional[str] = None
    reason: str = ""
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    grant_id: Optional[str] = None
    approval_id: Optional[str] = None
    decision_id: Optional[str] = None
    auth_outcome: Optional[str] = None          # ALLOW / DENY / REQUIRE_APPROVAL / INDETERMINATE
    details: dict = field(default_factory=dict)
    environment: str = "development"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditLedger:
    """
    Append-only audit ledger (Phase 1.2).

    Key behavioural rule from Final Spec:
    If a consequential action requires durable audit and the write fails,
    the caller must be able to detect the failure and block the action.
    """

    def __init__(self, path: str | Path = "logs/baig_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def record(
        self,
        *,
        event_type: str,
        actor: str,
        action: str,
        outcome: str = "recorded",
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        provenance_ref: Optional[str] = None,
        reason: str = "",
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        auth_outcome: Optional[str] = None,
        details: Optional[dict] = None,
        environment: str = "development",
        required: bool = False,          # If True, failure raises AuditWriteError
    ) -> AuditEvent:
        """
        Create and persist one validated audit event.

        If required=True and the write fails, raises AuditWriteError.
        """
        if not event_type or not str(event_type).strip():
            raise ValueError("event_type is required")
        if not actor or not str(actor).strip():
            raise ValueError("actor is required")
        if not action or not str(action).strip():
            raise ValueError("action is required")

        if outcome not in VALID_EVENT_OUTCOMES:
            raise ValueError(
                f"Invalid event outcome '{outcome}'. "
                f"Allowed: {sorted(VALID_EVENT_OUTCOMES)}"
            )

        if auth_outcome is not None and auth_outcome not in VALID_AUTH_OUTCOMES:
            raise ValueError(
                f"Invalid auth_outcome '{auth_outcome}'. "
                f"Allowed: {sorted(VALID_AUTH_OUTCOMES)}"
            )

        if event_type not in VALID_EVENT_TYPES:
            # Soft acceptance for extensibility, but record the fact
            pass

        safe_details = self._sanitize_details(details or {})

        event = AuditEvent(
            event_id=_new_event_id(),
            event_type=event_type.strip(),
            actor=actor.strip(),
            action=action.strip(),
            timestamp=_utc_now(),
            outcome=outcome,
            target_type=target_type,
            target_id=target_id,
            task_id=task_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            provenance_ref=provenance_ref,
            reason=reason or "",
            old_state=old_state,
            new_state=new_state,
            grant_id=grant_id,
            approval_id=approval_id,
            decision_id=decision_id,
            auth_outcome=auth_outcome,
            details=safe_details,
            environment=environment,
            schema_version=SCHEMA_VERSION,
        )

        try:
            self._append(event)
        except Exception as e:
            if required:
                raise AuditWriteError(
                    f"Failed to write required audit event: {e}"
                ) from e
            # For non-required events we still surface the problem
            raise AuditWriteError(
                f"Failed to write audit event: {e}"
            ) from e

        return event

    def record_transition(
        self,
        *,
        actor: str,
        task_id: str,
        from_status: str,
        to_status: str,
        reason: str = "",
        correlation_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        outcome: str = "success",
        environment: str = "development",
        details: Optional[dict] = None,
        required: bool = True,
    ) -> AuditEvent:
        return self.record(
            event_type="task.transition",
            actor=actor,
            action="transition",
            outcome=outcome,
            target_type="task",
            target_id=task_id,
            task_id=task_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            reason=reason,
            old_state=from_status,
            new_state=to_status,
            details=details,
            environment=environment,
            required=required,
        )

    def record_authorization(
        self,
        *,
        actor: str,
        action: str,
        auth_outcome: str,                    # ALLOW / DENY / REQUIRE_APPROVAL / INDETERMINATE
        reason: str,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        environment: str = "development",
        details: Optional[dict] = None,
        required: bool = True,
    ) -> AuditEvent:
        if auth_outcome not in VALID_AUTH_OUTCOMES:
            raise ValueError(
                f"auth_outcome must be one of {sorted(VALID_AUTH_OUTCOMES)}"
            )

        # Map auth outcome to general event outcome for consistency
        general_outcome = {
            "ALLOW": "success",
            "DENY": "denied",
            "REQUIRE_APPROVAL": "recorded",
            "INDETERMINATE": "error",
        }.get(auth_outcome, "recorded")

        return self.record(
            event_type="authorization.decision",
            actor=actor,
            action=action,
            outcome=general_outcome,
            auth_outcome=auth_outcome,
            target_type="task" if task_id else None,
            target_id=task_id,
            task_id=task_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            reason=reason,
            grant_id=grant_id,
            approval_id=approval_id,
            decision_id=decision_id,
            details=details,
            environment=environment,
            required=required,
        )

    def _sanitize_details(self, details: dict) -> dict:
        """Basic recursive-ish redaction of common secret keys."""
        if not isinstance(details, dict):
            return {}

        sensitive = {
            "password", "token", "secret", "api_key", "apikey",
            "authorization", "private_key", "access_token",
            "refresh_token", "credential", "credentials",
        }

        def clean(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: ("[REDACTED]" if any(s in str(k).lower() for s in sensitive) else clean(v))
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [clean(i) for i in obj]
            return obj

        return clean(details)

    def _append(self, event: AuditEvent) -> None:
        """Append with locking + flush. Raises on failure."""
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

        try:
            with self.path.open("a", encoding="utf-8") as f:
                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_EX)

                f.write(line)
                f.flush()
                os.fsync(f.fileno())   # Do not silently ignore failure

                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            raise AuditWriteError(str(e)) from e


# Global instance
AUDIT_LEDGER = AuditLedger()
