from dataclasses import dataclass, field
from enum import Enum


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


@dataclass(frozen=True)
class SenseResult:
    """
    Structured representation of what BAIG SENSE understands
    about an owner's message.
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
    explanation: str = ""

    def to_dict(self) -> dict:
        """Convert the Sense result into a serializable dictionary."""

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
            "explanation": self.explanation,
        }
