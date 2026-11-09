import re

from app.sense.intent.action.models import ActionType
from app.sense.intent.decomposition.models import (
    DecompositionResult,
    SubTask,
    TaskDependency,
    TaskPlan,
)
from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.task.models import TaskDetectionResult


_OPERATION_CUES = (
    (ActionType.EXPLAIN, r"\b(?:explain|describe)\b"),
    (ActionType.CALCULATE, r"\b(?:calculate|compute|work out)\b"),
    (ActionType.RESEARCH, r"\b(?:research|investigate|look up)\b"),
    (ActionType.COMPARE, r"\b(?:compare|contrast)\b"),
    (ActionType.ANALYZE, r"\b(?:analy[sz]e|assess|evaluate)\b"),
    (ActionType.PLAN, r"\bplan\b"),
    (ActionType.CREATE, r"\b(?:create|make|build|write|draft|generate)\b"),
    (ActionType.MODIFY, r"\b(?:modify|change|update|edit|revise)\b"),
    (ActionType.MONITOR, r"\b(?:monitor|track|watch)\b"),
    (ActionType.ALERT, r"\b(?:alert|notify)\b"),
    (ActionType.EXECUTE, r"\b(?:execute|place|submit)\b"),
)
_STOP = {"a", "an", "and", "the", "to", "for", "me", "it", "them", "this", "these", "those", "with", "on", "in", "of", "that", "whether", "why", "how", "what", "when", "then", "please", "my", "this"}


class TaskDecomposer:
    def decompose(self, text: str, task: TaskDetectionResult | None = None) -> DecompositionResult:
        matches = []
        for priority, (operation, pattern) in enumerate(_OPERATION_CUES):
            for match in re.finditer(pattern, text, re.IGNORECASE):
                prefix = text[max(0, match.start() - 16):match.start()]
                if re.search(r"\b(?:do not|don't|never)\s+$", prefix, re.IGNORECASE):
                    continue
                if task is not None and operation not in task.operation:
                    continue
                if operation == ActionType.PLAN:
                    preceding = text[max(0, match.start() - 40):match.start()]
                    clause_prefix = re.split(r"\b(?:and|then)\b|[,;.]", preceding, flags=re.IGNORECASE)[-1]
                    if clause_prefix.strip():
                        continue
                matches.append((match.start(), match.end(), priority, operation))
        matches.sort(key=lambda item: (item[0], item[2]))
        if not matches:
            if task is not None and task.operation:
                generated = tuple(SubTask(
                    task_id=f"task-{index + 1}",
                    description=task.objective or text,
                    objective=task.objective or text,
                    operation=operation,
                    subject=task.subject,
                    inputs=task.inputs,
                    outputs=(self._output(operation),),
                    ordering=index + 1,
                    parallelizable=len(task.operation) > 1,
                    completion_condition=f"Provide {self._output(operation)}.",
                    confidence=ConfidenceLevel.MEDIUM,
                ) for index, operation in enumerate(task.operation))
                groups = (tuple(item.task_id for item in generated),) if len(generated) > 1 else ()
                return DecompositionResult(TaskPlan(
                    tasks=generated,
                    parallel_groups=groups,
                    overall_objective=task.objective,
                    completion_condition="Complete the contextual follow-up and provide its output.",
                    is_multi_task=len(generated) > 1,
                    is_uncertain=True,
                    uncertainty_reasons=("Operation inherited from available conversation context.",),
                ))
            return DecompositionResult(TaskPlan(
                overall_objective=task.objective if task else text or None,
                is_uncertain=bool(text.strip()),
                uncertainty_reasons=("No explicit operation boundary was found.",) if text.strip() else (),
            ))

        segments = []
        for index, (start, end, _, operation) in enumerate(matches):
            stop = matches[index + 1][0] if index + 1 < len(matches) else len(text)
            description = text[start:stop].strip(" ,;.")
            description = re.split(
                r"\b(?:but|and)\s+(?:do not|don't|never)\b",
                description,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" ,;.")
            description = re.sub(r"\s+(?:and\s+then|and|then)\s*$", "", description, flags=re.IGNORECASE)
            preceding = text[matches[index - 1][1]:start].casefold() if index else ""
            segments.append((start, end, stop, operation, description, preceding))

        generated: list[SubTask] = []
        dependencies: list[TaskDependency] = []
        uncertainty: list[str] = []
        for index, (start, end, stop, operation, description, preceding) in enumerate(segments):
            subject = self._subjects(description, operation)
            if re.search(r"\b(?:it|that|those|them)\b", description, re.IGNORECASE):
                explicit_subjects = tuple(
                    item for item in subject
                    if item.casefold() not in _STOP
                    and not re.fullmatch(r"(?:19|20)\d{2}|\d[\d,.]*%?", item)
                )
                previous_subjects = tuple(
                    subject_name
                    for previous_task in generated
                    for subject_name in previous_task.subject
                )
                subject = tuple(dict.fromkeys(previous_subjects + explicit_subjects))
            if not subject and task and index == 0:
                subject = task.subject
            if re.search(r"\b(?:it|that|those|them)\b", description, re.IGNORECASE):
                if generated and generated[-1].subject:
                    subject = tuple(dict.fromkeys(generated[-1].subject + subject))
                else:
                    uncertainty.append(f"Subject reference in task {index + 1} could not be resolved.")
            task_id = f"task-{index + 1}"
            depends_on: tuple[str, ...] = ()
            sequential = bool(re.search(r"\bthen\b", preceding))
            refers_to_prior = bool(re.search(
                r"\b(?:it|that|those|them|the result|the findings|the analysis|these)\b",
                description, re.IGNORECASE,
            ))
            creates_deliverable = operation == ActionType.CREATE and bool(re.search(
                r"\b(?:report|summary|chart|table|presentation)\b",
                description, re.IGNORECASE,
            ))
            if index and sequential:
                depends_on = (generated[-1].task_id,)
                reason = "Explicit sequence marker."
            elif index and (refers_to_prior or creates_deliverable):
                depends_on = tuple(item.task_id for item in generated)
                if refers_to_prior:
                    reason = "Later operation refers to a preceding result or subject."
                else:
                    reason = "Deliverable combines preceding task results."
            if depends_on:
                dependencies.extend(TaskDependency(task_id, parent, reason) for parent in depends_on)
            output = self._output(operation)
            confidence = ConfidenceLevel.HIGH if subject else ConfidenceLevel.MEDIUM
            generated.append(SubTask(
                task_id=task_id,
                description=description,
                objective=description,
                operation=operation,
                subject=subject,
                inputs=subject,
                outputs=(output,),
                dependencies=depends_on,
                ordering=index + 1,
                parallelizable=not depends_on,
                completion_condition=f"Provide {output}.",
                confidence=confidence,
            ))

        if len(generated) == 1 and re.search(r"\b(?:and then|then)\b", text, re.IGNORECASE):
            uncertainty.append("A sequence marker was present without a separately detected operation.")
        roots = tuple(item.task_id for item in generated if not item.dependencies)
        parallel_groups = (roots,) if len(roots) > 1 else ()
        plan = TaskPlan(
            tasks=tuple(generated),
            dependencies=tuple(dependencies),
            parallel_groups=parallel_groups,
            overall_objective=task.objective if task and task.objective else text,
            completion_condition="Complete all requested tasks and provide their outputs.",
            is_multi_task=len(generated) > 1,
            is_uncertain=bool(uncertainty),
            uncertainty_reasons=tuple(dict.fromkeys(uncertainty)),
        )
        return DecompositionResult(plan)

    @staticmethod
    def _subjects(description: str, operation: ActionType) -> tuple[str, ...]:
        pattern = dict(_OPERATION_CUES)[operation]
        match = re.search(pattern, description, re.IGNORECASE)
        tail = description[match.end():] if match else description
        tail = re.sub(r"^\s+(?:why|what|how|whether|if)\b", " ", tail, flags=re.IGNORECASE)
        tail = re.split(r"\b(?:because|when|today|yesterday|tomorrow|using|under|within|before|after|in\s+(?:19|20)\d{2})\b", tail, maxsplit=1, flags=re.IGNORECASE)[0]
        pieces = re.split(r"\b(?:with|against|versus|vs\.?|and|from|to)\b", tail, flags=re.IGNORECASE)
        subjects = []
        for piece in pieces:
            piece = re.split(r"\b(?:is|are|was|were|has|have|will|would|could|should|can|did|does|do|reaches|falling|rising)\b", piece, maxsplit=1, flags=re.IGNORECASE)[0]
            words = re.findall(r"[A-Za-z][A-Za-z'-]*|[A-Z0-9]{2,}", piece)
            words = [word for word in words if word.casefold() not in _STOP]
            words = [word for word in words if not re.fullmatch(r"(?:19|20)\d{2}|\d[\d,.]*%?", word)]
            if words:
                subjects.append(" ".join(words[:4]))
        return tuple(dict.fromkeys(subjects))

    @staticmethod
    def _output(operation: ActionType) -> str:
        return {
            ActionType.EXPLAIN: "explanation",
            ActionType.CALCULATE: "calculation result",
            ActionType.RESEARCH: "research findings",
            ActionType.COMPARE: "comparison",
            ActionType.ANALYZE: "analysis",
            ActionType.PLAN: "plan",
            ActionType.CREATE: "created content",
            ActionType.MODIFY: "modified content",
            ActionType.MONITOR: "monitoring status",
            ActionType.ALERT: "alert result",
            ActionType.EXECUTE: "execution result",
        }.get(operation, "task result")