import re
from dataclasses import replace

from app.sense.domain.correction.models import (
    CorrectionHistoryEntry,
    CorrectionType,
    DomainScopeCorrection,
    InterpretationUpdate,
)
from app.sense.domain.models import (
    DomainConfidence,
    DomainType,
    EvidenceProvenance,
)
from app.sense.domain.scope.models import ScopeType

_CORRECTION_MARKER = re.compile(
    r"\b(?:i mean|i meant|actually|rather|instead|forget|ignore|remove|drop|"
    r"exclude|omit|focus only)\b|^\s*no,?\s+"
    r"(?=i mean|i meant|use|physical|financial|company|stock|futures)",
    re.I,
)
_REMOVAL_TARGET = re.compile(
    r"\b(?:forget|ignore|remove|drop|exclude|omit)\s+(?:the\s+)?"
    r"(?P<target>[\w'-]+(?:\s+[\w'-]+){0,3}?)(?:\s+part)?(?=[.,;!?]|$)",
    re.I,
)
_NEGATED_TARGET = re.compile(
    r"\bnot\s+(?:(?:its|their|the|that|those)\s+)?"
    r"(?P<target>[\w'-]+(?:\s+[\w'-]+){0,2}?)(?=[.,;!?]|$)",
    re.I,
)
_FINANCIAL_MARKER = re.compile(
    r"\b(?:stock|shares?|futures?|ticker|equities|financial market|"
    r"stock price|share price)\b",
    re.I,
)
_PHYSICAL_MARKER = re.compile(
    r"\b(?:physical|production|produced|mining|physical supply|buyers?|"
    r"shipment|delivered|extraction|refining)\b",
    re.I,
)
_REFERENCE = re.compile(r"\b(?:it|its|they|them|that|those|this|their)\b", re.I)
_WORD = re.compile(r"[a-z0-9]+", re.I)
_SUBJECT_STOP_WORDS = {
    "a",
    "about",
    "actually",
    "an",
    "and",
    "analyze",
    "analyse",
    "are",
    "as",
    "at",
    "business",
    "company",
    "compare",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "its",
    "mean",
    "meant",
    "of",
    "on",
    "or",
    "research",
    "shares",
    "stock",
    "stocks",
    "the",
    "their",
    "them",
    "they",
    "this",
    "that",
    "to",
    "use",
    "what",
    "with",
    "futures",
    "future",
    "physical",
    "financial",
    "market",
    "markets",
    "supply",
    "production",
    "produced",
    "buyers",
}


class DomainScopeCorrectionDetector:
    def detect(self, text, current, context=None) -> DomainScopeCorrection:
        marker = _CORRECTION_MARKER.search(text)
        previous = context.previous_result if context is not None else None
        if marker is None or previous is None:
            return DomainScopeCorrection()
        if not self._same_subject(previous.raw_text, text, context):
            return DomainScopeCorrection()

        previous_domains = previous.classification.domains
        previous_scopes = self._scopes(previous)
        previous_scope_subjects = (
            previous.scope_classification.scope_subjects
            if previous.scope_classification is not None
            else ()
        )
        current_scope_subjects = (
            current.scope_classification.scope_subjects
            if current.scope_classification is not None
            else ()
        )
        previous_domain_evidence = tuple(
            self._historical_evidence(item) for item in previous.detection.signals
        )
        previous_scope_evidence = (
            tuple(
                self._historical_evidence(item)
                for item in previous.scope_detection.evidence
            )
            if previous.scope_detection is not None
            else ()
        )
        current_domain_evidence = tuple(
            item
            for item in current.detection.signals
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
        )
        current_scope_evidence = (
            tuple(
                item
                for item in current.scope_detection.evidence
                if item.provenance == EvidenceProvenance.SOURCE_TEXT
            )
            if current.scope_detection is not None
            else ()
        )
        current_domain_types = {item.domain for item in current_domain_evidence}
        current_domains = tuple(
            item
            for item in current.classification.domains
            if item in current_domain_types
        )
        current_scope_types = {item.scope_type for item in current_scope_evidence}
        current_scopes = tuple(
            item
            for item in self._scopes(current, exclude_inherited=True)
            if item in current_scope_types
        )

        physical_correction = bool(
            _PHYSICAL_MARKER.search(text)
            and ScopeType.PHYSICAL_COMMERCE in current_scope_types
        )
        financial_correction = bool(
            _FINANCIAL_MARKER.search(text)
            and ScopeType.FINANCIAL_MARKET in current_scope_types
        )
        preserved_domains = self._preserved_domains(
            previous_domains,
            previous_domain_evidence,
            text,
            current_domains,
            physical_correction,
            self._removed_terms(text),
        )
        preserved_scopes = self._preserved_scopes(
            previous_scopes,
            current_scopes,
            physical_correction,
            financial_correction,
            previous_scope_evidence,
            self._removed_terms(text),
        )
        updated_domains = tuple(dict.fromkeys((*preserved_domains, *current_domains)))
        updated_scopes = tuple(dict.fromkeys((*preserved_scopes, *current_scopes)))
        changes_domains = set(updated_domains) != set(previous_domains)
        changes_scopes = set(updated_scopes) != set(previous_scopes)
        changes_scope_subjects = bool(re.search(r"\bfocus only\b", text, re.I)) and set(
            current_scope_subjects
        ) != set(previous_scope_subjects)
        if not changes_domains and not changes_scopes and not changes_scope_subjects:
            return DomainScopeCorrection()

        updates = []
        if changes_domains:
            updates.append(
                InterpretationUpdate(
                    "domains",
                    self._values(previous_domains),
                    self._values(updated_domains),
                    marker.group(),
                    marker.span(),
                    text,
                )
            )
        if changes_scopes:
            updates.append(
                InterpretationUpdate(
                    "scopes",
                    self._values(previous_scopes),
                    self._values(updated_scopes),
                    marker.group(),
                    marker.span(),
                    text,
                )
            )

        if changes_scope_subjects:
            updates.append(
                InterpretationUpdate(
                    "scope_subjects",
                    ", ".join(previous_scope_subjects),
                    ", ".join(current_scope_subjects),
                    marker.group(),
                    marker.span(),
                    text,
                )
            )

        if changes_domains and changes_scopes:
            kind = CorrectionType.INTERPRETATION_REPLACEMENT
        elif changes_domains:
            kind = self._change_type(previous_domains, updated_domains, domain=True)
        elif physical_correction or financial_correction or self._removed_terms(text):
            kind = CorrectionType.SCOPE_REPLACEMENT
        else:
            kind = self._change_type(previous_scopes, updated_scopes, domain=False)

        correction_confidence = self._correction_confidence(
            current_domain_evidence, current_scope_evidence
        )
        previous_domain_confidence = (
            previous.confidence.domain
            if previous.confidence is not None
            else previous.classification.confidence
        )
        previous_scope_confidence = (
            previous.confidence.scope
            if previous.confidence is not None
            else self._evidence_confidence(previous_scope_evidence)
        )
        history = self._history(previous)
        entry = CorrectionHistoryEntry(
            correction_type=kind,
            updates=tuple(updates),
            previous_domains=previous_domains,
            updated_domains=updated_domains,
            previous_scopes=previous_scopes,
            updated_scopes=updated_scopes,
            previous_domain_evidence=previous_domain_evidence,
            updated_domain_evidence=current_domain_evidence,
            previous_scope_evidence=previous_scope_evidence,
            updated_scope_evidence=current_scope_evidence,
            previous_scope_subjects=previous_scope_subjects,
            updated_scope_subjects=current_scope_subjects,
            evidence=text,
            confidence=correction_confidence,
            evidence_provenance=EvidenceProvenance.SOURCE_TEXT,
        )
        history = (*history, entry)
        return DomainScopeCorrection(
            detected=True,
            correction_type=kind,
            updates=tuple(updates),
            previous_domains=previous_domains,
            updated_domains=updated_domains,
            previous_scopes=previous_scopes,
            updated_scopes=updated_scopes,
            preserved_context=self._preserved_context(
                previous,
                changes_domains,
                changes_scopes,
                preserved_domains,
                preserved_scopes,
            ),
            evidence=text,
            confidence=correction_confidence,
            previous_domain_evidence=previous_domain_evidence,
            updated_domain_evidence=current_domain_evidence,
            previous_scope_evidence=previous_scope_evidence,
            updated_scope_evidence=current_scope_evidence,
            preserved_domains=preserved_domains,
            preserved_scopes=preserved_scopes,
            previous_domain_confidence=previous_domain_confidence,
            previous_scope_confidence=previous_scope_confidence,
            history=history,
            evidence_provenance=EvidenceProvenance.SOURCE_TEXT,
            previous_scope_subjects=previous_scope_subjects,
            updated_scope_subjects=current_scope_subjects,
        )

    @staticmethod
    def _same_subject(previous_text, current_text, context):
        previous_subjects = DomainScopeCorrectionDetector._subject_terms(previous_text)
        if context.previous_text:
            previous_subjects.update(
                DomainScopeCorrectionDetector._subject_terms(context.previous_text)
            )
        previous_subjects.update(
            DomainScopeCorrectionDetector._subject_terms(
                " ".join(context.previous_entities)
            )
        )
        if (
            context.previous_result is not None
            and context.previous_result.source_sense2 is not None
        ):
            previous_subjects.update(
                DomainScopeCorrectionDetector._subject_terms(
                    " ".join(context.previous_result.source_sense2.task.subject)
                )
            )
        current_subjects = DomainScopeCorrectionDetector._subject_terms(current_text)
        if previous_subjects and current_subjects:
            return bool(previous_subjects.intersection(current_subjects))
        return bool(_REFERENCE.search(current_text))

    @staticmethod
    def _subject_terms(text):
        return {
            word.casefold()
            for word in _WORD.findall(text)
            if word.casefold() not in _SUBJECT_STOP_WORDS and not word.isdigit()
        }

    @staticmethod
    def _scopes(result, exclude_inherited=False):
        if result.scope_classification is None:
            return ()
        scopes = tuple(
            dict.fromkeys(
                (
                    result.scope_classification.primary_scope,
                    *result.scope_classification.secondary_scopes,
                )
            )
        )
        if exclude_inherited and result.scope_detection is not None:
            current_evidence = {
                item.scope_type
                for item in result.scope_detection.evidence
                if item.provenance == EvidenceProvenance.SOURCE_TEXT
            }
            return tuple(item for item in scopes if item in current_evidence)
        return scopes

    @classmethod
    def _preserved_domains(
        cls, previous, previous_evidence, correction_text, current, physical, removed
    ):
        current_set = set(current)
        target_terms = cls._subject_terms(correction_text)
        remove_financial = physical and bool(
            _FINANCIAL_MARKER.search(
                " ".join(item.evidence for item in previous_evidence)
            )
        )
        preserved = []
        for domain in previous:
            if domain in current_set:
                continue
            supporting = [
                item
                for item in previous_evidence
                if item.domain == domain
                and item.provenance
                in {
                    EvidenceProvenance.SOURCE_TEXT,
                    EvidenceProvenance.HISTORICAL,
                }
            ]
            if (
                removed
                and supporting
                and all(
                    cls._evidence_terms(item.evidence).intersection(removed)
                    for item in supporting
                )
            ):
                continue
            if remove_financial and domain in {DomainType.MARKETS, DomainType.TRADING}:
                if any(
                    cls._subject_terms(item.evidence).intersection(target_terms)
                    for item in supporting
                ):
                    continue
            preserved.append(domain)
        return tuple(preserved)

    @classmethod
    def _preserved_scopes(
        cls, previous, current, physical, financial, previous_evidence, removed_terms
    ):
        current_set = set(current)
        removed_scopes = set()
        if physical and financial is False:
            removed_scopes.add(ScopeType.FINANCIAL_MARKET)
        elif financial and not physical:
            removed_scopes.add(ScopeType.PHYSICAL_COMMERCE)
        preserved = []
        for scope in previous:
            if scope in current_set:
                preserved.append(scope)
                continue
            supporting = [
                item
                for item in previous_evidence
                if item.scope_type == scope
                and item.provenance
                in {
                    EvidenceProvenance.SOURCE_TEXT,
                    EvidenceProvenance.HISTORICAL,
                }
            ]
            if (
                removed_terms
                and supporting
                and all(
                    cls._evidence_terms(item.evidence).intersection(removed_terms)
                    for item in supporting
                )
            ):
                continue
            if scope not in removed_scopes or scope in current_set:
                preserved.append(scope)
        return tuple(preserved)

    @staticmethod
    def _evidence_terms(text):
        return {word.casefold() for word in _WORD.findall(text) if not word.isdigit()}

    @staticmethod
    def _removed_terms(text):
        terms = set()
        for pattern in (_REMOVAL_TARGET, _NEGATED_TARGET):
            for match in pattern.finditer(text):
                terms.update(
                    word.casefold()
                    for word in _WORD.findall(match.group("target"))
                    if not word.isdigit()
                )
        return terms

    @staticmethod
    def _change_type(previous, current, *, domain):
        old = set(previous)
        new = set(current)
        if old and new and new < old:
            return (
                CorrectionType.DOMAIN_REPLACEMENT
                if domain
                else CorrectionType.SCOPE_REPLACEMENT
            )
        if old and new and old < new:
            return (
                CorrectionType.DOMAIN_ADDITION
                if domain
                else CorrectionType.SCOPE_ADDITION
            )
        return (
            CorrectionType.DOMAIN_REFINEMENT
            if domain
            else CorrectionType.SCOPE_REFINEMENT
        )

    @staticmethod
    def _values(values):
        return ", ".join(item.value for item in values)

    @staticmethod
    def _correction_confidence(domain_evidence, scope_evidence):
        evidence = (*domain_evidence, *scope_evidence)
        if any(item.confidence == DomainConfidence.HIGH for item in evidence):
            return DomainConfidence.HIGH
        if any(item.confidence == DomainConfidence.MEDIUM for item in evidence):
            return DomainConfidence.MEDIUM
        if evidence:
            return DomainConfidence.LOW
        return DomainConfidence.UNKNOWN

    @staticmethod
    def _evidence_confidence(evidence):
        if not evidence:
            return DomainConfidence.UNKNOWN
        return max(
            (item.confidence for item in evidence),
            key=lambda item: {
                DomainConfidence.UNKNOWN: 0,
                DomainConfidence.LOW: 1,
                DomainConfidence.MEDIUM: 2,
                DomainConfidence.HIGH: 3,
                DomainConfidence.CONFLICTING: -1,
            }[item],
        )

    @staticmethod
    def _history(previous):
        correction = previous.correction
        if correction is None or not correction.detected:
            return ()
        if correction.history:
            return tuple(
                replace(
                    entry,
                    previous_domain_evidence=tuple(
                        DomainScopeCorrectionDetector._historical_evidence(item)
                        for item in entry.previous_domain_evidence
                    ),
                    updated_domain_evidence=tuple(
                        DomainScopeCorrectionDetector._historical_evidence(item)
                        for item in entry.updated_domain_evidence
                    ),
                    previous_scope_evidence=tuple(
                        DomainScopeCorrectionDetector._historical_evidence(item)
                        for item in entry.previous_scope_evidence
                    ),
                    updated_scope_evidence=tuple(
                        DomainScopeCorrectionDetector._historical_evidence(item)
                        for item in entry.updated_scope_evidence
                    ),
                    evidence_provenance=EvidenceProvenance.HISTORICAL,
                )
                for entry in correction.history
            )
        entry = CorrectionHistoryEntry(
            correction_type=correction.correction_type,
            updates=correction.updates,
            previous_domains=correction.previous_domains,
            updated_domains=correction.updated_domains,
            previous_scopes=correction.previous_scopes,
            updated_scopes=correction.updated_scopes,
            previous_domain_evidence=correction.previous_domain_evidence,
            updated_domain_evidence=correction.updated_domain_evidence,
            previous_scope_evidence=correction.previous_scope_evidence,
            updated_scope_evidence=correction.updated_scope_evidence,
            previous_scope_subjects=correction.previous_scope_subjects,
            updated_scope_subjects=correction.updated_scope_subjects,
            evidence=correction.evidence,
            confidence=correction.confidence,
            evidence_provenance=EvidenceProvenance.HISTORICAL,
        )
        return (*correction.history, entry)

    @staticmethod
    def _historical_evidence(item):
        if item.provenance == EvidenceProvenance.INTERNAL_TAXONOMY:
            return item
        return replace(item, provenance=EvidenceProvenance.HISTORICAL)

    @staticmethod
    def _preserved_context(previous, changes_domains, changes_scopes, domains, scopes):
        preserved = []
        if not changes_domains and previous.classification.domains:
            preserved.append("domains")
        if not changes_scopes and scopes:
            preserved.append("scopes")
        else:
            preserved.extend(item.value for item in scopes)
        if previous.source_sense2 is not None:
            preserved.append("sense2_context")
        if previous.source_input is not None:
            preserved.append("sense1_context")
        return tuple(dict.fromkeys(preserved))
