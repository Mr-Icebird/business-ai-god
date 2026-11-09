import re

from app.sense.intent.conversation.models import ConversationIntent, IntentContext
from app.sense.intent.correction.models import (
    CorrectionChange,
    CorrectionDetectionResult,
    CorrectionType,
)
from app.sense.intent.models import ConfidenceLevel


_CORRECTION_MARKER = re.compile(
    r"\b(?:i meant|i mean|rather|instead|actually|only want|use .+ instead)\b|"
    r"^\s*no,?\s+(?=(?:i meant|i mean|research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute|use)\b)",
    re.IGNORECASE,
)
_REPLACEMENT = re.compile(r"\b(?:i meant|i mean|rather)\s+(?P<value>[^,.!?]+)", re.IGNORECASE)
_TARGET_ONLY = re.compile(r"\b(?:only want|just want)\s+(?:the\s+)?current price\b", re.IGNORECASE)


class IntentCorrectionDetector:
    def detect(self, text, current, context: IntentContext | None) -> CorrectionDetectionResult:
        if context is None or not context.previous_text:
            return CorrectionDetectionResult()
        previous = context.previous_result
        if previous is None:
            return self._unstructured_correction(text, context)

        marker = _CORRECTION_MARKER.search(text)
        refinement = bool(
            current.conversation
            and current.conversation.intent == ConversationIntent.REFINEMENT
        )
        if marker is None and not refinement:
            return CorrectionDetectionResult()

        changes: list[CorrectionChange] = []
        previous_ops = tuple(item.value for item in previous.task.operation)
        current_ops = tuple(item.value for item in current.task.operation)
        if not refinement and current_ops and current_ops != previous_ops:
            changes.append(self._change("task.operation", previous_ops, current_ops, text))

        old_subjects = tuple(previous.task.subject)
        new_subjects = tuple(current.task.subject)
        replacement = self._replacement_value(text, current)
        if replacement and not current_ops:
            new_subjects = self._parse_subjects(replacement)
        if not refinement and new_subjects and old_subjects and new_subjects != old_subjects:
            changes.append(self._change("task.subject", old_subjects, new_subjects, text))

        old_constraints = tuple(previous.constraints.constraints) if previous.constraints else ()
        new_constraints = tuple(current.constraints.constraints) if current.constraints else ()
        if new_constraints:
            old_by_type = {item.constraint_type: item.value for item in old_constraints}
            changed = tuple(
                item for item in new_constraints
                if old_by_type.get(item.constraint_type) != item.value
            )
            if changed:
                changes.append(self._change(
                    "constraints",
                    tuple(item.value for item in old_constraints),
                    tuple(item.value for item in changed),
                    text,
                ))

        if _TARGET_ONLY.search(text) and previous.task.operation:
            changes.append(self._change(
                "task.operation",
                previous_ops,
                (),
                text,
            ))
            changes.append(self._change("task.objective", previous.task.objective or "", text, text))

        if not changes:
            return CorrectionDetectionResult()

        fields = tuple(dict.fromkeys(item.field_name for item in changes))
        if "constraints" in fields:
            correction_type = CorrectionType.CONSTRAINT_MODIFICATION
        elif "task.operation" in fields and current_ops:
            correction_type = CorrectionType.INTENT_REPLACEMENT
        elif "task.operation" in fields and _TARGET_ONLY.search(text):
            correction_type = CorrectionType.REINTERPRETATION
        elif "task.subject" in fields:
            correction_type = CorrectionType.TASK_MODIFICATION
        else:
            correction_type = CorrectionType.OWNER_CORRECTION

        previous_interpretation = previous.task.objective or previous.raw_text
        return CorrectionDetectionResult(
            is_correction=True,
            correction_type=correction_type,
            affected_fields=fields,
            changes=tuple(changes),
            previous_interpretation=previous_interpretation,
            new_interpretation=text,
            preserved_fields=self._preserved_fields(fields),
            confidence=ConfidenceLevel.HIGH,
            source_text=text,
        )

    def _unstructured_correction(self, text, context: IntentContext) -> CorrectionDetectionResult:
        marker = _CORRECTION_MARKER.search(text)
        replacement = _REPLACEMENT.search(text)
        if marker is None or replacement is None:
            return CorrectionDetectionResult()
        return CorrectionDetectionResult(
            is_correction=True,
            correction_type=CorrectionType.OWNER_CORRECTION,
            affected_fields=("interpretation",),
            changes=(self._change("interpretation", context.previous_text or "", replacement.group("value").strip(), text),),
            previous_interpretation=context.previous_text,
            new_interpretation=text,
            confidence=ConfidenceLevel.MEDIUM,
            source_text=text,
        )

    @staticmethod
    def _replacement_value(text, current) -> str | None:
        if current.conversation and current.conversation.correction:
            value = current.conversation.correction.replacement_value
            if value:
                return value
        match = _REPLACEMENT.search(text)
        return match.group("value").strip() if match else None

    @staticmethod
    def _parse_subjects(value: str) -> tuple[str, ...]:
        value = re.sub(
            r"^\s*(?:research|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert|execute)\s+",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"\b(?:instead|not|rather)\b.*$", "", value, flags=re.IGNORECASE).strip(" .,!?")
        subjects = re.split(r"\s+(?:and|&)\s+|,\s*", value, flags=re.IGNORECASE)
        return tuple(item.strip() for item in subjects if item.strip())

    @staticmethod
    def _change(field_name: str, previous, updated, text: str) -> CorrectionChange:
        marker = _CORRECTION_MARKER.search(text)
        return CorrectionChange(
            field_name=field_name,
            previous_value=repr(previous),
            updated_value=repr(updated),
            source_text=text,
            source_span=marker.span() if marker else None,
        )

    @staticmethod
    def _preserved_fields(affected: tuple[str, ...]) -> tuple[str, ...]:
        all_fields = ("user_goal", "unmodified_constraints", "unmodified_subjects", "task_outputs")
        return tuple(item for item in all_fields if item not in affected)