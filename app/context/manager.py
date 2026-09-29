import re
from uuid import uuid4

from app.context.models import ConversationContext, ConversationState
from app.sense.entity_models import EntitySenseResult
from app.sense.models import (
    ConversationEvent,
    IntentType,
    ScopeType,
    SenseResult,
)


class ConversationContextManager:
    """
    Maintains the active conversational state for BAIG.

    This component coordinates short-term conversation context.
    It does not provide permanent memory or domain knowledge.
    """

    def __init__(self) -> None:
        self._context: ConversationContext | None = None

    def start_conversation(self) -> ConversationContext:
        self._context = ConversationContext(
            conversation_id=str(uuid4()),
            conversation_state=ConversationState.NEW,
        )
        return self._context

    def get_context(self) -> ConversationContext | None:
        return self._context

    def update(
        self,
        sense_result: SenseResult,
        entity_result: EntitySenseResult | None = None,
    ) -> ConversationContext:
        """
        Update conversational state from SENSE.

        Entity Sense can be supplied explicitly, but when it is not,
        the Entity Sense result attached to SenseResult is used
        automatically.
        """

        if self._context is None:
            self.start_conversation()

        context = self._context

        context.turn_number += 1

        if entity_result is None:
            entity_result = sense_result.entity_sense

        self._update_entities(context, sense_result)
        self._update_entity_sense(context, entity_result)

        self._update_intent(context, sense_result)
        self._update_topic(context, sense_result)
        self._update_scope(context, sense_result)
        self._update_clarification(context, sense_result)
        self._update_state(context, sense_result)
        self._update_open_question(context, sense_result)

        context.last_sense_result = sense_result

        return context

    def update_entity_sense(
        self,
        entity_result: EntitySenseResult,
    ) -> ConversationContext:
        """
        Update only the entity/reference portion of context.
        """

        if self._context is None:
            self.start_conversation()

        self._update_entity_sense(
            self._context,
            entity_result,
        )

        return self._context

    def _update_entities(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.entities:
            context.current_entities = sense_result.entities

    def _update_entity_sense(
        self,
        context: ConversationContext,
        entity_result: EntitySenseResult | None,
    ) -> None:
        if entity_result is None:
            return

        context.entity_mentions = entity_result.mentions
        context.entity_references = entity_result.references
        context.entity_relationships = entity_result.relationships

        resolved_entities = [
            reference.refers_to
            for reference in entity_result.references
            if reference.refers_to
        ]

        explicit_entities = [
            mention.text
            for mention in entity_result.mentions
            if mention.text
        ]

        if resolved_entities:
            context.active_entity = resolved_entities[-1]
            context.current_entities = tuple(
                dict.fromkeys(resolved_entities)
            )
            return

        if explicit_entities:
            context.active_entity = explicit_entities[-1]
            context.current_entities = tuple(
                dict.fromkeys(explicit_entities)
            )

    def _update_intent(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.intent == IntentType.UNKNOWN:
            return

        if (
            sense_result.conversation_event
            in (
                ConversationEvent.CONFIRMATION,
                ConversationEvent.NEGATION,
            )
            and context.current_intent != IntentType.UNKNOWN
        ):
            return

        context.current_intent = sense_result.intent

    def _update_topic(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.entities:
            context.current_topic = sense_result.entities[0]

        elif (
            sense_result.entity_sense is not None
            and sense_result.entity_sense.references
        ):
            resolved = [
                reference.refers_to
                for reference in sense_result.entity_sense.references
                if reference.refers_to
            ]

            if resolved:
                context.current_topic = resolved[-1]

    def _update_scope(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.requires_clarification:
            context.current_scope = ScopeType.AMBIGUOUS
            context.current_scope_detail = None
            return

        if sense_result.conversation_event in (
            ConversationEvent.CONFIRMATION,
            ConversationEvent.NEGATION,
        ):
            if context.pending_clarification:
                return

        if (
            sense_result.scope == ScopeType.CLEAR
            and context.current_scope != ScopeType.AMBIGUOUS
        ):
            context.current_scope = ScopeType.CLEAR

        elif sense_result.scope == ScopeType.UNKNOWN:
            return

    def _update_clarification(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.requires_clarification:
            context.pending_clarification = sense_result.message

            if context.original_question is None:
                context.original_question = sense_result.message

            context.clarification_options = tuple(
                self._extract_clarification_options(
                    sense_result.message
                )
            )

            return

        if context.pending_clarification is None:
            return

        if sense_result.conversation_event in (
            ConversationEvent.CONFIRMATION,
            ConversationEvent.NEGATION,
        ):
            return

        selected_option = self._match_clarification_option(
            sense_result.message,
            context.clarification_options,
        )

        if selected_option is not None:
            context.current_scope = ScopeType.CLEAR
            context.current_scope_detail = selected_option
            context.pending_clarification = None
            context.clarification_options = ()

    def _update_state(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        event = sense_result.conversation_event

        if event == ConversationEvent.FAREWELL:
            context.conversation_state = ConversationState.ENDING
            return

        if event == ConversationEvent.DEFERRED_CONTINUATION:
            context.conversation_state = ConversationState.ENDING
            return

        if context.pending_clarification is not None:
            context.conversation_state = (
                ConversationState.CLARIFICATION_NEEDED
            )
            return

        if event == ConversationEvent.CONTINUATION:
            context.conversation_state = ConversationState.CONTINUING
            return

        context.conversation_state = ConversationState.ACTIVE

    def _update_open_question(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        if sense_result.conversation_event in (
            ConversationEvent.FAREWELL,
            ConversationEvent.DEFERRED_CONTINUATION,
        ):
            context.open_question = None
            context.pending_clarification = None
            context.clarification_options = ()
            return

        if context.pending_clarification is not None:
            context.open_question = context.pending_clarification
            return

        if context.conversation_state == ConversationState.ACTIVE:
            context.open_question = None

    @staticmethod
    def _extract_clarification_options(
        message: str,
    ) -> list[str]:
        match = re.search(
            r"\b(?:do you mean|are you referring to|is it|would you like)\s+"
            r"(.+?)\s+or\s+(.+?)(?:[?.!]|$)",
            message,
            flags=re.IGNORECASE,
        )

        if not match:
            return []

        first = match.group(1).strip()
        second = match.group(2).strip()

        return [first, second]

    @staticmethod
    def _match_clarification_option(
        message: str,
        options: tuple[str, ...],
    ) -> str | None:
        normalized_message = message.strip().lower()

        for option in options:
            normalized_option = option.lower().strip()

            if normalized_message == normalized_option:
                return option

            if (
                normalized_message.startswith(
                    normalized_option + " "
                )
                or normalized_message.endswith(
                    " " + normalized_option
                )
            ):
                return option

        return None


CONTEXT_MANAGER = ConversationContextManager()
