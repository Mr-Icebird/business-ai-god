from app.sense.intent.detection.knowledge import INTENT_HIERARCHY
from app.sense.intent.detection.models import IntentDetectionResult, IntentType
from app.sense.intent.action.models import ActionDetectionResult, ActionType
from app.sense.intent.models import AmbiguityInfo, ConfidenceLevel
from app.sense.intent.subintent.models import SubIntentDetectionResult, SubIntentType


_SUBINTENT_MAP = {item.value: IntentType(item.value) for item in SubIntentType if item.value != "unknown"}


class IntentDetector:
    """Selects a primary intent and preserves other evidenced intents."""

    def detect(
        self,
        text: str,
        subintents: SubIntentDetectionResult,
        actions: ActionDetectionResult | None = None,
    ) -> IntentDetectionResult:
        detected = [
            _SUBINTENT_MAP[item.value]
            for item in subintents.detected
            if item.value in _SUBINTENT_MAP
        ]
        if actions is not None and ActionType.EXECUTE in actions.actions:
            detected.append(IntentType.EXECUTION)
        if not detected:
            return IntentDetectionResult(
                ambiguity=AmbiguityInfo(
                    is_ambiguous=bool(text.strip()),
                    reason="No clear intent cue was detected." if text.strip() else None,
                )
            )

        primary = subintents.primary
        primary_intent = _SUBINTENT_MAP.get(primary.value)
        if primary_intent is None or primary_intent not in detected:
            primary_intent = detected[0]
        secondary = tuple(item for item in detected if item != primary_intent)
        confidence = (
            subintents.confidence
            if subintents.primary.value != "unknown"
            else actions.confidence if actions is not None else ConfidenceLevel.UNKNOWN
        )
        return IntentDetectionResult(
            primary_intent=primary_intent,
            secondary_intents=secondary,
            multi_intent=bool(secondary),
            hierarchy=tuple(INTENT_HIERARCHY[item] for item in detected),
            confidence=confidence,
            ambiguity=AmbiguityInfo(),
        )