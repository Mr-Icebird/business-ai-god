import re
import unicodedata

from .knowledge import (
    AMERICAN_ENGLISH_MARKERS,
    BRITISH_ENGLISH_MARKERS,
    ENGLISH_MARKERS,
    ENGLISH_SLANG,
    FRENCH_MARKERS,
    GERMAN_MARKERS,
    HAUSA_MARKERS,
    ITALIAN_MARKERS,
    IGBO_MARKERS,
    NIGERIAN_PIDGIN_PHRASES,
    NIGERIAN_PIDGIN_WORDS,
    PORTUGUESE_MARKERS,
    SPANISH_MARKERS,
    SPELLING_CORRECTIONS,
    YORUBA_MARKERS,
)
from .models import (
    DialectStatus,
    LanguageDetection,
    LanguageSignal,
    LanguageSignalType,
    SlangDetection,
    SpellingDetection,
)


class LanguageIntelligence:
    """
    Local-first language intelligence for SENSE-1.

    This component detects language signals and linguistic patterns.
    It does not pretend that a small local knowledge base can cover
    every language, dialect, slang expression, or cultural variation.

    External providers will be connected later through a separate
    provider layer.
    """

    WORD_PATTERN = re.compile(r"\b[a-zA-ZÀ-ÖØ-öø-ÿ']+\b")

    def detect(self, text: str) -> LanguageDetection:
        if not text.strip():
            return LanguageDetection(
                reason="Empty input."
            )

        normalized = text.lower().strip()
        signal_text = "".join(
            character
            for character in unicodedata.normalize("NFKD", normalized)
            if not unicodedata.combining(character)
        )
        words = self.WORD_PATTERN.findall(signal_text)

        if not words:
            return LanguageDetection(
                language="unknown",
                confidence=0.0,
                requires_external_intelligence=any(
                    character.isalpha() for character in text
                ),
                reason=(
                    "Non-Latin-script language detection requires external "
                    "language intelligence."
                    if any(character.isalpha() for character in text)
                    else "No linguistic word tokens detected."
                ),
            )

        scores: dict[str, float] = {
            "en": 0.0,
            "pcm": 0.0,
            "ig": 0.0,
            "yo": 0.0,
            "ha": 0.0,
            "es": 0.0,
            "fr": 0.0,
            "de": 0.0,
            "pt": 0.0,
            "it": 0.0,
        }

        signals: list[LanguageSignal] = []

        self._score_words(
            words,
            ENGLISH_MARKERS,
            "en",
            scores,
            signals,
        )

        for vocabulary in (
            BRITISH_ENGLISH_MARKERS,
            AMERICAN_ENGLISH_MARKERS,
        ):
            self._score_words(
                words,
                vocabulary,
                "en",
                scores,
                signals,
            )

        self._score_words(
            words,
            NIGERIAN_PIDGIN_WORDS,
            "pcm",
            scores,
            signals,
        )

        self._score_words(
            words,
            IGBO_MARKERS,
            "ig",
            scores,
            signals,
        )

        self._score_words(
            words,
            YORUBA_MARKERS,
            "yo",
            scores,
            signals,
        )

        self._score_words(
            words,
            HAUSA_MARKERS,
            "ha",
            scores,
            signals,
        )
        for language, vocabulary in (
            ("es", SPANISH_MARKERS),
            ("fr", FRENCH_MARKERS),
            ("de", GERMAN_MARKERS),
            ("pt", PORTUGUESE_MARKERS),
            ("it", ITALIAN_MARKERS),
        ):
            self._score_words(words, vocabulary, language, scores, signals)

        for phrase in NIGERIAN_PIDGIN_PHRASES:
            if phrase in normalized:
                scores["pcm"] += 2.0
                signals.append(
                    LanguageSignal(
                        text=phrase,
                        language="pcm",
                        signal_type=LanguageSignalType.PHRASE,
                        weight=2.0,
                    )
                )

        candidates = sorted(
            (
                (language, score)
                for language, score in scores.items()
                if score > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        if not candidates:
            return self._latin_fallback(
                words=words,
                signals=signals,
            )

        primary_language, primary_score = candidates[0]

        total_score = sum(
            score
            for _, score in candidates
        )

        confidence = (
            primary_score / total_score
            if total_score > 0
            else 0.0
        )
        evidence_coverage = min(1.0, primary_score / len(words))
        confidence = min(confidence, evidence_coverage)

        # A single weak marker should not create high confidence.
        if primary_score < 2.0:
            confidence = min(confidence, 0.55)

        code_switching = (
            len(
                [
                    score
                    for _, score in candidates
                    if score >= 1.0
                ]
            )
            > 1
        )

        dialect = None
        dialect_status = DialectStatus.UNKNOWN
        dialect_conflict = False

        if primary_language == "pcm":
            dialect = "Nigerian Pidgin"
            dialect_status = DialectStatus.DETECTED
        elif primary_language == "en":
            british_score = sum(word in BRITISH_ENGLISH_MARKERS for word in words)
            american_score = sum(word in AMERICAN_ENGLISH_MARKERS for word in words)
            if british_score and american_score:
                dialect_status = DialectStatus.UNCERTAIN
                dialect_conflict = True
            elif british_score:
                dialect = "British English"
                dialect_status = DialectStatus.DETECTED
            elif american_score:
                dialect = "American English"
                dialect_status = DialectStatus.DETECTED

        requires_external = (
            confidence < 0.70
            or code_switching
            or dialect_conflict
        )

        if dialect_conflict:
            reason = "Conflicting supported dialect signals require review."
        elif requires_external:
            reason = (
                "Local evidence is insufficient for high-confidence "
                "language interpretation."
            )
        else:
            reason = "Detected from local linguistic signals."

        normalized_candidates = tuple(
            (
                language,
                round(
                    score / total_score,
                    4,
                ),
            )
            for language, score in candidates
        )

        return LanguageDetection(
            language=primary_language,
            dialect=dialect,
            dialect_status=dialect_status,
            confidence=round(confidence, 4),
            candidates=normalized_candidates,
            code_switching_detected=code_switching,
            signals=tuple(signals),
            requires_external_intelligence=requires_external,
            reason=reason,
        )

    def detect_slang(
        self,
        text: str,
    ) -> tuple[SlangDetection, ...]:
        normalized = text.lower()

        results: list[SlangDetection] = []

        for word in self.WORD_PATTERN.findall(normalized):
            if word in ENGLISH_SLANG:
                results.append(
                    SlangDetection(
                        text=word,
                        language="en",
                        confidence=0.98,
                    )
                )

            elif word in NIGERIAN_PIDGIN_WORDS:
                results.append(
                    SlangDetection(
                        text=word,
                        language="pcm",
                        confidence=0.90,
                    )
                )

        # Preserve order while removing duplicates.
        unique: dict[str, SlangDetection] = {}

        for item in results:
            unique.setdefault(item.text, item)

        return tuple(unique.values())

    def detect_spelling(
        self,
        text: str,
    ) -> tuple[SpellingDetection, ...]:
        results: list[SpellingDetection] = []

        for word in self.WORD_PATTERN.findall(
            text.lower()
        ):
            correction = SPELLING_CORRECTIONS.get(word)

            if correction:
                results.append(
                    SpellingDetection(
                        text=word,
                        suggested_correction=correction,
                        confidence=0.99,
                    )
                )

        return tuple(results)

    @staticmethod
    def _score_words(
        words: list[str],
        vocabulary: set[str],
        language: str,
        scores: dict[str, float],
        signals: list[LanguageSignal],
    ) -> None:
        for word in words:
            if word in vocabulary:
                scores[language] += 1.0

                signals.append(
                    LanguageSignal(
                        text=word,
                        language=language,
                        signal_type=LanguageSignalType.WORD,
                        weight=1.0,
                    )
                )

    def _latin_fallback(
        self,
        *,
        words: list[str],
        signals: list[LanguageSignal],
    ) -> LanguageDetection:
        """
        Latin-script fallback.

        This deliberately does NOT claim that every Latin-script
        message is English. Unknown Latin-script languages should
        eventually be handled by external language intelligence.
        """

        if all(
            re.fullmatch(
                r"[a-zA-ZÀ-ÖØ-öø-ÿ']+",
                word,
            )
            for word in words
        ):
            return LanguageDetection(
                language="unknown",
                confidence=0.0,
                candidates=(),
                signals=tuple(signals),
                requires_external_intelligence=True,
                reason=(
                    "Latin-script text detected, but local linguistic "
                    "evidence is insufficient for reliable language "
                    "identification."
                ),
            )

        return LanguageDetection(
            confidence=0.0,
            signals=tuple(signals),
            requires_external_intelligence=True,
            reason=(
                "No sufficiently reliable local language evidence."
            ),
        )


LANGUAGE_INTELLIGENCE = LanguageIntelligence()
