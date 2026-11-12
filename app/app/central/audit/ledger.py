"""
BAIG Central System — Audit Ledger (Phase 1)

Lightweight, structured, append-only audit recording.
Supports the Final Specification requirements for:
- Traceability
- No hidden transitions
- Recording of actor, action, reason, old/new state, timestamps
- Correlation IDs

This is a development-stage durable ledger (JSONL file).
It is not yet a full production-grade, cryptographically
tamper-evident store. That can be added later.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_event_id() -> str:
    return f"audit_{uuid4().hex[:12]}"


@dataclass
class AuditEvent:
    """
    Single structured audit record.
    """

    event_id: str
    event_type: str
    actor: str
    action: str
    timestamp: datetime
    outcome: str = "recorded"          # recorded / success / denied / rejected / error
    target_type: Optional[str] = None  # e.g. "task", "grant", "approval", "component"
    target_id: Optional[str] = None
    correlation_id: Optional[str] = None
    reason: str = ""
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    details: dict = field(default_factory=dict)
    environment: str = "development"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditLedger:
    """
    Simple append-only audit ledger.

    Phase 1 storage: JSON Lines file.
    Later this can be replaced by a database or hash-chained store
    without changing the calling code.
    """

    def __init__(self, path: str | Path = "logs/baig_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure the file exists
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
        correlation_id: Optional[str] = None,
        reason: str = "",
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        details: Optional[dict] = None,
        environment: str = "development",
    ) -> AuditEvent:
        """
        Create and persist one audit event.
        """
        event = AuditEvent(
            event_id=_new_event_id(),
            event_type=event_type,
            actor=actor,
            action=action,
            timestamp=_utc_now(),
            outcome=outcome,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
            reason=reason,
            old_state=old_state,
            new_state=new_state,
            details=details or {},
            environment=environment,
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
        outcome: str = "success",
        environment: str = "development",
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """
        Convenience method for task state transitions.
        """
        return self.record(
            event_type="task.transition",
            actor=actor,
            action="transition",
            outcome=outcome,
            target_type="task",
            target_id=task_id,
            correlation_id=correlation_id,
            reason=reason,
            old_state=from_status,
            new_state=to_status,
            details=details or {},
            environment=environment,
        )

    def record_authorization(
        self,
        *,
        actor: str,
        action: str,
        allowed: bool,
        reason: str,
        task_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        grant_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        environment: str = "development",
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """
        Convenience method for authorization decisions.
        """
        return self.record(
            event_type="authorization.decision",
            actor=actor,
            action=action,
            outcome="allowed" if allowed else "denied",
            target_type="task" if task_id else None,
            target_id=task_id,
            correlation_id=correlation_id,
            reason=reason,
            details={
                **(details or {}),
                "grant_id": grant_id,
                "approval_id": approval_id,
            },
            environment=environment,
        )

    def _append(self, event: AuditEvent) -> None:
        """Append one event as a JSON line."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")


# Global ledger instance used by MASTER and other components
# Can later be replaced by a more advanced implementation.
AUDIT_LEDGER = AuditLedger()
