import re

from app.sense.intent.models import ConfidenceLevel
from app.sense.intent.question.models import (
    QuestionAmbiguity,
    QuestionDetectionResult,
    QuestionType,
)


_CUES = (
    (QuestionType.HOW_MUCH, r"\bhow\s+much\b"),
    (QuestionType.HOW_MANY, r"\bhow\s+many\b"),
    (QuestionType.WHAT, r"\bwhat\b"),
    (QuestionType.WHY, r"\bwhy\b"),
    (QuestionType.HOW, r"\bhow\b"),
    (QuestionType.WHEN, r"\bwhen\b"),
    (QuestionType.WHERE, r"\bwhere\b"),
    (QuestionType.WHO, r"\bwho\b"),
    (QuestionType.WHICH, r"\bwhich\b"),
)
_INDIRECT_PREFIX = re.compile(
    r"^\s*(?:(?:please\s+)?(?:can|could|would|will|do|does|did|is|are|"
    r"was|were|have|has|had|may|might|should)\s+you\b|"
    r"(?:please\s+)?(?:tell|show|explain|let me know)\b|"
    r"i\s+(?:want|would like|need)\s+to\s+know|i'd\s+like\s+to\s+know)\s*",
    re.IGNORECASE,
)
_CONDITIONAL = re.compile(
    r"(?:^\s*if\b.*\b(?:what|why|how|when|where|who|which)\b|"
    r"^\s*(?:what|why|how|when|where|who|which)\b[^?]*\bif\b)",
    re.IGNORECASE,
)
_DIRECT_PREFIX = re.compile(
    r"^\s*(?:what|why|how|when|where|who|which)\b", re.IGNORECASE
)
_DIRECT_QUERY = re.compile(
    r"^\s*(?:what|why|how|when|where|who|which)\s+"
    r"(?:is|are|was|were|do|does|did|can|could|would|will|has|have|had|"
    r"happened|caused|affects|impact|much|many)\b",
    re.IGNORECASE,
)


class QuestionDetector:
    def detect(self, text: str) -> QuestionDetectionResult:
        normalized = text
        if not normalized.strip():
            return QuestionDetectionResult()

        conditional_match = _CONDITIONAL.search(normalized)
        direct_match = _DIRECT_PREFIX.search(normalized)
        indirect_match = _INDIRECT_PREFIX.search(normalized)
        is_question = bool(
            conditional_match
            or direct_match and ("?" in normalized or _DIRECT_QUERY.search(normalized))
            or re.match(r"^\s*(?:what's|whats)\b", normalized, re.IGNORECASE)
            or indirect_match and any(
                re.search(pattern, normalized[indirect_match.end():], re.IGNORECASE)
                for _, pattern in _CUES
            )
            or "?" in normalized
        )
        if not is_question:
            return QuestionDetectionResult()

        if conditional_match:
            return QuestionDetectionResult(
                question_type=QuestionType.CONDITIONAL,
                is_question=True,
                conditional_question=True,
                question_confidence=ConfidenceLevel.HIGH,
                source_span=(conditional_match.start(), conditional_match.end()),
                matched_text=normalized[conditional_match.start():conditional_match.end()],
            )

        search_from = indirect_match.end() if indirect_match else 0
        matches = []
        for priority, (question_type, pattern) in enumerate(_CUES):
            match = re.search(pattern, normalized[search_from:], re.IGNORECASE)
            if match:
                matches.append((match.start() + search_from, priority, question_type, match))
        if not matches:
            return QuestionDetectionResult(
                is_question=True,
                question_confidence=ConfidenceLevel.LOW,
                question_ambiguity=QuestionAmbiguity(
                    reason="Question detected, but its type is not supported."
                ),
            )

        matches.sort(key=lambda item: (item[0], item[1]))
        start, _, question_type, match = matches[0]
        distinct = tuple(dict.fromkeys(item[2] for item in matches))
        if QuestionType.HOW in distinct and any(
            kind in distinct for kind in (QuestionType.HOW_MUCH, QuestionType.HOW_MANY)
        ):
            distinct = tuple(kind for kind in distinct if kind != QuestionType.HOW)
        ambiguous = len(distinct) > 1
        confidence = ConfidenceLevel.MEDIUM if indirect_match else ConfidenceLevel.HIGH
        return QuestionDetectionResult(
            question_type=question_type,
            is_question=True,
            question_confidence=confidence,
            question_ambiguity=QuestionAmbiguity(
                is_ambiguous=ambiguous,
                candidates=distinct if ambiguous else (),
                reason="Multiple question cues were found." if ambiguous else None,
            ),
            source_span=(start, start + len(match.group())),
            matched_text=match.group(),
        )