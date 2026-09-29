import re
from uuid import uuid4

from app.context.models import ConversationContext, ConversationState
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
        """Start a new conversation context."""

        self._context = ConversationContext(
            conversation_id=str(uuid4()),
            conversation_state=ConversationState.NEW,
        )

        return self._context

    def get_context(self) -> ConversationContext | None:
        """Return the active conversation context."""

        return self._context

    def update(
        self,
        sense_result: SenseResult,
    ) -> ConversationContext:
        """
        Update conversation state from a SENSE result.
        """

        if self._context is None:
            self.start_conversation()

        context = self._context
        context.turn_number += 1

        self._update_entities(context, sense_result)
        self._update_intent(context, sense_result)
        self._update_topic(context, sense_result)
        self._update_scope(context, sense_result)
        self._update_clarification(context, sense_result)
        self._update_state(context, sense_result)
        self._update_open_question(context, sense_result)

        context.last_sense_result = sense_result

        return context

    def _update_entities(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        """Update currently active entities."""

        if sense_result.entities:
            context.current_entities = sense_result.entities

    def _update_intent(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        """
        Update the current intent without allowing a short clarification
        response to erase the meaningful intent of the conversation.
        """

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
        """Update the current conversational topic."""

        if sense_result.entities:
            context.current_topic = sense_result.entities[0]

    def _update_scope(
        self,
        context: ConversationContext,
        sense_result: SenseResult,
    ) -> None:
        """
        Update scope without incorrectly converting ambiguity into clarity.

        A new ambiguous topic clears the previous scope detail because
        the previous scope belongs to the previous topic.
        """

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
        """
        Track clarification questions and resolve explicit option selections.
        """

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
        """Update the high-level conversation state."""

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
        """Track the current unresolved question."""

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
        """
        Extract simple alternatives from a clarification question.

        This is intentionally lightweight. Full semantic option extraction
        belongs to future Sense / Entity intelligence.
        """

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

        return [
            first,
            second,
        ]

    @staticmethod
    def _match_clarification_option(
        message: str,
        options: tuple[str, ...],
    ) -> str | None:
        """
        Match an explicit owner response against pending clarification options.
        """

        normalized_message = message.strip().lower()

        for option in options:
            normalized_option = option.lower().strip()

            if normalized_message == normalized_option:
                return option

            if (
                normalized_message.startswith(normalized_option + " ")
                or normalized_message.endswith(" " + normalized_option)
            ):
                return option

        return None


CONTEXT = ConversationContextManager()
