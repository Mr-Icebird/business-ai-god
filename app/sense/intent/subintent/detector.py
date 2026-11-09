import re

from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.subintent.knowledge import ACTION_SUBINTENTS, SUBINTENT_CUES
from app.sense.intent.subintent.models import SubIntentDetectionResult, SubIntentType


class SubIntentDetector:
    """Recognizes explicit sub-intent cues without inferring from topic words."""

    def detect(self, text: str) -> SubIntentDetectionResult:
        normalized = " ".join(text.casefold().split())
        matches = []
        for priority, (kind, patterns) in enumerate(SUBINTENT_CUES):
            positions = [
                match.start()
                for pattern in patterns
                if (match := re.search(pattern, normalized, re.IGNORECASE))
            ]
            if positions:
                matches.append((min(positions), priority, kind))
        detected = [kind for _, _, kind in sorted(matches)]
        if not detected:
            return SubIntentDetectionResult()

        # Social and conversational turns take precedence over incidental words.
        primary = detected[0]
        if primary in {SubIntentType.GREETING, SubIntentType.FAREWELL,
                       SubIntentType.CONFIRMATION, SubIntentType.NEGATION,
                       SubIntentType.CORRECTION, SubIntentType.CLARIFICATION,
                       SubIntentType.FOLLOW_UP, SubIntentType.CONTINUATION}:
            detected = [primary] + [item for item in detected[1:] if item in ACTION_SUBINTENTS]

        has_explicit_action = any(item in ACTION_SUBINTENTS for item in detected)
        confidence = ConfidenceLevel.HIGH if has_explicit_action else ConfidenceLevel.MEDIUM
        return SubIntentDetectionResult(
            primary=detected[0], detected=tuple(dict.fromkeys(detected)),
            confidence=confidence,
        )