"""
BAIG Central System — Audit Ledger (Phase 1.3 + Cross-Platform Locking)

Adds reliable file locking that works on both Windows and Linux/Unix.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# ---------------------------------------------------------------------------
# Cross-platform file locking
# ---------------------------------------------------------------------------

class FileLock:
    """
    Cross-platform exclusive file lock with clearer error handling.

    - Windows: msvcrt.locking
    - Linux/Unix: fcntl.flock

    Distinguishes genuine lock conflicts (retryable) from other OS errors.
    """

    def __init__(self, file_obj, timeout: float = 5.0):
        self.file_obj = file_obj
        self.timeout = timeout
        self._locked = False

    def acquire(self) -> None:
        start = time.monotonic()

        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self.file_obj.seek(0)
                    # Non-blocking lock of 1 byte
                    msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                self._locked = True
                return

            except (OSError, IOError) as e:
                # On Windows, msvcrt raises OSError when the lock is held.
                # On Unix, fcntl also raises OSError / BlockingIOError.
                # We only retry when it looks like a genuine lock conflict.
                err_no = getattr(e, "errno", None)
                winerror = getattr(e, "winerror", None)

                # Common lock-conflict indicators
                is_lock_conflict = (
                    isinstance(e, BlockingIOError)
                    or err_no in (11, 35, 36)          # EAGAIN / EDEADLK / etc.
                    or winerror in (33, 36)            # Windows lock violations
                    or "locked" in str(e).lower()
                    or "resource temporarily unavailable" in str(e).lower()
                )

                if not is_lock_conflict:
                    # Real storage / permission / handle error → fail immediately
                    raise

                if time.monotonic() - start >= self.timeout:
                    raise TimeoutError(
                        f"Could not acquire audit file lock within {self.timeout}s"
                    ) from e

                time.sleep(0.05)

    def release(self) -> None:
        if not self._locked:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self.file_obj.seek(0)
                msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_UN)
        finally:
            self._locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.3"

VALID_EVENT_OUTCOMES = frozenset({
    "recorded", "success", "denied", "rejected", "error",
})

VALID_AUTH_OUTCOMES = frozenset({
    "ALLOW", "DENY", "REQUIRE_APPROVAL", "INDETERMINATE",
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


# ---------------------------------------------------------------------------
# Audit Event
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
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
    auth_outcome: Optional[str] = None
    requester_id: Optional[str] = None
    executor_id: Optional[str] = None
    policy_version: Optional[str] = None
    risk_categories: tuple[str, ...] = ()
    applied_limits: dict = field(default_factory=dict)
    unmet_conditions: tuple[str, ...] = ()
    details: dict = field(default_factory=dict)
    environment: str = "development"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["risk_categories"] = list(self.risk_categories)
        data["unmet_conditions"] = list(self.unmet_conditions)
        return data


# ---------------------------------------------------------------------------
# Audit Ledger
# ---------------------------------------------------------------------------

class AuditLedger:
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
        requester_id: Optional[str] = None,
        executor_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        risk_categories: Optional[tuple[str, ...]] = None,
        applied_limits: Optional[dict] = None,
        unmet_conditions: Optional[tuple[str, ...]] = None,
        details: Optional[dict] = None,
        environment: str = "development",
    ) -> AuditEvent:
        if not event_type or not str(event_type).strip():
            raise ValueError("event_type is required")
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Unknown event_type '{event_type}'. Allowed: {sorted(VALID_EVENT_TYPES)}"
            )
        if not actor or not str(actor).strip():
            raise ValueError("actor is required")
        if not action or not str(action).strip():
            raise ValueError("action is required")
        if outcome not in VALID_EVENT_OUTCOMES:
            raise ValueError(f"Invalid outcome '{outcome}'")
        if auth_outcome is not None and auth_outcome not in VALID_AUTH_OUTCOMES:
            raise ValueError(f"Invalid auth_outcome '{auth_outcome}'")

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
            requester_id=requester_id,
            executor_id=executor_id,
            policy_version=policy_version,
            risk_categories=risk_categories or (),
            applied_limits=applied_limits or {},
            unmet_conditions=unmet_conditions or (),
            details=safe_details,
            environment=environment,
            schema_version=SCHEMA_VERSION,
        )

        self._append(event)
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
        )

    def record_authorization(
        self,
        *,
        actor: str,
        action: str,
        auth_outcome: str,
        reason: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        executor_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        risk_categories: Optional[tuple[str, ...]] = None,
        applied_limits: Optional[dict] = None,
        unmet_conditions: Optional[tuple[str, ...]] = None,
        environment: str = "development",
        details: Optional[dict] = None,
    ) -> AuditEvent:
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
            target_type=target_type or ("task" if task_id else None),
            target_id=target_id or task_id,
            task_id=task_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            reason=reason,
            grant_id=grant_id,
            approval_id=approval_id,
            decision_id=decision_id,
            requester_id=requester_id,
            executor_id=executor_id,
            policy_version=policy_version,
            risk_categories=risk_categories,
            applied_limits=applied_limits,
            unmet_conditions=unmet_conditions,
            details=details,
            environment=environment,
        )

    def _sanitize_details(self, details: dict) -> dict:
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
        """Append with cross-platform exclusive lock + flush."""
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

        try:
            # Open in a+ so we can seek for Windows locking
            with self.path.open("a+", encoding="utf-8") as f:
                with FileLock(f, timeout=5.0):
                    f.seek(0, os.SEEK_END)
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
        except Exception as e:
            raise AuditWriteError(f"Failed to write audit event: {e}") from e


# Global instance
AUDIT_LEDGER = AuditLedger()
