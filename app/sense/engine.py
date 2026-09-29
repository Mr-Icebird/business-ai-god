import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.sense.entity_engine import ENTITY_SENSE

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

        # Resolve the previous active entity for conversational references.
        previous_entity = None

        if previous_result is not None:
            if (
                previous_result.entity_sense is not None
                and previous_result.entity_sense.references
            ):
                resolved_entities = [
                    reference.refers_to
                    for reference in previous_result.entity_sense.references
                    if reference.refers_to
                ]

                if resolved_entities:
                    previous_entity = resolved_entities[-1]

            if (
                previous_entity is None
                and previous_result.entity_sense is not None
            ):
                mentioned_entities = [
                    mention.text
                    for mention in previous_result.entity_sense.mentions
                    if mention.text
                ]

                if mentioned_entities:
                    previous_entity = mentioned_entities[-1]

        entity_sense = ENTITY_SENSE.understand(
            cleaned,
            previous_entity=previous_entity,
        )

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
            entity_sense=entity_sense,
        )

    def _detect_conversation_event(
        self,
        normalized: str,
    ) -> ConversationEvent:

        if any(
            re.search(pattern, normalized)
            for pattern in self.DEFERRED_CONTINUATION_PATTERNS
        ):
            return ConversationEvent.DEFERRED_CONTINUATION

        if any(
            re.search(pattern, normalized)
            for pattern in self.FAREWELL_PATTERNS
        ):
            return ConversationEvent.FAREWELL

        if any(
            re.search(pattern, normalized)
            for pattern in self.GREETING_PATTERNS
        ):
            return ConversationEvent.GREETING

        if any(
            re.search(pattern, normalized)
            for pattern in self.CONTINUATION_PATTERNS
        ):
            return ConversationEvent.CONTINUATION

        if any(
            re.search(pattern, normalized)
            for pattern in self.ACKNOWLEDGEMENT_PATTERNS
        ):
            return ConversationEvent.ACKNOWLEDGEMENT

        if any(
            re.search(pattern, normalized)
            for pattern in self.CONFIRMATION_PATTERNS
        ):
            return ConversationEvent.CONFIRMATION

        if any(
            re.search(pattern, normalized)
            for pattern in self.NEGATION_PATTERNS
        ):
            return ConversationEvent.NEGATION

        if any(
            re.search(pattern, normalized)
            for pattern in self.ATTENTION_PATTERNS
        ):
            return ConversationEvent.ATTENTION

        return ConversationEvent.NONE

    def _is_addressed_to_baig(self, normalized: str) -> bool:
        return any(
            re.search(pattern, normalized)
            for pattern in self.BAIG_ADDRESS_PATTERNS
        )

    def _detect_time_period(self, current_time: datetime) -> TimePeriod:
        hour = current_time.hour

        if 5 <= hour < 12:
            return TimePeriod.MORNING

        if 12 <= hour < 17:
            return TimePeriod.AFTERNOON

        if 17 <= hour < 21:
            return TimePeriod.EVENING

        return TimePeriod.NIGHT

    def _detect_intent(self, normalized: str) -> IntentType:
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(
                re.search(pattern, normalized)
                for pattern in patterns
            ):
                return intent

        return IntentType.UNKNOWN

    def _detect_context(self, normalized: str) -> str:
        if any(
            re.search(pattern, normalized)
            for pattern in self.CURRENT_CONTEXT_PATTERNS
        ):
            return "current"

        return "unknown"

    def _detect_entities(self, normalized: str) -> list[str]:
        entities = []

        for entity in self.AMBIGUOUS_ENTITIES:
            if re.search(
                rf"\b{re.escape(entity)}\b",
                normalized,
            ):
                entities.append(entity)

        return entities

    def _apply_previous_context(
        self,
        context: str,
        previous_result: SenseResult,
    ) -> str:
        if context != "unknown":
            return context

        if previous_result.context != "unknown":
            return previous_result.context

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

        if conversation_event == ConversationEvent.GREETING:
            return "The owner is greeting BAIG."

        if conversation_event == ConversationEvent.FAREWELL:
            return "The owner is ending the conversation."

        if conversation_event == ConversationEvent.DEFERRED_CONTINUATION:
            return "The owner wants to continue the conversation later."

        if conversation_event == ConversationEvent.CONTINUATION:
            return "The owner wants BAIG to continue."

        if conversation_event == ConversationEvent.ACKNOWLEDGEMENT:
            return "The owner acknowledges the previous response."

        if conversation_event == ConversationEvent.CONFIRMATION:
            return "The owner is confirming the previous context or question."

        if conversation_event == ConversationEvent.NEGATION:
            return "The owner is rejecting or correcting the previous context."

        if conversation_event == ConversationEvent.ATTENTION:
            return "The owner is directly getting BAIG's attention."

        if requires_clarification:
            return "The message contains an entity whose intended scope is ambiguous."

        if entities:
            return (
                f"The message contains the entity or topic: "
                f"{', '.join(entities)}."
            )

        if addressed_to_baig:
            return "The owner is addressing BAIG."

        if previous_result is not None:
            return "The message may depend on the previous conversational context."

        if intent == IntentType.UNKNOWN:
            return "SENSE could not determine a specific intent."

        return f"SENSE classified the message as {intent.value}."


SENSE = SenseEngine()
