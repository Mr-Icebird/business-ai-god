from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LanguageFamily(str, Enum):
    ENGLISH = "english"
    NIGERIAN_PIDGIN = "nigerian_pidgin"
    IGBO = "igbo"
    YORUBA = "yoruba"
    HAUSA = "hausa"
    UNKNOWN = "unknown"


class LanguageSignalType(str, Enum):
    WORD = "word"
    PHRASE = "phrase"
    PATTERN = "pattern"
    SCRIPT = "script"
    UNKNOWN = "unknown"


class DialectStatus(str, Enum):
    DETECTED = "detected"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LanguageSignal:
    text: str
    language: str
    signal_type: LanguageSignalType = LanguageSignalType.UNKNOWN
    weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "signal_type": self.signal_type.value,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class LanguageDetection:
    language: str | None = None
    dialect: str | None = None
    dialect_status: DialectStatus = DialectStatus.UNKNOWN
    confidence: float = 0.0
    candidates: tuple[tuple[str, float], ...] = field(
        default_factory=tuple
    )
    code_switching_detected: bool = False
    signals: tuple[LanguageSignal, ...] = field(
        default_factory=tuple
    )
    requires_external_intelligence: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "dialect": self.dialect,
            "dialect_status": self.dialect_status.value,
            "confidence": self.confidence,
            "candidates": [
                {
                    "language": language,
                    "confidence": confidence,
                }
                for language, confidence in self.candidates
            ],
            "code_switching_detected": self.code_switching_detected,
            "signals": [
                signal.to_dict()
                for signal in self.signals
            ],
            "requires_external_intelligence": (
                self.requires_external_intelligence
            ),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SlangDetection:
    text: str
    language: str | None = None
    meaning: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "meaning": self.meaning,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SpellingDetection:
    text: str
    suggested_correction: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "suggested_correction": self.suggested_correction,
            "confidence": self.confidence,
        }
