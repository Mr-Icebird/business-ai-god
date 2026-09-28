import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.sense.models import (
    ConversationEvent,
    IntentType,
    ScopeType,
    SenseResult,
    TimePeriod,
)


class SenseEngine:
    """
    First-stage BAIG Sense engine.

    SENSE interprets language, conversation events, basic time context,
    intent, entities, ambiguity, and simple conversational responses.

    Deeper knowledge and world understanding will come from other
    BAIG systems.
    """

    TIME_ZONE = ZoneInfo("Africa/Lagos")

    INTENT_PATTERNS = {
        IntentType.EXPLANATION: (
            r"\bexplain\b",
            r"\bwhat does\b",
            r"\bwhat do you mean\b",
            r"\bmeaning of\b",
        ),
        IntentType.ANALYSIS: (
            r"\banalyze\b",
            r"\banalysis\b",
            r"\banalyse\b",
        ),
        IntentType.RESEARCH: (
            r"\bresearch\b",
            r"\binvestigate\b",
            r"\bfind out\b",
            r"\blook into\b",
        ),
        IntentType.ACTION: (
            r"\bexecute\b",
            r"\bcreate\b",
            r"\bbuild\b",
            r"\brun\b",
        ),
        IntentType.INQUIRY: (
            r"\bwhat\b",
            r"\bwhat's\b",
            r"\bwhats\b",
            r"\bhow\b",
            r"\bwhy\b",
            r"\btell me\b",
            r"\bi want to know\b",
            r"\bi'd like to know\b",
            r"\bid like to know\b",
            r"\bcan you tell me\b",
            r"\bcould you tell me\b",
            r"\bi want information\b",
            r"\bi need to know\b",
            r"\bdo you mean\b",
            r"\bare you saying\b",
            r"\bare you talking about\b",
            r"\bwhich one do you mean\b",
        ),
    }

    GREETING_PATTERNS = (
        r"^hello\b",
        r"^hi\b",
        r"^hey\b",
        r"^good morning\b",
        r"^good afternoon\b",
        r"^good evening\b",
    )

    FAREWELL_PATTERNS = (
        r"\bgoodbye\b",
        r"\bbye\b",
        r"\bsee you\b",
        r"\btalk to you later\b",
        r"\bsee you later\b",
        r"^good night\b",
        r"\bgood night\b",
    )

    DEFERRED_CONTINUATION_PATTERNS = (
        r"\bcontinue tomorrow\b",
        r"\blet's continue tomorrow\b",
        r"\blets continue tomorrow\b",
        r"\bwe can continue tomorrow\b",
        r"\bwe'll continue tomorrow\b",
        r"\bwe will continue tomorrow\b",
        r"\bcontinue later\b",
        r"\blet's continue later\b",
        r"\blets continue later\b",
        r"\bwe can continue later\b",
        r"\bwe'll continue later\b",
        r"\bwe will continue later\b",
    )

    CONTINUATION_PATTERNS = (
        r"^go on[.!?]*$",
        r"^continue[.!?]*$",
        r"^keep going[.!?]*$",
        r"^carry on[.!?]*$",
        r"^go ahead[.!?]*$",
    )

    ACKNOWLEDGEMENT_PATTERNS = (
        r"^okay[.!?]*$",
        r"^ok[.!?]*$",
        r"^alright[.!?]*$",
        r"^all right[.!?]*$",
        r"^understood[.!?]*$",
        r"^got it[.!?]*$",
        r"^i understand[.!?]*$",
    )

    CONFIRMATION_PATTERNS = (
        r"^yes[.!?]*$",
        r"^yeah[.!?]*$",
        r"^yep[.!?]*$",
        r"^correct[.!?]*$",
        r"^that's right[.!?]*$",
        r"^that is right[.!?]*$",
    )

    NEGATION_PATTERNS = (
        r"^no[.!?]*$",
        r"^nope[.!?]*$",
        r"^not really[.!?]*$",
        r"^that's not right[.!?]*$",
        r"^that is not right[.!?]*$",
    )

    ATTENTION_PATTERNS = (
        r"^baig[.!?]*$",
        r"^hey baig[.!?]*$",
        r"^hello baig[.!?]*$",
        r"^hi baig[.!?]*$",
    )

    BAIG_ADDRESS_PATTERNS = (
        r"\bbaig\b",
    )

    CURRENT_CONTEXT_PATTERNS = (
        r"\bwhat's up\b",
        r"\bwhats up\b",
        r"\bwhat is happening\b",
        r"\bwhat's happening\b",
        r"\bwhats happening\b",
        r"\bwhat happened\b",
        r"\bright now\b",
        r"\btoday\b",
        r"\bcurrently\b",
        r"\bnow\b",
    )

    AMBIGUOUS_ENTITIES = {
        "oil",
        "gold",
        "silver",
        "bitcoin",
        "crypto",
    }

    def understand(
        self,
        message: str,
        current_time: datetime | None = None,
        previous_message: str | None = None,
        previous_result: SenseResult | None = None,
    ) -> SenseResult:
        """
        Create a structured first-stage interpretation.

        previous_message and previous_result allow SENSE to eventually
        interpret short conversational responses using conversation context.
        """

        cleaned = message.strip()

        if not cleaned:
            return SenseResult(
                message=message,
                intent=IntentType.UNKNOWN,
                explanation="The message is empty.",
            )

        normalized = cleaned.lower()
        now = current_time or datetime.now(self.TIME_ZONE)

        conversation_event = self._detect_conversation_event(normalized)
        addressed_to_baig = self._is_addressed_to_baig(normalized)
        time_period = self._detect_time_period(now)

        if conversation_event != ConversationEvent.NONE:
            intent = IntentType.CONVERSATIONAL
        else:
            intent = self._detect_intent(normalized)

        context = self._detect_context(normalized)
        entities = self._detect_entities(normalized)

        ambiguous = any(
            entity in self.AMBIGUOUS_ENTITIES
            for entity in entities
        )

        scope = (
            ScopeType.AMBIGUOUS
            if ambiguous
            else ScopeType.CLEAR
        )

        requires_clarification = (
            scope == ScopeType.AMBIGUOUS
            and intent in (
                IntentType.INQUIRY,
                IntentType.ANALYSIS,
                IntentType.RESEARCH,
            )
        )

        if previous_result is not None:
            context = self._apply_previous_context(
                context=context,
                previous_result=previous_result,
            )

        explanation = self._build_explanation(
            intent=intent,
            entities=entities,
            conversation_event=conversation_event,
            time_period=time_period,
            addressed_to_baig=addressed_to_baig,
            requires_clarification=requires_clarification,
            previous_result=previous_result,
        )

        return SenseResult(
            message=cleaned,
            intent=intent,
            entities=tuple(entities),
            context=context,
            scope=scope,
            conversation_event=conversation_event,
            time_period=time_period,
            addressed_to_baig=addressed_to_baig,
            requires_clarification=requires_clarification,
            explanation=explanation,
        )

    def _detect_conversation_event(
        self,
        message: str,
    ) -> ConversationEvent:
        """Detect conversational events."""

        if any(
            re.search(pattern, message)
            for pattern in self.DEFERRED_CONTINUATION_PATTERNS
        ):
            return ConversationEvent.DEFERRED_CONTINUATION

        if any(
            re.search(pattern, message)
            for pattern in self.FAREWELL_PATTERNS
        ):
            return ConversationEvent.FAREWELL

        if any(
            re.search(pattern, message)
            for pattern in self.GREETING_PATTERNS
        ):
            return ConversationEvent.GREETING

        if any(
            re.search(pattern, message)
            for pattern in self.CONTINUATION_PATTERNS
        ):
            return ConversationEvent.CONTINUATION

        if any(
            re.search(pattern, message)
            for pattern in self.ACKNOWLEDGEMENT_PATTERNS
        ):
            return ConversationEvent.ACKNOWLEDGEMENT

        if any(
            re.search(pattern, message)
            for pattern in self.CONFIRMATION_PATTERNS
        ):
            return ConversationEvent.CONFIRMATION

        if any(
            re.search(pattern, message)
            for pattern in self.NEGATION_PATTERNS
        ):
            return ConversationEvent.NEGATION

        if any(
            re.search(pattern, message)
            for pattern in self.ATTENTION_PATTERNS
        ):
            return ConversationEvent.ATTENTION

        return ConversationEvent.NONE

    def _is_addressed_to_baig(self, message: str) -> bool:
        """Determine whether the owner directly addressed BAIG."""

        return any(
            re.search(pattern, message)
            for pattern in self.BAIG_ADDRESS_PATTERNS
        )

    def _detect_time_period(self, now: datetime) -> TimePeriod:
        """Convert local time into a conversational time period."""

        hour = now.hour

        if 5 <= hour < 12:
            return TimePeriod.MORNING

        if 12 <= hour < 17:
            return TimePeriod.AFTERNOON

        if 17 <= hour < 22:
            return TimePeriod.EVENING

        return TimePeriod.NIGHT

    def _detect_intent(self, message: str) -> IntentType:
        """Detect the broad non-conversational intent."""

        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(
                re.search(pattern, message)
                for pattern in patterns
            ):
                return intent

        return IntentType.UNKNOWN

    def _detect_context(self, message: str) -> str:
        """Detect basic time-related context."""

        if any(
            re.search(pattern, message)
            for pattern in self.CURRENT_CONTEXT_PATTERNS
        ):
            return "current/general"

        return "general"

    def _detect_entities(self, message: str) -> list[str]:
        """Detect currently supported high-level entities."""

        found = []

        for entity in self.AMBIGUOUS_ENTITIES:
            if re.search(
                rf"\b{re.escape(entity)}\b",
                message,
            ):
                found.append(entity)

        return found

    def _apply_previous_context(
        self,
        context: str,
        previous_result: SenseResult,
    ) -> str:
        """Carry forward useful context from the immediately previous turn."""

        if context != "general":
            return context

        if previous_result.entities:
            return "continuation"

        if previous_result.conversation_event in (
            ConversationEvent.GREETING,
            ConversationEvent.ATTENTION,
        ):
            return "conversation"

        return context

    def _build_explanation(
        self,
        intent: IntentType,
        entities: list[str],
        conversation_event: ConversationEvent,
        time_period: TimePeriod,
        addressed_to_baig: bool,
        requires_clarification: bool,
        previous_result: SenseResult | None,
    ) -> str:
        """Describe the current Sense interpretation."""

        if conversation_event == ConversationEvent.GREETING:
            return (
                f"Detected a greeting during the {time_period.value}. "
                f"Addressed to BAIG: {addressed_to_baig}."
            )

        if conversation_event == ConversationEvent.FAREWELL:
            return (
                "Detected a conversation-ending farewell. "
                f"Addressed to BAIG: {addressed_to_baig}."
            )

        if conversation_event == ConversationEvent.DEFERRED_CONTINUATION:
            return (
                "The owner appears to be ending the current conversation "
                "with an intention to continue later."
            )

        if conversation_event == ConversationEvent.CONTINUATION:
            return (
                "The owner appears to be asking BAIG to continue "
                "the current conversation or explanation."
            )

        if conversation_event == ConversationEvent.ACKNOWLEDGEMENT:
            return "Detected an acknowledgement from the owner."

        if conversation_event == ConversationEvent.CONFIRMATION:
            if previous_result is not None:
                return (
                    "Detected an affirmative response to the previous "
                    "conversation context."
                )

            return "Detected an affirmative response from the owner."

        if conversation_event == ConversationEvent.NEGATION:
            if previous_result is not None:
                return (
                    "Detected a negative response to the previous "
                    "conversation context."
                )

            return "Detected a negative response from the owner."

        if conversation_event == ConversationEvent.ATTENTION:
            return "The owner appears to be calling or addressing BAIG."

        if requires_clarification:
            return (
                "The message contains an entity whose economic scope "
                "may require clarification before deeper processing."
            )

        if entities:
            return (
                f"Detected intent '{intent.value}' and entity "
                f"{', '.join(entities)}."
            )

        return f"Detected intent '{intent.value}'."

SENSE = SenseEngine()
