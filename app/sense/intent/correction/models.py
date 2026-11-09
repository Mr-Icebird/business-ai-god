from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class CorrectionType(str, Enum):
    NONE = "none"
    OWNER_CORRECTION = "owner_correction"
    INTENT_REPLACEMENT = "intent_replacement"
    TASK_MODIFICATION = "task_modification"
    CONSTRAINT_MODIFICATION = "constraint_modification"
    REINTERPRETATION = "reinterpretation"


@dataclass(frozen=True)
class CorrectionChange:
    field_name: str
    previous_value: str
    updated_value: str
    source_text: str
    source_span: tuple[int, int] | None = None


@dataclass(frozen=True)
class CorrectionDetectionResult:
    is_correction: bool = False
    correction_type: CorrectionType = CorrectionType.NONE
    affected_fields: tuple[str, ...] = field(default_factory=tuple)
    changes: tuple[CorrectionChange, ...] = field(default_factory=tuple)
    previous_interpretation: str | None = None
    new_interpretation: str | None = None
    preserved_fields: tuple[str, ...] = field(default_factory=tuple)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    source_text: str | None = None