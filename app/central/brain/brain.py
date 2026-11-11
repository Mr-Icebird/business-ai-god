"""
BAIG BRAIN — Intelligence Core (skeleton)

Implements the high-level operating cycle and output contract defined in
the Central System specification (Version 2.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.central.models.authority import new_id
from app.central.models.task import Task


@dataclass
class BrainResult:
    """
    Structured intelligence result handed to MASTER / owner
    (BRAIN output contract).
    """

    brain_result_id: str
    task_id: Optional[str]
    correlation_id: str
    question_and_scope: str
    conclusion_or_recommendation: str
    evidence_references: tuple[str, ...] = ()
    assumptions_and_unknowns: tuple[str, ...] = ()
    confidence_assessment: str = "unknown"
    alternatives_considered: tuple[str, ...] = ()
    authority_status: str = "recommendation"  # recommendation | delegated_decision | approval_required
    operational_request: Optional[dict] = None
    review_triggers: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = field(default_factory=dict)


class Brain:
    """
    Intelligence Core.

    BRAIN receives structured understanding (from SENSE), reasons about it,
    and produces a BrainResult. It does not perform operational coordination;
    that is MASTER's responsibility.
    """

    def __init__(self):
        self._results: dict[str, BrainResult] = {}

    def process(
        self,
        sense_handoff: dict,
        *,
        task: Optional[Task] = None,
        context: Optional[dict] = None,
    ) -> BrainResult:
        """
        Minimal operating cycle — skeleton implementation.

        Real reasoning engines will replace the placeholder logic below.
        """
        correlation_id = (
            task.correlation_id if task else sense_handoff.get("correlation_id", new_id("corr_"))
        )
        question = sense_handoff.get("message") or sense_handoff.get("question") or "No question provided"
        scope = sense_handoff.get("scope") or "unspecified"

        # Placeholder reasoning — will be expanded with real engines later
        conclusion = (
            f"Received understanding for: {question[:120]}. "
            "Full multi-engine reasoning is not yet implemented."
        )
        assumptions = ("This is a skeleton BRAIN response.",)
        confidence = "low — skeleton only"

        # Decide authority status (very conservative for now)
        authority_status = "recommendation"
        operational_request = None

        # If the sense handoff already indicated a high-impact action,
        # flag that approval will be required.
        if sense_handoff.get("requires_approval") or sense_handoff.get("approval_category"):
            authority_status = "approval_required"
            operational_request = {
                "type": "await_approval",
                "category": sense_handoff.get("approval_category"),
                "reason": "High-impact action detected by SENSE",
            }

        result = BrainResult(
            brain_result_id=new_id("brain_"),
            task_id=task.task_id if task else None,
            correlation_id=correlation_id,
            question_and_scope=f"{question} [scope: {scope}]",
            conclusion_or_recommendation=conclusion,
            assumptions_and_unknowns=assumptions,
            confidence_assessment=confidence,
            authority_status=authority_status,
            operational_request=operational_request,
            raw={"sense_handoff": sense_handoff, "context": context or {}},
        )
        self._results[result.brain_result_id] = result
        return result

    def get_result(self, brain_result_id: str) -> Optional[BrainResult]:
        return self._results.get(brain_result_id)


# Singleton
BRAIN = Brain()
