import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.sense.domain.ambiguity.models import AmbiguityType as DomainAmbiguityType
from app.sense.domain.engine import DOMAIN_SENSE
from app.sense.domain.models import DomainContext, EvidenceProvenance
from app.sense.entity_engine import ENTITY_SENSE
from app.sense.input.engine import INPUT_SENSE
from app.sense.input.models import InputType
from app.sense.intent.action.models import ActionType
from app.sense.intent.ambiguity.models import AmbiguityType as IntentAmbiguityType
from app.sense.intent.conversation.models import IntentContext
from app.sense.intent.engine import INTENT_SENSE

from app.sense.models import (
    ConversationEvent,
    ClarificationDimension,
    ClarificationEvidence,
    ClarificationIssue,
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

    BAIG_ADDRESS_PATTERNS = (r"\bbaig\b",)

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
        *,
        input_type: InputType | str = InputType.TEXT,
        intent_context: IntentContext | None = None,
        domain_context: DomainContext | None = None,
    ) -> SenseResult:
        """
        Create the complete structured SENSE interpretation.

        previous_message and previous_result allow SENSE to eventually
        interpret short conversational responses using conversation context.
        """

        input_result = INPUT_SENSE.understand(message, input_type=input_type)
        if intent_context is None and (previous_message or previous_result):
            previous_entity_mentions = ()
            if previous_result is not None and previous_result.entity_sense is not None:
                previous_entity_mentions = tuple(
                    mention.text
                    for mention in previous_result.entity_sense.mentions
                    if mention.text
                )
            intent_context = IntentContext(
                previous_input=(
                    previous_result.input_sense if previous_result else None
                ),
                previous_result=(
                    previous_result.intent_sense if previous_result else None
                ),
                previous_user_message=(
                    previous_message
                    or (previous_result.message if previous_result else None)
                ),
                previous_entity_mentions=previous_entity_mentions,
            )

        intent_result = INTENT_SENSE.understand(
            input_result,
            context=intent_context,
        )

        if domain_context is None and (previous_message or previous_result):
            domain_context = DomainContext(
                previous_input=(
                    previous_result.input_sense if previous_result else None
                ),
                previous_sense2=(
                    previous_result.intent_sense if previous_result else None
                ),
                previous_result=(
                    previous_result.domain_sense if previous_result else None
                ),
                previous_text=(
                    previous_message
                    or (previous_result.message if previous_result else None)
                ),
                previous_entities=(previous_result.entities if previous_result else ()),
            )

        domain_result = DOMAIN_SENSE.understand(
            input_result,
            sense2_result=intent_result,
            context=domain_context,
        )

        cleaned = message.strip()

        if not cleaned:
            return SenseResult(
                message=message,
                intent=IntentType.UNKNOWN,
                explanation=(
                    "The message is empty; no clarification question can be "
                    "grounded in its contents."
                ),
                input_sense=input_result,
                intent_sense=intent_result,
                domain_sense=domain_result,
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

            if previous_entity is None and previous_result.entity_sense is not None:
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

        clarification_issues = self._clarification_issues(
            intent_result,
            domain_result,
            previous_result,
        )
        clarification_dimensions = tuple(
            dict.fromkeys(item.dimension for item in clarification_issues)
        )
        requires_clarification = bool(clarification_issues)
        scope = (
            ScopeType.AMBIGUOUS
            if ClarificationDimension.SCOPE in clarification_dimensions
            else ScopeType.CLEAR
        )
        clarification_questions = tuple(
            item.question for item in clarification_issues if item.question
        )
        clarification_question = self._combined_clarification_question(
            clarification_questions
        )
        if not any(character.isalnum() for character in cleaned):
            explanation = (
                "The message contains no meaningful text; no clarification "
                "question can be grounded in it."
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
        if requires_clarification:
            explanation = self._clarification_explanation(clarification_issues)

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
            clarification_dimensions=clarification_dimensions,
            clarification_issues=clarification_issues,
            clarification_questions=clarification_questions,
            clarification_question=clarification_question,
            explanation=explanation,
            entity_sense=entity_sense,
            input_sense=input_result,
            intent_sense=intent_result,
            domain_sense=domain_result,
        )

    @classmethod
    def _clarification_issues(cls, intent_result, domain_result, previous_result):
        issues = []
        intent_ambiguity = intent_result.ambiguity
        for item in intent_ambiguity.issues if intent_ambiguity else ():
            if not item.requires_clarification:
                continue
            if item.ambiguity_type == IntentAmbiguityType.MISSING_INTENT and not any(
                character.isalnum() for character in intent_result.normalized_text
            ):
                continue
            if cls._intent_issue_resolved_by_correction(
                item, intent_result, domain_result, previous_result
            ):
                continue
            source_text = intent_result.normalized_text
            evidence = ()
            if item.source_span is not None and 0 <= item.source_span[
                0
            ] < item.source_span[1] <= len(source_text):
                evidence = (
                    ClarificationEvidence(
                        source_text[slice(*item.source_span)],
                        "sense2",
                        item.source_span,
                        source_text,
                    ),
                )
            dimension = (
                ClarificationDimension.INTENT
                if item.affected == "intent"
                else ClarificationDimension.TASK
            )
            candidates = tuple(item.candidates)
            issues.append(
                ClarificationIssue(
                    dimension=dimension,
                    reason=item.reason,
                    evidence=evidence,
                    candidates=candidates,
                    question=cls._question_for(
                        dimension,
                        item.reason,
                        candidates,
                        cls._clarification_topic(intent_result, domain_result),
                    ),
                )
            )

        ambiguity = domain_result.ambiguity
        if ambiguity is not None and ambiguity.clarification_required:
            domain_type = ambiguity.domain_ambiguity_type
            scope_type = ambiguity.scope_ambiguity_type
            if domain_type != DomainAmbiguityType.NONE:
                candidates = tuple(item.value for item in ambiguity.possible_domains)
                evidence = cls._domain_clarification_evidence(
                    domain_result, ambiguity.possible_domains
                )
                issues.append(
                    ClarificationIssue(
                        ClarificationDimension.DOMAIN,
                        cls._dimension_reason(
                            ambiguity.clarification_reason,
                            "domain",
                        ),
                        evidence,
                        candidates,
                        cls._question_for(
                            ClarificationDimension.DOMAIN,
                            "",
                            candidates,
                        ),
                    )
                )
            if scope_type != DomainAmbiguityType.NONE:
                candidates = tuple(item.value for item in ambiguity.possible_scopes)
                evidence = cls._scope_clarification_evidence(
                    domain_result, ambiguity.possible_scopes
                )
                issues.append(
                    ClarificationIssue(
                        ClarificationDimension.SCOPE,
                        cls._dimension_reason(
                            ambiguity.clarification_reason,
                            "scope",
                        ),
                        evidence,
                        candidates,
                        cls._question_for(
                            ClarificationDimension.SCOPE,
                            "",
                            candidates,
                        ),
                    )
                )
            if (
                domain_type == DomainAmbiguityType.NONE
                and scope_type == DomainAmbiguityType.NONE
            ):
                issues.append(
                    ClarificationIssue(
                        ClarificationDimension.TASK,
                        ambiguity.clarification_reason
                        or "The task refers to context that is not available.",
                        tuple(
                            ClarificationEvidence(item, "sense3")
                            for item in ambiguity.evidence
                        ),
                        (),
                        cls._question_for(
                            ClarificationDimension.TASK,
                            ambiguity.clarification_reason or "",
                            (),
                        ),
                    )
                )
        return tuple(issues)

    @staticmethod
    def _intent_issue_resolved_by_correction(
        issue, intent_result, domain_result, previous_result
    ):
        intent_correction = intent_result.correction
        if intent_correction and intent_correction.is_correction:
            affected = set(intent_correction.affected_fields)
            if issue.affected in affected or any(
                issue.affected.startswith(f"{field}.") for field in affected
            ):
                return True

        if (
            issue.ambiguity_type != IntentAmbiguityType.MISSING_INTENT
            or issue.affected != "intent"
            or previous_result is None
            or previous_result.intent_sense is None
            or domain_result.correction is None
            or not domain_result.correction.detected
        ):
            return False
        previous_task = previous_result.intent_sense.task
        previous_actions = previous_result.intent_sense.action.actions
        if previous_task.operation != (ActionType.ANALYZE,) or previous_actions != (
            ActionType.ANALYZE,
        ):
            return False
        correction_updates_subject_or_scope = any(
            update.field_name in {"domains", "scopes", "scope_subjects"}
            and bool(update.updated_value)
            for update in domain_result.correction.updates
        )
        if not correction_updates_subject_or_scope:
            return False

        updated_subjects = {
            subject.strip().casefold()
            for subject in domain_result.correction.updated_scope_subjects
            if subject.strip()
        }
        previous_subjects = {
            subject.strip().casefold()
            for subject in previous_task.subject
            if subject.strip()
        }
        return bool(updated_subjects & previous_subjects)

    @staticmethod
    def _domain_clarification_evidence(result, candidates):
        candidate_set = set(candidates)
        return tuple(
            dict.fromkeys(
                ClarificationEvidence(
                    signal.evidence,
                    "sense3",
                    signal.source_span,
                    signal.source_text,
                )
                for signal in result.detection.signals
                if signal.domain in candidate_set
                and signal.provenance == EvidenceProvenance.SOURCE_TEXT
            )
        )

    @staticmethod
    def _scope_clarification_evidence(result, candidates):
        candidate_set = set(candidates)
        detection = result.scope_detection
        if detection is None:
            return ()
        return tuple(
            dict.fromkeys(
                ClarificationEvidence(
                    item.evidence,
                    "sense3",
                    item.source_span,
                    item.source_text,
                )
                for item in detection.evidence
                if item.scope_type in candidate_set
                and item.provenance == EvidenceProvenance.SOURCE_TEXT
            )
        )

    @staticmethod
    def _dimension_reason(reason, dimension):
        if not reason:
            return f"The {dimension} interpretation remains unresolved."
        marker = (
            "Domain evidence supports multiple plausible interpretations."
            if dimension == "domain"
            else "Scope evidence does not resolve the highlighted subject."
        )
        if marker in reason:
            return marker
        return reason

    @staticmethod
    def _clarification_topic(intent_result, domain_result):
        signal = next(
            (
                item
                for item in domain_result.detection.signals
                if item.provenance == EvidenceProvenance.SOURCE_TEXT
            ),
            None,
        )
        if signal is not None:
            return signal.evidence
        if intent_result.task.subject:
            return ", ".join(intent_result.task.subject)
        return None

    @staticmethod
    def _question_for(dimension, reason, candidates, topic=None):
        labels = tuple(item.replace("_", " ") for item in candidates)
        choices = ", ".join(labels)
        if dimension == ClarificationDimension.INTENT:
            if not choices and topic:
                return f"What would you like me to do with {topic}?"
            prompt = "Which intent should I apply"
        elif dimension == ClarificationDimension.TASK:
            if "refer" in reason.casefold() or "context" in reason.casefold():
                prompt = "What does this refer to"
            elif (
                "subject" in reason.casefold()
                or "comparison target" in reason.casefold()
            ):
                prompt = "Which subject or target should I use"
            else:
                prompt = "What specific task should I perform"
        elif dimension == ClarificationDimension.DOMAIN:
            prompt = "Which domain do you mean"
        else:
            prompt = "Which scope do you mean"
        return f"{prompt}: {choices}?" if choices else f"{prompt}?"

    @staticmethod
    def _combined_clarification_question(questions):
        if not questions:
            return None
        if len(questions) == 1:
            return questions[0]
        numbered = "; ".join(
            f"{index}. {question}" for index, question in enumerate(questions, 1)
        )
        return f"Please clarify each point: {numbered}"

    @staticmethod
    def _clarification_explanation(issues):
        details = "; ".join(f"{item.dimension.value}: {item.reason}" for item in issues)
        return f"Clarification is needed for {details}"

    def _detect_conversation_event(
        self,
        normalized: str,
    ) -> ConversationEvent:

        if any(
            re.search(pattern, normalized)
            for pattern in self.DEFERRED_CONTINUATION_PATTERNS
        ):
            return ConversationEvent.DEFERRED_CONTINUATION

        if any(re.search(pattern, normalized) for pattern in self.FAREWELL_PATTERNS):
            return ConversationEvent.FAREWELL

        if any(re.search(pattern, normalized) for pattern in self.GREETING_PATTERNS):
            return ConversationEvent.GREETING

        if any(
            re.search(pattern, normalized) for pattern in self.CONTINUATION_PATTERNS
        ):
            return ConversationEvent.CONTINUATION

        if any(
            re.search(pattern, normalized) for pattern in self.ACKNOWLEDGEMENT_PATTERNS
        ):
            return ConversationEvent.ACKNOWLEDGEMENT

        if any(
            re.search(pattern, normalized) for pattern in self.CONFIRMATION_PATTERNS
        ):
            return ConversationEvent.CONFIRMATION

        if any(re.search(pattern, normalized) for pattern in self.NEGATION_PATTERNS):
            return ConversationEvent.NEGATION

        if any(re.search(pattern, normalized) for pattern in self.ATTENTION_PATTERNS):
            return ConversationEvent.ATTENTION

        return ConversationEvent.NONE

    def _is_addressed_to_baig(self, normalized: str) -> bool:
        return any(
            re.search(pattern, normalized) for pattern in self.BAIG_ADDRESS_PATTERNS
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
            if any(re.search(pattern, normalized) for pattern in patterns):
                return intent

        return IntentType.UNKNOWN

    def _detect_context(self, normalized: str) -> str:
        if any(
            re.search(pattern, normalized) for pattern in self.CURRENT_CONTEXT_PATTERNS
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
                f"The message contains the entity or topic: " f"{', '.join(entities)}."
            )

        if addressed_to_baig:
            return "The owner is addressing BAIG."

        if previous_result is not None:
            return "The message may depend on the previous conversational context."

        if intent == IntentType.UNKNOWN:
            return "SENSE could not determine a specific intent."

        return f"SENSE classified the message as {intent.value}."


SENSE = SenseEngine()
