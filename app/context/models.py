from dataclasses import dataclass, field
from enum import Enum

from app.sense.models import IntentType, SenseResult, ScopeType


class ConversationState(str, Enum):
    """
    Current state of an active BAIG conversation.
    """

    NEW = "new"
    ACTIVE = "active"
    CLARIFICATION_NEEDED = "clarification_needed"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    CONTINUING = "continuing"
    ENDING = "ending"
    ENDED = "ended"


@dataclass
class ConversationContext:
    """
    Current working context for one conversation.

    This is temporary conversational state.
    It is not BAIG's permanent Memory system.
    """

    conversation_id: str
    turn_number: int = 0

    current_topic: str | None = None
    current_entities: tuple[str, ...] = field(default_factory=tuple)

    current_scope: ScopeType = ScopeType.UNKNOWN
    current_scope_detail: str | None = None

    current_intent: IntentType = IntentType.UNKNOWN

    conversation_state: ConversationState = ConversationState.NEW

    open_question: str | None = None
    original_question: str | None = None

    pending_clarification: str | None = None
    clarification_options: tuple[str, ...] = field(default_factory=tuple)

    last_sense_result: SenseResult | None = None

    def to_dict(self) -> dict:
        """Convert the conversation context into a serializable dictionary."""

        return {
            "conversation_id": self.conversation_id,
            "turn_number": self.turn_number,
            "current_topic": self.current_topic,
            "current_entities": list(self.current_entities),
            "current_scope": self.current_scope.value,
            "current_scope_detail": self.current_scope_detail,
            "current_intent": self.current_intent.value,
            "conversation_state": self.conversation_state.value,
            "open_question": self.open_question,
            "original_question": self.original_question,
            "pending_clarification": self.pending_clarification,
            "clarification_options": list(self.clarification_options),
            "last_sense_result": (
                self.last_sense_result.to_dict()
                if self.last_sense_result
                else None
            ),
        }