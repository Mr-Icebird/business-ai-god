from dataclasses import dataclass, field
from enum import Enum

from app.sense.entity_models import (
    EntityMention,
    EntityReference,
    Relationship,
)
from app.sense.models import IntentType, ScopeType, SenseResult


class ConversationState(str, Enum):
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
    Maintains the short-term state of an active BAIG conversation.

    This includes topics, entities, references, relationships,
    clarification state, and the latest SENSE result.

    It does not provide permanent knowledge or long-term memory.
    """

    conversation_id: str

    turn_number: int = 0

    # Conversation topic and scope
    current_topic: str | None = None
    current_entities: tuple[str, ...] = field(default_factory=tuple)
    current_scope: ScopeType = ScopeType.UNKNOWN
    current_scope_detail: str | None = None
    current_intent: IntentType = IntentType.UNKNOWN

    # Entity/reference state
    active_entity: str | None = None
    entity_mentions: tuple[EntityMention, ...] = field(default_factory=tuple)
    entity_references: tuple[EntityReference, ...] = field(default_factory=tuple)
    entity_relationships: tuple[Relationship, ...] = field(default_factory=tuple)

    # Conversation state
    conversation_state: ConversationState = ConversationState.NEW

    # Questions and clarification
    open_question: str | None = None
    original_question: str | None = None
    pending_clarification: str | None = None
    clarification_options: tuple[str, ...] = field(default_factory=tuple)

    # Latest SENSE result
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

            "active_entity": self.active_entity,

            "entity_mentions": [
                mention.to_dict()
                for mention in self.entity_mentions
            ],

            "entity_references": [
                reference.to_dict()
                for reference in self.entity_references
            ],

            "entity_relationships": [
                relationship.to_dict()
                for relationship in self.entity_relationships
            ],

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
