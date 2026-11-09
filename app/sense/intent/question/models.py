from dataclasses import dataclass, field
from enum import Enum

from app.sense.intent.models import ConfidenceLevel


class QuestionType(str, Enum):
    WHAT = "what"
    WHY = "why"
    HOW = "how"
    WHEN = "when"
    WHERE = "where"
    WHO = "who"
    WHICH = "which"
    HOW_MUCH = "how_much"
    HOW_MANY = "how_many"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class QuestionAmbiguity:
    is_ambiguous: bool = False
    candidates: tuple[QuestionType, ...] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True)
class QuestionDetectionResult:
    question_type: QuestionType = QuestionType.UNKNOWN
    is_question: bool = False
    conditional_question: bool = False
    question_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    question_ambiguity: QuestionAmbiguity = QuestionAmbiguity()
    source_span: tuple[int, int] | None = None
    matched_text: str | None = None