from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InputType(str, Enum):
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"
    DOCUMENT = "document"
    PDF = "pdf"
    IMAGE = "image"
    CHART = "chart"
    TABLE = "table"
    VIDEO_TRANSCRIPT = "video_transcript"
    API_DATA = "api_data"
    MARKET_DATA = "market_data"
    NEWS = "news"
    WEBSITE = "website"
    WEBSITE_INFORMATION = "website_information"
    SYSTEM_EVENT = "system_event"
    UNKNOWN = "unknown"


class LanguageStatus(str, Enum):
    DETECTED = "detected"
    MULTILINGUAL = "multilingual"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class DialectStatus(str, Enum):
    DETECTED = "detected"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class RecognitionStatus(str, Enum):
    DETECTED = "detected"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class DetectionSource(str, Enum):
    LOCAL_RULE = "local_rule"
    LOCAL_KNOWLEDGE = "local_knowledge"
    EXTERNAL_PROVIDER = "external_provider"
    USER_PROVIDED = "user_provided"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class TextSpanType(str, Enum):
    WORD = "word"
    PHRASE = "phrase"
    SENTENCE = "sentence"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    UNIT = "unit"
    URL = "url"
    SYMBOL = "symbol"
    ABBREVIATION = "abbreviation"
    SLANG = "slang"
    SPELLING = "spelling"
    CODE = "code"
    UNKNOWN = "unknown"


class LanguageRelationType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CODE_SWITCH = "code_switch"
    BORROWED_TERM = "borrowed_term"
    UNKNOWN = "unknown"


class SpellingIssueType(str, Enum):
    TYPO = "typo"
    MISSPELLING = "misspelling"
    ABBREVIATION = "abbreviation"
    INFORMAL_SPELLING = "informal_spelling"
    PHONETIC_SPELLING = "phonetic_spelling"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DetectionMetadata:
    """
    Describes where an interpretation came from and how reliable it is.
    This allows SENSE to combine local processing with future external
    language/AI providers without treating external output as automatic truth.
    """

    source: DetectionSource = DetectionSource.UNKNOWN
    provider: str | None = None
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "provider": self.provider,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
        }


@dataclass(frozen=True)
class TextSpan:
    """
    A meaningful portion of the original input.
    """

    text: str
    start: int | None = None
    end: int | None = None
    span_type: TextSpanType = TextSpanType.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "span_type": self.span_type.value,
        }


@dataclass(frozen=True)
class LanguageCandidate:
    """
    A possible language detected in the input.
    """

    language: str
    confidence: float = 0.0
    relation: LanguageRelationType = LanguageRelationType.UNKNOWN
    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "confidence": self.confidence,
            "relation": self.relation.value,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class SpellingIssue:
    """
    A possible spelling or informal-writing issue.

    SENSE does not silently change the owner's original input.
    A correction is an interpretation that can be reviewed later.
    """

    text: str
    issue_type: SpellingIssueType = SpellingIssueType.UNKNOWN
    suggested_correction: str | None = None
    confidence: float = 0.0
    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "issue_type": self.issue_type.value,
            "suggested_correction": self.suggested_correction,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class SlangMention:
    """
    A slang, informal, colloquial, or culturally specific expression.

    The expression itself is preserved. Meaning can be supplied later
    by local knowledge or an external language provider.
    """

    text: str
    language: str | None = None
    meaning: str | None = None
    confidence: float = 0.0
    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "meaning": self.meaning,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True, eq=False)
class AbbreviationMention:
    text: str
    expanded_form: str | None = None
    domain: str | None = None
    confidence: float = 0.0
    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.text == other
        if isinstance(other, AbbreviationMention):
            return (
                self.text == other.text
                and self.expanded_form == other.expanded_form
                and self.domain == other.domain
                and self.confidence == other.confidence
                and self.metadata == other.metadata
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "expanded_form": self.expanded_form,
            "domain": self.domain,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class NumericMention:
    text: str
    value: float | None = None
    unit: str | None = None
    currency: str | None = None
    percentage: float | None = None

    # Additional quantitative information.
    multiplier: float | None = None
    multiplier_text: str | None = None
    ratio: float | None = None
    basis_points: float | None = None
    normalized_value: float | None = None

    # Useful when a number has a financial/economic meaning.
    quantity_type: str | None = None

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "value": self.value,
            "unit": self.unit,
            "currency": self.currency,
            "percentage": self.percentage,
            "multiplier": self.multiplier,
            "multiplier_text": self.multiplier_text,
            "ratio": self.ratio,
            "basis_points": self.basis_points,
            "normalized_value": self.normalized_value,
            "quantity_type": self.quantity_type,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class DateMention:
    text: str
    normalized: str | None = None

    # Allows later temporal intelligence to distinguish
    # an exact date from a relative expression.
    temporal_type: str | None = None
    timezone: str | None = None

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "normalized": self.normalized,
            "temporal_type": self.temporal_type,
            "timezone": self.timezone,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class URLMention:
    text: str
    scheme: str | None = None
    domain: str | None = None
    path: str | None = None

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "scheme": self.scheme,
            "domain": self.domain,
            "path": self.path,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True, eq=False)
class CurrencyMention:
    text: str
    code: str | None = None
    symbol: str | None = None
    name: str | None = None
    confidence: float = 0.0

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.code == other
        if isinstance(other, CurrencyMention):
            return (
                self.text == other.text
                and self.code == other.code
                and self.symbol == other.symbol
                and self.name == other.name
                and self.confidence == other.confidence
                and self.metadata == other.metadata
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.code, self.text))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "code": self.code,
            "symbol": self.symbol,
            "name": self.name,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class UnitMention:
    text: str
    normalized: str | None = None
    category: str | None = None
    confidence: float = 0.0

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "normalized": self.normalized,
            "category": self.category,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class SymbolMention:
    text: str
    meaning: str | None = None
    category: str | None = None
    confidence: float = 0.0

    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "meaning": self.meaning,
            "category": self.category,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True)
class InputUnderstandingResult:
    """
    Complete structured result produced by SENSE-1 input understanding.

    The original input is always preserved. SENSE may interpret it,
    normalize information, or request external intelligence, but it
    must not silently rewrite the owner's original message.
    """

    raw_input: str

    input_type: InputType = InputType.TEXT

    # Language
    language: str | None = None
    language_status: LanguageStatus = LanguageStatus.UNKNOWN
    dialect: str | None = None
    dialect_status: DialectStatus = DialectStatus.UNKNOWN
    language_candidates: tuple[LanguageCandidate, ...] = field(
        default_factory=tuple
    )
    code_switching_detected: bool = False

    # Writing/language quality
    spelling_status: RecognitionStatus = RecognitionStatus.UNKNOWN
    spelling_errors_detected: bool = False
    spelling_issues: tuple[SpellingIssue, ...] = field(
        default_factory=tuple
    )
    abbreviations: tuple[AbbreviationMention, ...] = field(default_factory=tuple)
    abbreviation_mentions: tuple[AbbreviationMention, ...] = field(
        default_factory=tuple
    )
    slang: tuple[SlangMention, ...] = field(default_factory=tuple)
    slang_status: RecognitionStatus = RecognitionStatus.UNKNOWN
    slang_mentions: tuple[SlangMention, ...] = field(
        default_factory=tuple
    )

    # Quantitative information
    numbers: tuple[NumericMention, ...] = field(
        default_factory=tuple
    )
    dates: tuple[DateMention, ...] = field(
        default_factory=tuple
    )
    percentages: tuple[NumericMention, ...] = field(
        default_factory=tuple
    )
    units: tuple[UnitMention, ...] = field(default_factory=tuple)
    unit_mentions: tuple[UnitMention, ...] = field(
        default_factory=tuple
    )
    currencies: tuple[CurrencyMention, ...] = field(default_factory=tuple)
    currency_mentions: tuple[CurrencyMention, ...] = field(
        default_factory=tuple
    )
    symbols: tuple[SymbolMention, ...] = field(default_factory=tuple)
    symbol_mentions: tuple[SymbolMention, ...] = field(
        default_factory=tuple
    )

    # URLs
    urls: tuple[URLMention, ...] = field(
        default_factory=tuple
    )

    # General text spans
    spans: tuple[TextSpan, ...] = field(
        default_factory=tuple
    )

    # Structural detection
    is_code: bool = False
    is_command: bool = False
    is_question: bool = False
    is_statement: bool = False

    # Interpretation/processing state
    normalized_text: str | None = None
    requires_external_intelligence: bool = False
    external_intelligence_reason: str | None = None
    requires_content_extraction: bool = False
    content_extraction_reason: str | None = None
    content_reference: str | None = None
    input_metadata: dict[str, Any] = field(default_factory=dict)

    # Ambiguity
    ambiguous: bool = False
    ambiguity_reason: str | None = None

    # Overall confidence
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_LOW

    # Provenance for the complete result.
    metadata: DetectionMetadata = field(
        default_factory=DetectionMetadata
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "input_type": self.input_type.value,

            "language": self.language,
            "language_status": self.language_status.value,
            "dialect": self.dialect,
            "dialect_status": self.dialect_status.value,
            "language_candidates": [
                candidate.to_dict()
                for candidate in self.language_candidates
            ],
            "code_switching_detected": self.code_switching_detected,

            "spelling_errors_detected": self.spelling_errors_detected,
            "spelling_status": self.spelling_status.value,
            "spelling_issues": [
                issue.to_dict()
                for issue in self.spelling_issues
            ],

            # Preserve the original simple fields for compatibility.
            "abbreviations": [item.text for item in self.abbreviations],
            "abbreviation_mentions": [
                abbreviation.to_dict()
                for abbreviation in self.abbreviation_mentions
            ],

            "slang": [item.text for item in self.slang],
            "slang_status": self.slang_status.value,
            "slang_mentions": [
                slang.to_dict()
                for slang in self.slang_mentions
            ],

            "numbers": [
                number.to_dict()
                for number in self.numbers
            ],

            "dates": [
                date.to_dict()
                for date in self.dates
            ],

            "percentages": [
                percentage.to_dict()
                for percentage in self.percentages
            ],

            "units": [item.text for item in self.units],
            "unit_mentions": [
                unit.to_dict()
                for unit in self.unit_mentions
            ],

            "currencies": [item.code for item in self.currencies],
            "currency_mentions": [
                currency.to_dict()
                for currency in self.currency_mentions
            ],

            "symbols": [item.text for item in self.symbols],
            "symbol_mentions": [
                symbol.to_dict()
                for symbol in self.symbol_mentions
            ],

            "urls": [
                url.to_dict()
                for url in self.urls
            ],

            "spans": [
                span.to_dict()
                for span in self.spans
            ],

            "is_code": self.is_code,
            "is_command": self.is_command,
            "is_question": self.is_question,
            "is_statement": self.is_statement,

            "normalized_text": self.normalized_text,
            "requires_external_intelligence": (
                self.requires_external_intelligence
            ),
            "external_intelligence_reason": (
                self.external_intelligence_reason
            ),
            "requires_content_extraction": self.requires_content_extraction,
            "content_extraction_reason": self.content_extraction_reason,
            "content_reference": self.content_reference,
            "input_metadata": dict(self.input_metadata),

            "ambiguous": self.ambiguous,
            "ambiguity_reason": self.ambiguity_reason,

            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,

            "metadata": self.metadata.to_dict(),
        }


def confidence_level_for(value: float) -> ConfidenceLevel:
    """
    Convert a numeric confidence score into a stable qualitative level.
    """

    value = max(0.0, min(1.0, float(value)))

    if value >= 0.90:
        return ConfidenceLevel.VERY_HIGH

    if value >= 0.75:
        return ConfidenceLevel.HIGH

    if value >= 0.50:
        return ConfidenceLevel.MEDIUM

    if value >= 0.25:
        return ConfidenceLevel.LOW

    return ConfidenceLevel.VERY_LOW