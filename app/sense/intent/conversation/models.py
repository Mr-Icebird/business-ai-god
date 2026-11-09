from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.sense.intent.models import ConfidenceLevel

if TYPE_CHECKING:
    from app.sense.input.models import InputUnderstandingResult
    from app.sense.intent.models import Sense2Result


class ConversationIntent(str, Enum):
    NEW_REQUEST = "new_request"
    FOLLOW_UP = "follow_up"
    CONTINUATION = "continuation"
    CLARIFICATION = "clarification"
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"
    REJECTION = "rejection"
    REFINEMENT = "refinement"
    TOPIC_SWITCH = "topic_switch"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentContext:
    previous_input: InputUnderstandingResult | None = None
    previous_result: Sense2Result | None = None
    previous_user_message: str | None = None
    previous_entity_mentions: tuple[str, ...] = ()

    @property
    def previous_text(self) -> str | None:
        if self.previous_user_message is not None:
            return self.previous_user_message
        if self.previous_input is not None:
            return self.previous_input.raw_input
        if self.previous_result is not None:
            return self.previous_result.raw_text
        return None


@dataclass(frozen=True)
class CorrectionLink:
    relation: str
    previous_interpretation: str | None
    current_correction: str
    previous_value: str | None = None
    replacement_value: str | None = None


@dataclass(frozen=True)
class ConversationDetectionResult:
    intent: ConversationIntent = ConversationIntent.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    context_available: bool = False
    related_to_previous: bool = False
    previous_interpretation: str | None = None
    correction: CorrectionLink | None = None
    topic_switch_from: str | None = None
    topic_switch_to: str | None = None