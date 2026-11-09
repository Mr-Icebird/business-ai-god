import re

from app.sense.intent.conversation.models import (
    ConversationDetectionResult,
    ConversationIntent,
    CorrectionLink,
    IntentContext,
)
from app.sense.intent.models import ConfidenceLevel


_TOPIC_SWITCH = re.compile(
    r"\b(?:actually,?\s+)?(?:forget|leave|drop)\s+(?P<old>[^,.!?]+)[,.!?\s]+"
    r"(?:let's|let us|switch|move)\s+(?:look at|to|over to)?\s*(?P<new>[^,.!?]+)",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"\b(?:i meant|i mean|not\s+(?P<old>[^,.!?]+?)\s+but|rather)\s+"
    r"(?P<new>[^,.!?]+)|^\s*no,?\s+(?P<replacement>(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute)\b[^,.!?]*)",
    re.IGNORECASE,
)
_REJECTION = re.compile(r"^\s*(?:no|nope)\b.*\b(?:don't|do not|stop|cancel|reject)\b", re.IGNORECASE)
_REFINEMENT = re.compile(
    r"\b(?:make it|keep it|shorten it|expand it|narrow it|broaden it|focus it)\b",
    re.IGNORECASE,
)
_CLARIFICATION = re.compile(
    r"\b(?:clarify|what do you mean)\b|\b(?:could|can) you explain\s+(?:that|this|it)\b",
    re.IGNORECASE,
)
_FOLLOW_UP = re.compile(r"\b(?:what about|how about|and regarding|and\s+(?:the\s+)?\w+\s*\?|now\s+(?:compare|research|analy[sz]e|calculate|explain|plan|create|monitor))\b", re.IGNORECASE)
_CONTINUATION = re.compile(r"\b(?:continue|go on|carry on|pick up where|continue with)\b", re.IGNORECASE)
_CONFIRMATION = re.compile(r"^\s*(?:yes|yeah|yep|correct|confirmed)\b|\bthat's what i meant\b", re.IGNORECASE)
_CORRECTION_START = re.compile(r"^\s*(?:(?:no,?\s+)?(?:i meant|i mean|not\s+.+?\s+but)|no,?\s+(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute))\b", re.IGNORECASE)
_NEGATION = re.compile(r"^\s*(?:no|nope|not at all)\s*[.!?]*\s*$", re.IGNORECASE)
_NEW_REQUEST = re.compile(
    r"^\s*(?:please\s+)?(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute)\b"
    r"|^\s*(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute)\b"
    r"|^\s*i\s+(?:want|need|would like)\s+to\s+(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute)\b"
    r"|^\s*(?:tell|show|give)\s+(?:me|us)\b"
    r"|^\s*i\s+(?:want|would like|need)\s+to\s+know\b",
    re.IGNORECASE,
)
_QUESTION_OR_REQUEST = re.compile(
    r"^\s*(?:what|why|how|when|where|who|which)\b|\?",
    re.IGNORECASE,
)


class ConversationIntentDetector:
    def detect(
        self,
        text: str,
        context: IntentContext | None = None,
    ) -> ConversationDetectionResult:
        previous = context.previous_text if context else None
        available = bool(
            previous
            or context and (context.previous_result or context.previous_entity_mentions)
        )
        previous_interpretation = self._previous_interpretation(context)
        base = {
            "context_available": available,
            "previous_interpretation": previous_interpretation,
        }

        switch = _TOPIC_SWITCH.search(text)
        if switch:
            return ConversationDetectionResult(
                intent=ConversationIntent.TOPIC_SWITCH,
                confidence=ConfidenceLevel.HIGH, related_to_previous=available,
                topic_switch_from=switch.group("old").strip(),
                topic_switch_to=switch.group("new").strip(), **base,
            )

        correction = _CORRECTION.search(text)
        if correction or _CORRECTION_START.search(text):
            replacement = (
                (correction.group("new") or correction.groupdict().get("replacement") or "")
                .strip(" .!?,'\"")
                if correction else text.strip()
            )
            old = correction.groupdict().get("old") if correction else None
            old = old.strip() if old else self._previous_subject(context)
            link = CorrectionLink(
                relation="replaces_previous_interpretation" if available else "unlinked_correction",
                previous_interpretation=previous_interpretation or previous,
                current_correction=text,
                previous_value=old,
                replacement_value=replacement,
            )
            return ConversationDetectionResult(
                intent=ConversationIntent.CORRECTION, confidence=ConfidenceLevel.HIGH,
                related_to_previous=available, correction=link, **base,
            )

        if _REJECTION.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.REJECTION,
                                               confidence=ConfidenceLevel.HIGH, related_to_previous=available, **base)
        if _CONFIRMATION.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.CONFIRMATION,
                                               confidence=ConfidenceLevel.HIGH, related_to_previous=available, **base)
        if _NEGATION.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.NEGATION,
                                               confidence=ConfidenceLevel.MEDIUM, related_to_previous=available, **base)
        if _REFINEMENT.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.REFINEMENT,
                                               confidence=ConfidenceLevel.HIGH, related_to_previous=available, **base)
        if _CLARIFICATION.search(text):
            if available:
                return ConversationDetectionResult(intent=ConversationIntent.CLARIFICATION,
                                                   confidence=ConfidenceLevel.MEDIUM, related_to_previous=True, **base)
            return ConversationDetectionResult(intent=ConversationIntent.UNKNOWN,
                                               confidence=ConfidenceLevel.LOW, related_to_previous=False, **base)
        if _CONTINUATION.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.CONTINUATION,
                                               confidence=ConfidenceLevel.HIGH, related_to_previous=available, **base)
        if _FOLLOW_UP.search(text) or available and re.search(r"\b(?:that|it|those|them)\b", text, re.IGNORECASE) and "?" in text:
            return ConversationDetectionResult(intent=ConversationIntent.FOLLOW_UP,
                                               confidence=ConfidenceLevel.MEDIUM, related_to_previous=available, **base)
        if _NEW_REQUEST.search(text) or _QUESTION_OR_REQUEST.search(text):
            return ConversationDetectionResult(intent=ConversationIntent.NEW_REQUEST,
                                               confidence=ConfidenceLevel.MEDIUM, related_to_previous=False, **base)
        return ConversationDetectionResult(intent=ConversationIntent.UNKNOWN,
                                           confidence=ConfidenceLevel.UNKNOWN, **base)

    @staticmethod
    def _previous_interpretation(context: IntentContext | None) -> str | None:
        if context is None:
            return None
        if context.previous_result is not None:
            return context.previous_result.task.objective or context.previous_result.raw_text
        return context.previous_text

    @staticmethod
    def _previous_subject(context: IntentContext | None) -> str | None:
        if context is None or context.previous_result is None:
            return None
        subjects = context.previous_result.task.subject
        return subjects[-1] if subjects else None