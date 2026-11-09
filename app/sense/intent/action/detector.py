import re

from app.sense.intent.action.models import ActionDetectionResult, ActionType
from app.sense.intent.models import ConfidenceLevel


_ACTION_CUES = (
    (ActionType.EXPLAIN, r"\b(?:explain|describe|clarify)\b"),
    (ActionType.CALCULATE, r"\b(?:calculate|compute|work out)\b"),
    (ActionType.RESEARCH, r"(?:^|\b(?:please|pls|actually,?|can you|can u|could you|would you|then|and|no,?\s+|i need to|i want to|i'd like to)\s+)(?:research|investigate|check|look\s+into)\b|\b(?:look up|find sources|gather information)\b|^\s*abeg\s+check\b"),
    (ActionType.COMPARE, r"\b(?:compare|contrast)\b|\b(?:versus|vs\.?)\b"),
    (ActionType.ANALYZE, r"\b(?:analy[sz]e|assess|evaluate)\b"),
    (ActionType.PLAN, r"\b(?:plan|prepare a plan|develop a strategy)\b|\b(?:build|create|develop)\s+(?:a\s+)?(?:trading\s+)?strategy\b"),
    (ActionType.CREATE, r"\b(?:create|make\b(?!\s+it\s+(?:shorter|briefer|narrower|broader))|build|write|draft|generate)\b"),
    (ActionType.MODIFY, r"\b(?:modify|change|update|edit|revise|amend|shorten|shorter|briefer|expand|narrow|narrower|broaden|broader)\b"),
    (ActionType.MONITOR, r"\b(?:monitor|track|watch)\b"),
    (ActionType.ALERT, r"\b(?:alert|notify|send an alert)\b"),
    (ActionType.EXECUTE, r"\b(?:execute|place|submit)\s+(?:(?:this|that|the|a)\s+)?(?:trade|order|transaction)\b"),
)


class ActionDetector:
    def detect(self, text: str) -> ActionDetectionResult:
        matches = []
        for priority, (action, pattern) in enumerate(_ACTION_CUES):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                matches.append((match.start(), priority, action))
        actions = tuple(action for _, _, action in sorted(matches))
        if not actions:
            return ActionDetectionResult()
        return ActionDetectionResult(
            primary=actions[0], actions=actions,
            confidence=ConfidenceLevel.HIGH,
        )