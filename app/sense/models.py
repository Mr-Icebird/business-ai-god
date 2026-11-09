from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from app.sense.entity_models import EntitySenseResult

if TYPE_CHECKING:
    from app.sense.domain.models import DomainUnderstandingResult
    from app.sense.input.models import InputUnderstandingResult
    from app.sense.intent.models import Sense2Result


class IntentType(str, Enum):
    UNKNOWN = "unknown"
    CONVERSATIONAL = "conversational"
    INQUIRY = "inquiry"
    EXPLANATION = "explanation"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    ACTION = "action"


class ScopeType(str, Enum):
    UNKNOWN = "unknown"
    CLEAR = "clear"
    AMBIGUOUS = "ambiguous"


class ConversationEvent(str, Enum):
    NONE = "none"
    GREETING = "greeting"
    FAREWELL = "farewell"
    DEFERRED_CONTINUATION = "deferred_continuation"
    CONTINUATION = "continuation"
    ATTENTION = "attention"
    ACKNOWLEDGEMENT = "acknowledgement"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"


class TimePeriod(str, Enum):
    UNKNOWN = "unknown"
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class ClarificationDimension(str, Enum):
    INTENT = "intent"
    TASK = "task"
    DOMAIN = "domain"
    SCOPE = "scope"


@dataclass(frozen=True)
class ClarificationEvidence:
    text: str
    component: str
    source_span: tuple[int, int] | None = None
    source_text: str | None = None


@dataclass(frozen=True)
class ClarificationIssue:
    dimension: ClarificationDimension
    reason: str
    evidence: tuple[ClarificationEvidence, ...] = field(default_factory=tuple)
    candidates: tuple[str, ...] = field(default_factory=tuple)
    question: str = ""


@dataclass(frozen=True)
class SenseResult:
    """
    Structured representation of what BAIG SENSE understands
    about an owner's message.

    Entity Sense is optional during the incremental SENSE build.
    """

    message: str
    intent: IntentType
    entities: tuple[str, ...] = field(default_factory=tuple)
    context: str = "unknown"
    scope: ScopeType = ScopeType.UNKNOWN
    conversation_event: ConversationEvent = ConversationEvent.NONE
    time_period: TimePeriod = TimePeriod.UNKNOWN
    addressed_to_baig: bool = False
    requires_clarification: bool = False
    clarification_dimensions: tuple[ClarificationDimension, ...] = field(
        default_factory=tuple
    )
    clarification_issues: tuple[ClarificationIssue, ...] = field(default_factory=tuple)
    clarification_questions: tuple[str, ...] = field(default_factory=tuple)
    clarification_question: str | None = None
    explanation: str = ""

    # Entity / reference / relationship understanding.
    entity_sense: EntitySenseResult | None = None

    # Structured results from the staged SENSE input/intent/domain pipeline.
    input_sense: InputUnderstandingResult | None = None
    intent_sense: Sense2Result | None = None
    domain_sense: DomainUnderstandingResult | None = None

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "intent": self.intent.value,
            "entities": list(self.entities),
            "context": self.context,
            "scope": self.scope.value,
            "conversation_event": self.conversation_event.value,
            "time_period": self.time_period.value,
            "addressed_to_baig": self.addressed_to_baig,
            "requires_clarification": self.requires_clarification,
            "clarification_dimensions": [
                item.value for item in self.clarification_dimensions
            ],
            "clarification_issues": [
                {
                    "dimension": item.dimension.value,
                    "reason": item.reason,
                    "evidence": [
                        {
                            "text": evidence.text,
                            "component": evidence.component,
                            "source_span": (
                                list(evidence.source_span)
                                if evidence.source_span is not None
                                else None
                            ),
                            "source_text": evidence.source_text,
                        }
                        for evidence in item.evidence
                    ],
                    "candidates": list(item.candidates),
                    "question": item.question,
                }
                for item in self.clarification_issues
            ],
            "clarification_questions": list(self.clarification_questions),
            "clarification_question": self.clarification_question,
            "explanation": self.explanation,
            "entity_sense": (
                self.entity_sense.to_dict() if self.entity_sense else None
            ),
            "input_sense": (self.input_sense.to_dict() if self.input_sense else None),
            "intent_sense": (
                self.intent_sense.to_dict() if self.intent_sense else None
            ),
            "domain_sense": (
                self.domain_sense.to_dict() if self.domain_sense else None
            ),
        }
