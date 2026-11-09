import re

from app.sense.input.models import InputUnderstandingResult
from app.sense.intent.action.models import ActionDetectionResult
from app.sense.intent.subintent.models import SubIntentDetectionResult
from app.sense.intent.task.models import TaskDetectionResult
from app.sense.intent.task.planner import TaskPlanner


_SUBJECT_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being",
    "between", "by", "for", "from", "has", "have", "how", "if", "in", "into",
    "is", "it", "me", "my", "of", "on", "or", "please", "that", "the", "their",
    "them", "there", "this", "to", "today", "was", "we", "what", "when", "where",
    "which", "who", "why", "will", "with", "would", "you", "u", "n",
    "next", "dey", "been", "moving", "moved", "fall", "fell", "rising", "rose",
    "these", "those", "two", "assets", "items", "things",
}
_OPERATION_CUE = re.compile(
    r"\b(?:research|investigate|analy[sz]e|compare|calculate|compute|explain|"
    r"predict|forecast|plan|create|build|write|draft|monitor|track|watch|alert|"
    r"modify|update|change|correct|execute|examine|assess|check|look\s+into)\b",
    re.IGNORECASE,
)
_SPLIT_CLAUSE = re.compile(r"\s*(?:and\s+|,\s*|then\s+)(?=(?:research|investigate|analy[sz]e|compare|calculate|explain|plan|create|monitor|track|alert)\b)")
_CONSTRAINT_CUE = re.compile(
    r"\b(?:within|at most|no more than|less than|under|above|below|before|after|using|without|only|between)\b[^,.;!?]*",
    re.IGNORECASE,
)
_TASK_INTENTS = frozenset({
    "information", "analysis", "research", "explanation", "comparison",
    "calculation", "prediction", "planning", "decision_support", "monitoring",
    "alert", "creation", "modification", "correction", "execution",
})


class TaskDetector:
    def __init__(self, planner: TaskPlanner | None = None) -> None:
        self._planner = planner or TaskPlanner()

    def detect(
        self,
        text: str,
        subintents: SubIntentDetectionResult,
        actions: ActionDetectionResult,
        source_input: InputUnderstandingResult | None = None,
        entity_mentions: tuple[str, ...] = (),
        context_subjects: tuple[str, ...] = (),
    ) -> TaskDetectionResult:
        actionable = bool(actions.actions or any(
            item.value in _TASK_INTENTS for item in subintents.detected
        ))
        subjects = list(entity_mentions) or (
            self._extract_subjects(
                text, prefer_for_target=actions.primary.value in {"create", "plan"}
            ) if actionable else []
        )
        if not subjects and any(item.value == "follow_up" for item in subintents.detected):
            follow_up = re.search(
                r"^\s*(?:what|how)\s+about\s+(?P<subject>[^?!,.]+)",
                text,
                re.IGNORECASE,
            )
            if follow_up:
                subjects = [follow_up.group("subject").strip()]
        if context_subjects and re.search(r"\b(?:it|that|those|them)\b", text, re.IGNORECASE):
            subjects = list(dict.fromkeys(context_subjects + tuple(subjects)))
        subjects = list(dict.fromkeys(item.strip() for item in subjects if item.strip()))
        outputs, completion = self._planner.plan(actions)
        constraints = tuple(dict.fromkeys(
            " ".join(match.group().split())
            for match in _CONSTRAINT_CUE.finditer(text)
        ))
        inputs = list(subjects)
        if source_input is not None:
            inputs.extend(item.text for item in source_input.dates)
            inputs.extend(item.text for item in source_input.numbers)
        else:
            inputs.extend(re.findall(
                r"\b(?:today|yesterday|tomorrow|last week|this week|next week)\b",
                text, re.IGNORECASE,
            ))
            inputs.extend(re.findall(r"(?<!\w)[$€£₦]?\d+(?:[.,]\d+)?%?", text))

        objective = " ".join(text.split()) or None
        return TaskDetectionResult(
            task_type=tuple(item for item in subintents.detected if item.value in _TASK_INTENTS),
            objective=objective,
            subject=tuple(subjects),
            operation=actions.actions,
            constraints=constraints,
            inputs=tuple(dict.fromkeys(inputs)),
            outputs=outputs,
            completion_condition=completion,
        )

    @staticmethod
    def _extract_subjects(text: str, prefer_for_target: bool = False) -> tuple[str, ...]:
        candidates: list[str] = []
        for clause in _SPLIT_CLAUSE.split(text):
            cue = _OPERATION_CUE.search(clause)
            if cue is None:
                tail = TaskDetector._question_subject_tail(clause)
                if tail is None:
                    continue
            else:
                tail = clause[cue.end():]
            if cue is not None and re.search(r"\balert\b", clause[:cue.start()] + clause[cue.start():cue.end()], re.IGNORECASE):
                trigger = re.search(r"\bwhen\s+(.+)$", clause, re.IGNORECASE)
                if trigger:
                    tail = trigger.group(1)
            tail = re.sub(r"^\s+(?:why|what|how|whether|if)\b", " ", tail, flags=re.IGNORECASE)
            tail = re.split(r"\bbut\b", tail, maxsplit=1, flags=re.IGNORECASE)[0]
            tail = re.sub(r"^\s*(?:happened|happens)\s+(?:to|with)\s+", " ", tail, flags=re.IGNORECASE)
            tail = re.split(r"\b(?:because|today|tomorrow|yesterday|if|so that|in\s+(?:19|20)\d{2})\b", tail, maxsplit=1, flags=re.IGNORECASE)[0]
            if prefer_for_target and re.search(r"\bfor\b", tail, re.IGNORECASE):
                tail = re.split(r"\bfor\b", tail, flags=re.IGNORECASE)[-1]
            pieces = re.split(r"\b(?:with|against|versus|vs\.?|and|n|from|to)\b", tail, flags=re.IGNORECASE)
            for piece in pieces:
                piece = re.split(r"\b(?:is|are|was|were|has|have|had|will|would|could|should|can|did|does|do)\b", piece, maxsplit=1, flags=re.IGNORECASE)[0]
                piece = re.sub(r"^\s*(?:happened|happens)\s+(?:to|with)\s+", " ", piece, flags=re.IGNORECASE)
                piece = re.split(r"\b(?:been|moving|moved|falling|fell|rising|rose|reaches|reach)\b", piece, maxsplit=1, flags=re.IGNORECASE)[0]
                words = re.findall(r"[A-Za-z][A-Za-z'-]*|[A-Z0-9]{2,}", piece)
                while words and words[0].casefold() in _SUBJECT_STOP:
                    words.pop(0)
                words = [
                    word for word in words
                    if word.casefold() not in _SUBJECT_STOP
                    and not re.fullmatch(r"(?:19|20)\d{2}|\d[\d,.]*%?", word)
                ]
                if words:
                    candidates.append(" ".join(words[:4]))
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _question_subject_tail(text: str) -> str | None:
        patterns = (
            r"\bwhat(?:'s| is)\s+(?:going on|happening)\s+(?:with|to|in)\s+(?P<subject>[^?!.,]+)",
            r"\bwhat(?:'s| is)\s+driving\s+(?P<subject>[^?!.,]+)",
            r"\bwhy\s+(?:has|have|did|does|is|are|was|were)?\s*(?P<subject>[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*)?)",
            r"\bif\s+(?P<subject>[A-Za-z][\w'-]*)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group("subject")
        return None