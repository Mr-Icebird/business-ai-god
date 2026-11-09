import re

from app.sense.intent.ambiguity.models import (
    AmbiguityIssue,
    AmbiguityResult,
    AmbiguityType,
)
from app.sense.intent.conversation.models import ConversationIntent, IntentContext
from app.sense.intent.detection.models import IntentType
from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.task.models import TaskDetectionResult


_CONFLICT_CUES = (
    (IntentType.RESEARCH, r"\bresearch\b", r"\b(?:do not|don't|never)\s+research\b"),
    (IntentType.ANALYSIS, r"\b(?:analyze|analyse|analysis)\b", r"\b(?:do not|don't|never)\s+(?:analyze|analyse)\b"),
    (IntentType.COMPARISON, r"\bcompare\b", r"\b(?:do not|don't|never)\s+compare\b"),
    (IntentType.CALCULATION, r"\b(?:calculate|compute)\b", r"\b(?:do not|don't|never)\s+(?:calculate|compute)\b"),
)
_DEICTIC = re.compile(r"\b(?:what happened|what about|compare (?:these|those|it|them)|explain that|analy[sz]e this|research (?:it|that|them|those)|analy[sz]e (?:it|that|them|those)|make it (?:shorter|briefer|narrower|broader)|keep it (?:short|brief))\b", re.IGNORECASE)
_GENERIC_REFERENCES = {"these", "those", "them", "it", "this", "that", "these assets", "those items"}


class AmbiguityDetector:
    def detect(
        self,
        text: str,
        intent,
        task: TaskDetectionResult,
        conversation,
        context: IntentContext | None = None,
    ) -> AmbiguityResult:
        issues: list[AmbiguityIssue] = []
        context_available = bool(
            context and (
                context.previous_text
                or context.previous_result
                or context.previous_entity_mentions
            )
        )

        conflict = self._conflict(text)
        if conflict is not None:
            kind, span = conflict
            issues.append(AmbiguityIssue(
                AmbiguityType.CONFLICTING_INTENT,
                "intent",
                f"The request both asks for and rejects {kind.value}.",
                (kind.value, f"not_{kind.value}"),
                span,
                ConfidenceLevel.HIGH,
            ))

        follow_up_without_context = (
            conversation.intent == ConversationIntent.FOLLOW_UP and not context_available
        )
        if follow_up_without_context:
            issues.append(AmbiguityIssue(
                AmbiguityType.AMBIGUOUS_INTENT,
                "intent",
                "A follow-up topic is present, but its intended operation is not established.",
                tuple(item.value for item in (
                    IntentType.INFORMATION, IntentType.ANALYSIS,
                    IntentType.RESEARCH,
                )),
                self._span(text, r"\b(?:what|how)\s+about\b"),
                ConfidenceLevel.LOW,
            ))

        if intent.primary_intent == IntentType.UNKNOWN and not conflict:
            issues.append(AmbiguityIssue(
                AmbiguityType.MISSING_INTENT,
                "intent",
                "No reliable intent was detected from the message.",
                source_span=(0, len(text)) if text else None,
                confidence=ConfidenceLevel.UNKNOWN,
            ))

        deictic = _DEICTIC.search(text)
        locally_resolved = bool(
            len(task.operation) > 1
            and task.subject
            and not any(subject.casefold() in _GENERIC_REFERENCES for subject in task.subject)
        )
        if (
            deictic
            and deictic.group().casefold() == "what happened"
            and task.subject
            and not any(subject.casefold() in _GENERIC_REFERENCES for subject in task.subject)
        ):
            locally_resolved = True
        if deictic and not context_available and not locally_resolved:
            missing_subject = bool(re.search(
                r"\b(?:research|analy[sz]e|compare)\s+(?:it|that|them|those|these)\b",
                text,
                re.IGNORECASE,
            ))
            issues.append(AmbiguityIssue(
                AmbiguityType.MISSING_TASK_INFORMATION if missing_subject else AmbiguityType.INSUFFICIENT_CONTEXT,
                "task",
                "The message refers to an event or subject that is not available in context.",
                source_span=deictic.span(),
                confidence=ConfidenceLevel.HIGH,
            ))

        generic_subject = any(subject.casefold() in _GENERIC_REFERENCES for subject in task.subject)
        comparison_requested = any(item.value == "compare" for item in task.operation)
        if comparison_requested and (not task.subject or generic_subject) and not context_available:
            issues.append(AmbiguityIssue(
                AmbiguityType.MISSING_TASK_INFORMATION,
                "task.subject",
                "The comparison target is missing or only referred to deictically.",
                source_span=self._span(text, r"\b(?:compare|versus|vs\.?)\b"),
                confidence=ConfidenceLevel.HIGH,
            ))

        alternative = re.search(r"\bor\b", text, re.IGNORECASE)
        if alternative and len(task.operation) > 1:
            issues.append(AmbiguityIssue(
                AmbiguityType.AMBIGUOUS_TASK,
                "task.operation",
                "The message presents alternative operations without selecting one.",
                tuple(item.value for item in task.operation),
                alternative.span(),
                ConfidenceLevel.MEDIUM,
            ))

        if not issues:
            issues.append(AmbiguityIssue(
                AmbiguityType.CLEAR_INTENT,
                "intent",
                "The detected intent has sufficient explicit evidence.",
                confidence=ConfidenceLevel.HIGH,
                requires_clarification=False,
            ))

        priority = (
            AmbiguityType.CONFLICTING_INTENT,
            AmbiguityType.MISSING_TASK_INFORMATION,
            AmbiguityType.AMBIGUOUS_INTENT,
            AmbiguityType.AMBIGUOUS_TASK,
            AmbiguityType.INSUFFICIENT_CONTEXT,
            AmbiguityType.MISSING_INTENT,
        )
        primary = next(
            (kind for kind in priority if any(item.ambiguity_type == kind for item in issues)),
            AmbiguityType.CLEAR_INTENT,
        )
        ambiguous = primary != AmbiguityType.CLEAR_INTENT
        return AmbiguityResult(
            primary_type=primary,
            issues=tuple(issues),
            is_ambiguous=ambiguous,
            requires_clarification=any(item.requires_clarification for item in issues),
        )

    @staticmethod
    def _conflict(text: str):
        for intent, positive, negative in _CONFLICT_CUES:
            positive_match = re.search(positive, text, re.IGNORECASE)
            negative_match = re.search(negative, text, re.IGNORECASE)
            is_separate_positive = bool(
                positive_match and negative_match
                and not (
                    negative_match.start() <= positive_match.start()
                    and positive_match.end() <= negative_match.end()
                )
            )
            if is_separate_positive:
                positive_clause = text[positive_match.end():negative_match.start()]
                negative_clause = text[negative_match.end():]
                positive_subject = AmbiguityDetector._operation_subject(positive_clause)
                negative_subject = AmbiguityDetector._operation_subject(negative_clause)
                if (
                    positive_subject and negative_subject
                    and positive_subject != negative_subject
                    and negative_subject not in {"it", "them", "that", "those"}
                ):
                    continue
                return intent, (min(positive_match.start(), negative_match.start()),
                                max(positive_match.end(), negative_match.end()))
        return None

    @staticmethod
    def _operation_subject(clause: str) -> str:
        clause = re.split(r"\b(?:but|and|or|then)\b|[.!?;,]", clause, maxsplit=1, flags=re.IGNORECASE)[0]
        clause = re.sub(r"^\s+(?:why|what|how|whether|if)\b", " ", clause, flags=re.IGNORECASE)
        words = re.findall(r"[A-Za-z][A-Za-z'-]*|[A-Z0-9]{2,}", clause)
        stop = {"a", "an", "and", "the", "it", "them", "that", "those", "me", "you", "please"}
        return " ".join(word.casefold() for word in words if word.casefold() not in stop)

    @staticmethod
    def _span(text: str, pattern: str) -> tuple[int, int] | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.span() if match else None