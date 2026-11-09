import ast
import re
from dataclasses import replace

from app.sense.intent.conversation.models import (
    ConversationDetectionResult,
    ConversationIntent,
    CorrectionLink,
    IntentContext,
)
from app.sense.intent.correction.models import CorrectionDetectionResult
from app.sense.intent.detection.knowledge import INTENT_HIERARCHY
from app.sense.intent.detection.models import IntentDetectionResult, IntentType
from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.subintent.models import SubIntentDetectionResult, SubIntentType


class IntentCorrectionUpdater:
    """Apply evidenced corrections while retaining unaffected prior context."""

    def update(self, current, context: IntentContext | None,
               correction: CorrectionDetectionResult):
        if not correction.is_correction or context is None or context.previous_result is None:
            return current

        previous = context.previous_result
        affected = set(correction.affected_fields)
        task = current.task
        if "task.operation" in affected and current.task.operation:
            task = replace(
                current.task,
                constraints=self._merge_constraint_texts(
                    previous.task.constraints, current.task.constraints, current.raw_text
                ),
            )
        elif "task.operation" in affected and "task.objective" in affected:
            task = replace(
                previous.task,
                objective=current.raw_text,
                operation=(),
                task_type=(SubIntentType.INFORMATION,),
                outputs=("current price",),
                completion_condition="Provide the current price.",
            )

        if "constraints" in affected:
            current_constraints = self._merge_constraints(previous, current)
            task = replace(
                previous.task,
                constraints=self._replace_time_text(previous.task.constraints, current.raw_text),
            )
            current = replace(current, constraints=current_constraints)

        if "task.subject" in affected:
            new_subjects = self._change_subjects(correction)
            old_subjects = previous.task.subject
            subject_base = (
                task if "task.operation" in affected and current.task.operation
                else previous.task
            )
            operation_text = " ".join(item.value for item in subject_base.operation)
            objective = (
                subject_base.objective
                if "task.operation" in affected and current.task.operation
                else previous.task.objective or previous.raw_text
            )
            if "task.operation" in affected and current.task.operation:
                objective = current.task.objective or objective
            elif len(old_subjects) > 1 and len(new_subjects) > 1:
                objective = f"{operation_text} {' and '.join(new_subjects)}".strip()
            else:
                for old in old_subjects:
                    objective = re.sub(
                        re.escape(old), " and ".join(new_subjects), objective,
                        count=1, flags=re.IGNORECASE,
                    )
                if not objective:
                    objective = f"{operation_text} {' and '.join(new_subjects)}".strip()
            task = replace(
                subject_base,
                objective=objective,
                subject=new_subjects,
                inputs=tuple(item for item in subject_base.inputs if item not in old_subjects) + new_subjects,
            )

        current = replace(current, task=task)
        if "task.operation" in affected and not current.task.operation and "task.objective" in affected:
            from app.sense.intent.question.models import QuestionDetectionResult, QuestionType

            current = replace(
                current,
                intent=IntentDetectionResult(
                    primary_intent=IntentType.INFORMATION,
                    hierarchy=(INTENT_HIERARCHY[IntentType.INFORMATION],),
                    confidence=ConfidenceLevel.MEDIUM,
                ),
                subintent=SubIntentDetectionResult(
                    primary=SubIntentType.INFORMATION,
                    detected=(SubIntentType.INFORMATION,),
                    confidence=ConfidenceLevel.MEDIUM,
                ),
                action=type(current.action)(),
                question=QuestionDetectionResult(question_type=QuestionType.UNKNOWN),
            )
        elif "task.operation" not in affected or not current.task.operation:
            current = replace(
                current,
                intent=previous.intent,
                subintent=previous.subintent,
                action=previous.action,
                goal=current.goal if current.goal.primary.value != "unknown" else previous.goal,
            )

        if "constraints" not in affected:
            current = replace(current, constraints=self._merge_constraints(previous, current))
        if current.goal.primary.value == "unknown" and previous.goal.primary.value != "unknown":
            current = replace(current, goal=previous.goal)

        return replace(
            current,
            conversation=self._correction_conversation(current, context, correction),
        )

    @staticmethod
    def _change_subjects(correction: CorrectionDetectionResult) -> tuple[str, ...]:
        for change in correction.changes:
            if change.field_name == "task.subject":
                try:
                    parsed = ast.literal_eval(change.updated_value)
                except (ValueError, SyntaxError):
                    return ()
                if isinstance(parsed, tuple):
                    return tuple(str(item) for item in parsed)
                if isinstance(parsed, str):
                    return (parsed,)
        return ()

    @staticmethod
    def _merge_constraint_texts(previous, current, message):
        years = re.findall(r"\b(?:19|20)\d{2}\b", message)
        retained = tuple(
            item for item in previous
            if not years or not re.search(r"\b(?:19|20)\d{2}\b", item)
        )
        return tuple(dict.fromkeys(current + retained))

    @staticmethod
    def _replace_time_text(previous, message):
        years = re.findall(r"\b(?:19|20)\d{2}\b", message)
        if not years:
            return previous
        retained = tuple(item for item in previous if not re.search(r"\b(?:19|20)\d{2}\b", item))
        return retained + (f"in {years[-1]}",)

    @staticmethod
    def _merge_constraints(previous, current):
        if previous.constraints is None:
            return current.constraints
        if current.constraints is None:
            return previous.constraints
        retained = tuple(
            item for item in previous.constraints.constraints
            if not any(
                IntentCorrectionUpdater._same_constraint_slot(item, replacement)
                for replacement in current.constraints.constraints
            )
        )
        return replace(
            current.constraints,
            constraints=retained + current.constraints.constraints,
        )

    @staticmethod
    def _same_constraint_slot(previous, replacement) -> bool:
        if previous.constraint_type != replacement.constraint_type:
            return False
        old = previous.value.casefold()
        new = replacement.value.casefold()
        if previous.constraint_type.value == "time":
            old_year = re.search(r"\b(?:19|20)\d{2}\b", old)
            new_year = re.search(r"\b(?:19|20)\d{2}\b", new)
            return bool(old_year and new_year) or old == new
        if previous.constraint_type.value == "financial":
            slot_pattern = r"\b(budget|risk|market cap|capital)\b"
            old_slot = re.search(slot_pattern, old)
            new_slot = re.search(slot_pattern, new)
            if old_slot and new_slot:
                return old_slot.group(1) == new_slot.group(1)
        if previous.constraint_type.value == "scope":
            words = lambda value: set(re.findall(r"[a-z0-9]+", value)) - {
                "only", "include", "exclude", "dont", "do", "not", "compare",
            }
            return bool(words(old) & words(new))
        if previous.constraint_type.value == "data":
            old_mode = "live" if "live data" in old else "historical" if "historical data" in old else None
            new_mode = "live" if "live data" in new else "historical" if "historical data" in new else None
            return bool(old_mode and new_mode)
        return old == new

    @staticmethod
    def _correction_conversation(current, context, correction):
        previous = context.previous_result
        old = previous.task.subject[-1] if previous and previous.task.subject else None
        new = current.task.subject[-1] if current.task.subject else None
        return ConversationDetectionResult(
            intent=ConversationIntent.CORRECTION,
            confidence=correction.confidence,
            context_available=True,
            related_to_previous=True,
            previous_interpretation=correction.previous_interpretation,
            correction=CorrectionLink(
                relation="replaces_previous_interpretation",
                previous_interpretation=correction.previous_interpretation,
                current_correction=correction.source_text or current.raw_text,
                previous_value=old,
                replacement_value=new,
            ),
        )