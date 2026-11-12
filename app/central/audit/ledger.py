"""
BAIG Central System — Audit Ledger (Phase 1.4)

Provides:
1. Structured audit events.
2. Security decision references.
3. Authorization validity periods.
4. Structured reason codes.
5. Input validation.
6. Cross-platform file locking.
7. Recursive sensitive-data sanitization.
8. Durable JSONL writes.
9. Explicit audit write-failure handling.
10. Separate general and authorization outcomes.

Storage: JSONL (Phase 1).

Not yet provided:
- Hash-chain integrity.
- Full tamper-evidence and verification.
- Transactional coordination with MASTER task state.
- Distributed locking across multiple servers.
"""

from __future__ import annotations

import errno
import json
import math
import os
import re
import sys
import time

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.4"

VALID_EVENT_OUTCOMES = frozenset({
    "recorded",
    "success",
    "denied",
    "rejected",
    "error",
})

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

REASON_CODE_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]{0,63}$"
)

GENERAL_CODE_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AuditWriteError(Exception):
    """Raised when a durable audit record cannot be written."""


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return f"audit_{uuid4().hex}"


def _require_string(
    value: Any,
    field_name: str,
    *,
    optional: bool = False,
) -> Optional[str]:

    if value is None and optional:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty")

    return value


def _normalize_datetime(
    value: Optional[datetime],
    field_name: str,
) -> Optional[datetime]:

    if value is None:
        return None

    if not isinstance(value, datetime):
        raise ValueError(
            f"{field_name} must be a datetime or None"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def _validate_string_sequence(
    values: Optional[tuple[str, ...] | list[str]],
    field_name: str,
    *,
    code_pattern: Optional[re.Pattern] = None,
) -> tuple[str, ...]:

    if values is None:
        return ()

    if not isinstance(values, (tuple, list)):
        raise ValueError(
            f"{field_name} must be a tuple or list"
        )

    result = []

    for value in values:
        if not isinstance(value, str):
            raise ValueError(
                f"Every item in {field_name} must be a string"
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field_name} cannot contain empty values"
            )

        if code_pattern and not code_pattern.fullmatch(value):
            raise ValueError(
                f"Invalid code in {field_name}: {value!r}"
            )

        result.append(value)

    if len(result) != len(set(result)):
        raise ValueError(
            f"{field_name} cannot contain duplicate values"
        )

    return tuple(result)


# ---------------------------------------------------------------------------
# JSON-safe conversion
# ---------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """
    Convert supported values into JSON-compatible values.

    Unsupported objects and non-finite floats are rejected.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                "Non-finite floating-point values are not allowed"
            )
        return value

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Nested datetime values must be timezone-aware"
            )
        return value.astimezone(timezone.utc).isoformat()

    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    "JSON object keys must be strings"
                )

            result[key] = _json_safe(item)

        return result

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    raise ValueError(
        f"Unsupported JSON value type: {type(value).__name__}"
    )


# ---------------------------------------------------------------------------
# Sensitive-data sanitization
# ---------------------------------------------------------------------------

SENSITIVE_KEYS = (
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "access_token",
    "refresh_token",
    "credential",
    "credentials",
    "client_secret",
)

TEXT_SECRET_PATTERNS = (
    re.compile(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"
    ),
    re.compile(
        r"(?i)\b(password|passwd|api[_-]?key|"
        r"access[_-]?token|refresh[_-]?token|"
        r"client[_-]?secret)\s*[:=]\s*"
        r"[^\s,;]+"
    ),
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")

    return any(
        sensitive in normalized
        for sensitive in SENSITIVE_KEYS
    )


def _sanitize_text(value: str) -> str:
    result = value

    for pattern in TEXT_SECRET_PATTERNS:
        result = pattern.sub(
            "[REDACTED]",
            result,
        )

    return result


def _sanitize_value(value: Any) -> Any:

    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    "Audit dictionary keys must be strings"
                )

            if _is_sensitive_key(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize_value(item)

        return result

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_value(item)
            for item in value
        ]

    if isinstance(value, str):
        return _sanitize_text(value)

    return value


def _sanitize_mapping(
    value: Optional[dict],
    field_name: str,
) -> dict:

    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError(
            f"{field_name} must be a dictionary"
        )

    sanitized = _sanitize_value(value)

    # Also verify that the resulting data is JSON-compatible.
    return _json_safe(sanitized)


# ---------------------------------------------------------------------------
# Cross-platform file locking
# ---------------------------------------------------------------------------

class FileLock:
    """
    Cross-platform exclusive file lock.

    Windows:
        msvcrt.locking

    Linux / Unix:
        fcntl.flock

    The lock is held on a separate lock file, not on the
    JSONL audit file itself.
    """

    def __init__(
        self,
        file_obj,
        timeout: float = 5.0,
    ):
        if not isinstance(timeout, (int, float)):
            raise ValueError("timeout must be numeric")

        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError(
                "timeout must be a finite non-negative number"
            )

        self.file_obj = file_obj
        self.timeout = float(timeout)
        self._locked = False

    @staticmethod
    def _is_lock_conflict(error: OSError) -> bool:

        if sys.platform == "win32":
            # Windows ERROR_LOCK_VIOLATION.
            return getattr(error, "winerror", None) == 33

        return error.errno in {
            errno.EACCES,
            errno.EAGAIN,
            errno.EWOULDBLOCK,
        }

    def acquire(self) -> None:

        start = time.monotonic()

        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    self.file_obj.seek(0)

                    msvcrt.locking(
                        self.file_obj.fileno(),
                        msvcrt.LK_NBLCK,
                        1,
                    )

                else:
                    import fcntl

                    fcntl.flock(
                        self.file_obj.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )

                self._locked = True
                return

            except OSError as error:

                if not self._is_lock_conflict(error):
                    raise

                elapsed = time.monotonic() - start

                if elapsed >= self.timeout:
                    raise TimeoutError(
                        "Could not acquire audit file lock "
                        f"within {self.timeout} seconds"
                    ) from error

                time.sleep(
                    min(0.05, self.timeout - elapsed)
                )

    def release(self) -> None:

        if not self._locked:
            return

        try:
            if sys.platform == "win32":
                import msvcrt

                self.file_obj.seek(0)

                msvcrt.locking(
                    self.file_obj.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )

            else:
                import fcntl

                fcntl.flock(
                    self.file_obj.fileno(),
                    fcntl.LOCK_UN,
                )

        finally:
            self._locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


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

    applied_limits: dict[str, Any] = field(
        default_factory=dict
    )

    unmet_conditions: tuple[str, ...] = ()

    security_decision_ref: Optional[str] = None

    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    reason_codes: tuple[str, ...] = ()

    details: dict[str, Any] = field(
        default_factory=dict
    )

    environment: str = "development"

    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:

        data = asdict(self)

        data["timestamp"] = _normalize_datetime(
            self.timestamp,
            "timestamp",
        ).isoformat()

        data["valid_from"] = (
            _normalize_datetime(
                self.valid_from,
                "valid_from",
            ).isoformat()
            if self.valid_from is not None
            else None
        )

        data["expires_at"] = (
            _normalize_datetime(
                self.expires_at,
                "expires_at",
            ).isoformat()
            if self.expires_at is not None
            else None
        )

        data["risk_categories"] = list(
            self.risk_categories
        )

        data["unmet_conditions"] = list(
            self.unmet_conditions
        )

        data["reason_codes"] = list(
            self.reason_codes
        )

        return _json_safe(data)


# ---------------------------------------------------------------------------
# Audit Ledger
# ---------------------------------------------------------------------------

class AuditLedger:

    def __init__(
        self,
        path: str | Path = "logs/baig_audit.jsonl",
        lock_timeout: float = 5.0,
    ):

        self.path = Path(path)
        self.lock_path = Path(
            str(self.path) + ".lock"
        )

        if not isinstance(lock_timeout, (int, float)):
            raise ValueError(
                "lock_timeout must be numeric"
            )

        if (
            not math.isfinite(lock_timeout)
            or lock_timeout < 0
        ):
            raise ValueError(
                "lock_timeout must be finite and non-negative"
            )

        self.lock_timeout = float(lock_timeout)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ------------------------------------------------------------------
    # General event recording
    # ------------------------------------------------------------------

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

        security_decision_ref: Optional[str] = None,

        valid_from: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,

        reason_codes: Optional[tuple[str, ...]] = None,

        details: Optional[dict] = None,

        environment: str = "development",
    ) -> AuditEvent:

        # Normalize required strings first.
        event_type = _require_string(
            event_type,
            "event_type",
        )

        actor = _require_string(
            actor,
            "actor",
        )

        action = _require_string(
            action,
            "action",
        )

        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"Unknown event_type: {event_type}"
            )

        if outcome not in VALID_EVENT_OUTCOMES:
            raise ValueError(
                f"Invalid outcome: {outcome}"
            )

        if (
            auth_outcome is not None
            and auth_outcome not in VALID_AUTH_OUTCOMES
        ):
            raise ValueError(
                f"Invalid auth_outcome: {auth_outcome}"
            )

        # Validate optional string fields.
        optional_string_fields = {
            "target_type": target_type,
            "target_id": target_id,
            "task_id": task_id,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "provenance_ref": provenance_ref,
            "old_state": old_state,
            "new_state": new_state,
            "grant_id": grant_id,
            "approval_id": approval_id,
            "decision_id": decision_id,
            "requester_id": requester_id,
            "executor_id": executor_id,
            "policy_version": policy_version,
            "security_decision_ref": security_decision_ref,
        }

        normalized_fields = {}

        for name, value in optional_string_fields.items():
            normalized_fields[name] = _require_string(
                value,
                name,
                optional=True,
            )

        target_type = normalized_fields["target_type"]
        target_id = normalized_fields["target_id"]

        if target_id is not None and target_type is None:
            raise ValueError(
                "target_type is required when target_id is supplied"
            )

        # Validate reason and environment.
        if not isinstance(reason, str):
            raise ValueError("reason must be a string")

        reason = _sanitize_text(reason.strip())

        environment = _require_string(
            environment,
            "environment",
        )

        # Validate datetime fields.
        valid_from = _normalize_datetime(
            valid_from,
            "valid_from",
        )

        expires_at = _normalize_datetime(
            expires_at,
            "expires_at",
        )

        if (
            valid_from is not None
            and expires_at is not None
            and valid_from >= expires_at
        ):
            raise ValueError(
                "valid_from must be earlier than expires_at"
            )

        # Validate sequences.
        risk_categories = _validate_string_sequence(
            risk_categories,
            "risk_categories",
            code_pattern=GENERAL_CODE_PATTERN,
        )

        unmet_conditions = _validate_string_sequence(
            unmet_conditions,
            "unmet_conditions",
        )

        reason_codes = _validate_string_sequence(
            reason_codes,
            "reason_codes",
            code_pattern=REASON_CODE_PATTERN,
        )

        # Validate and sanitize dictionaries.
        safe_details = _sanitize_mapping(
            details,
            "details",
        )

        safe_limits = _sanitize_mapping(
            applied_limits,
            "applied_limits",
        )

        event = AuditEvent(
            event_id=_new_event_id(),
            event_type=event_type,
            actor=actor,
            action=action,
            timestamp=_utc_now(),

            outcome=outcome,

            target_type=target_type,
            target_id=target_id,

            task_id=normalized_fields["task_id"],
            workflow_id=normalized_fields["workflow_id"],
            correlation_id=normalized_fields["correlation_id"],
            provenance_ref=normalized_fields["provenance_ref"],

            reason=reason,

            old_state=normalized_fields["old_state"],
            new_state=normalized_fields["new_state"],

            grant_id=normalized_fields["grant_id"],
            approval_id=normalinormalized_fields["approval_id"],
            decision_id=normalized_fields["decision_id"],

            auth_outcome=auth_outcome,

            requester_id=normalized_fields["requester_id"],
            executor_id=normalized_fields["executor_id"],

            policy_version=normalized_fields["policy_version"],

            risk_categories=risk_categories,
            applied_limits=safe_limits,
            unmet_conditions=unmet_conditions,

            security_decision_ref=normalized_fields[
                "security_decision_ref"
            ],

            valid_from=valid_from,
            expires_at=expires_at,

            reason_codes=reason_codes,

            details=safe_details,

            environment=environment,

            schema_version=SCHEMA_VERSION,
        )

        self._append(event)

        return event

    # ------------------------------------------------------------------
    # Task transition recording
    # ------------------------------------------------------------------

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
        reason_codes: Optional[tuple[str, ...]] = None,
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
            reason_codes=reason_codes,

            environment=environment,
        )

    # ------------------------------------------------------------------
    # Authorization recording
    # ------------------------------------------------------------------

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

        security_decision_ref: Optional[str] = None,

        valid_from: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,

        reason_codes: Optional[tuple[str, ...]] = None,

        environment: str = "development",

        details: Optional[dict] = None,
    ) -> AuditEvent:

        if auth_outcome not in VALID_AUTH_OUTCOMES:
            raise ValueError(
                f"Invalid auth_outcome: {auth_outcome}"
            )

        general_outcome = {
            "ALLOW": "success",
            "DENY": "denied",
            "REQUIRE_APPROVAL": "recorded",
            "INDETERMINATE": "error",
        }[auth_outcome]

        if target_id is None and task_id is not None:
            target_id = task_id

        if target_type is None and target_id is not None:
            target_type = "task" if task_id else None

        return self.record(
            event_type="authorization.decision",

            actor=actor,
            action=action,

            outcome=general_outcome,
            auth_outcome=auth_outcome,

            target_type=target_type,
            target_id=target_id,

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

            security_decision_ref=security_decision_ref,

            valid_from=valid_from,
            expires_at=expires_at,

            reason_codes=reason_codes,

            details=details,

            environment=environment,
        )

    # ------------------------------------------------------------------
    # Durable JSONL append
    # ------------------------------------------------------------------

    def _append(self, event: AuditEvent) -> None:

        try:
            # Serialization is inside the error-handling boundary.
            line = (
                json.dumps(
                    event.to_dict(),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )

            # Use a separate lock file so the audit data remains
            # a clean JSONL file on both Windows and Unix.
            with self.lock_path.open("a+b") as lock_file:

                # Ensure byte zero exists for Windows byte-range locking.
                lock_file.seek(0, os.SEEK_END)

                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                    os.fsync(lock_file.fileno())

                with FileLock(
                    lock_file,
                    timeout=self.lock_timeout,
                ):

                    with self.path.open(
                        "a",
                        encoding="utf-8",
                        newline="\n",
                    ) as audit_file:

                        audit_file.write(line)
                        audit_file.flush()
                        os.fsync(audit_file.fileno())

        except Exception as error:
            raise AuditWriteError(
                f"Failed to write audit event "
                f"{event.event_id}: {error}"
            ) from error


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

AUDIT_LEDGER = AuditLedger()
