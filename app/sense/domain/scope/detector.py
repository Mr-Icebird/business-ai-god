import re

from app.sense.domain.evidence import has_correction_marker, is_negated_source_span
from app.sense.domain.models import DomainConfidence, DomainType
from app.sense.domain.scope.knowledge import _GEOGRAPHIC, _SCOPE_CUES
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeDetection,
    ScopeEvidence,
    ScopeLevel,
    ScopeType,
)

_KNOWN_COMPANIES = {"apple", "microsoft", "amazon", "google", "dangote", "tesla"}
_COMPANY_CONTEXT = re.compile(
    r"\b(?:company|companies|business|operation|operations|stock|shares?|revenue|profit|"
    r"corporate|earnings|manufactur\w*|products?|industr(?:y|ies)|sector)\b",
    re.IGNORECASE,
)
_REFERENCE = re.compile(r"\b(?:it|its|they|them|that|those|this|such)\b", re.I)
_SCOPE_SEGMENT_SEPARATOR = re.compile(
    r",|\b(?:and|or|with|versus|vs\.?|but|however|whereas|while|although|though|yet|on|"
    r"affect\w*|impact\w*|influenc\w*|cause\w*|increase\w*|reduce\w*|"
    r"drive\w*|because|due to|effect of|effect on)\b",
    re.I,
)
_REQUEST_PREFIX = re.compile(
    r"^\s*(?:(?:i mean|i meant|actually|focus only)\s+)?"
    r"(?:(?:please\s+)?(?:analy[sz]e|compare|research|investigate|"
    r"explain|check|review|study|look into)\s+)?",
    re.I,
)
_GENERIC_ASSET_MARKET = re.compile(
    r"^(?:gold|oil|commodity|forex)\s+markets?$",
    re.I,
)


class ScopeDetector:
    def detect(
        self,
        text: str,
        *,
        domain_result=None,
        source_input=None,
        sense2_result=None,
        context=None,
    ) -> ScopeDetection:
        evidence = []
        for scope_type, pattern, confidence in _SCOPE_CUES:
            for match in pattern.finditer(text):
                if is_negated_source_span(text, match.span()):
                    continue
                if (
                    scope_type == ScopeType.FINANCIAL_MARKET
                    and _GENERIC_ASSET_MARKET.fullmatch(match.group())
                    and not re.search(
                        r"\bcompare\s+gold\s+and\s+oil\s+markets?\b", text, re.I
                    )
                ):
                    continue
                if (
                    scope_type == ScopeType.PHYSICAL_COMMERCE
                    and match.group().casefold() == "produce"
                    and not ScopeDetector._is_produce_verb(text, match)
                ):
                    continue
                if (
                    scope_type == ScopeType.COMPANY
                    and match.group().casefold() in _KNOWN_COMPANIES
                    and not self._company_context(text, match, sense2_result)
                ):
                    continue
                subject = self._subject_for_match(
                    text, match, scope_type, sense2_result
                )
                evidence.append(
                    ScopeEvidence(
                        scope_type=scope_type,
                        evidence=match.group(),
                        source="explicit_scope_cue",
                        confidence=confidence,
                        subject=subject,
                        level=(
                            ScopeLevel.INDIVIDUAL_EVENT
                            if scope_type == ScopeType.FINANCIAL_MARKET
                            and match.group().casefold()
                            in {
                                "earnings",
                                "announcement",
                                "earnings release",
                                "market crash",
                                "oil crash",
                            }
                            else self._level(scope_type, subject)
                        ),
                        source_span=match.span(),
                        source_text=text,
                    )
                )

        for pattern, level in _GEOGRAPHIC:
            for match in pattern.finditer(text):
                if is_negated_source_span(text, match.span()):
                    continue
                evidence.append(
                    ScopeEvidence(
                        scope_type=ScopeType.GEOGRAPHIC,
                        evidence=match.group(),
                        source="geographic_boundary",
                        confidence=DomainConfidence.HIGH,
                        subject=match.group(),
                        level=level,
                        source_span=match.span(),
                        source_text=text,
                    )
                )

        evidence.extend(
            self._upstream_evidence(
                text, domain_result, source_input, sense2_result, context
            )
        )
        unique = []
        seen = set()
        has_reference = bool(_REFERENCE.search(text))
        for item in evidence:
            key = (
                item.scope_type,
                item.subject.casefold() if item.subject else None,
                item.evidence.casefold(),
                item.source_span,
                item.provenance,
                item.source_text,
            )
            if (
                has_reference
                and item.source == "previous_scope_context"
                and key in seen
            ):
                continue
            if key not in seen:
                unique.append(item)
                seen.add(key)
        return ScopeDetection(tuple(unique))

    @staticmethod
    def _is_produce_verb(text, match):
        prefix = text[max(0, match.start() - 48) : match.start()]
        return bool(
            re.search(
                r"\b(?:do|does|did|will|can|to)\s+(?:[a-z'-]+\s+){0,3}$",
                prefix,
                re.I,
            )
        )

    @staticmethod
    def _company_context(text, match, sense2_result):
        head = text[max(0, match.start() - 48) : match.start()]
        tail = text[match.end() : match.end() + 48]
        if _COMPANY_CONTEXT.search(head + " " + tail):
            return True
        if re.search(
            r"\b(?:analy[sz]e|research|compare|check|how is|what about)\s+$",
            head,
            re.IGNORECASE,
        ):
            return bool(match.group()[:1].isupper())
        if sense2_result is not None:
            subjects = {item.casefold() for item in sense2_result.task.subject}
            return match.group().casefold() in subjects and bool(
                sense2_result.task.operation
            )
        return False

    @staticmethod
    def _subject_for_match(text, match, scope_type, sense2_result):
        if scope_type in {
            ScopeType.COMPANY,
            ScopeType.ASSET,
            ScopeType.INDUSTRY,
            ScopeType.COMMERCIAL_MARKET,
        }:
            return match.group()
        if scope_type == ScopeType.OPERATIONAL:
            for subject_match in re.finditer(
                r"\b[A-Z][A-Za-z0-9&.-]*'s\s+(?:business\s+)?operations?\b",
                text,
            ):
                if (
                    subject_match.start() <= match.start()
                    and match.end() <= subject_match.end()
                ):
                    return subject_match.group()
        if scope_type in {
            ScopeType.FINANCIAL_MARKET,
            ScopeType.OPERATIONAL,
            ScopeType.BUSINESS,
        }:
            preceding = tuple(_SCOPE_SEGMENT_SEPARATOR.finditer(text, 0, match.start()))
            segment_start = preceding[-1].end() if preceding else 0
            following = _SCOPE_SEGMENT_SEPARATOR.search(text, match.end())
            segment_end = following.start() if following else len(text)
            segment = _REQUEST_PREFIX.sub(
                "", text[segment_start:segment_end].strip(" .!?")
            )
            has_named_company = bool(
                re.search(
                    r"\b(?:Apple|Microsoft|Amazon|Google|Dangote|Tesla)'s?\b",
                    segment,
                    re.I,
                )
            )
            has_geography = any(pattern.search(segment) for pattern, _ in _GEOGRAPHIC)
            if segment and (
                scope_type == ScopeType.FINANCIAL_MARKET
                or has_named_company
                or has_geography
            ):
                return segment.strip()
            return None
        if sense2_result is not None:
            subjects = sense2_result.task.subject
            for subject in subjects:
                for subject_match in re.finditer(
                    re.escape(subject), text, re.IGNORECASE
                ):
                    if (
                        subject_match.start() <= match.start()
                        and match.end() <= subject_match.end()
                    ):
                        return subject
        return None

    @staticmethod
    def _level(scope_type, subject):
        if scope_type == ScopeType.COMPANY:
            return ScopeLevel.COMPANY
        if scope_type == ScopeType.INDUSTRY:
            return ScopeLevel.INDUSTRY
        if scope_type in {
            ScopeType.FINANCIAL_MARKET,
            ScopeType.COMMERCIAL_MARKET,
        }:
            return ScopeLevel.MARKET
        if scope_type == ScopeType.ASSET:
            return (
                ScopeLevel.TRANSACTION
                if subject and "future" in subject.casefold()
                else ScopeLevel.ASSET
            )
        if scope_type == ScopeType.STRATEGIC and subject:
            return ScopeLevel.COMPANY
        return None

    @staticmethod
    def _upstream_evidence(text, domain_result, source_input, sense2_result, context):
        evidence = []
        if domain_result is not None:
            domains = set(domain_result.classification.domains)
            if domains.intersection(
                {DomainType.FOREX, DomainType.EQUITIES, DomainType.BONDS}
            ):
                evidence.append(
                    ScopeEvidence(
                        ScopeType.FINANCIAL_MARKET,
                        ", ".join(item.value for item in domains),
                        "sense3_domain_context",
                        DomainConfidence.MEDIUM,
                        level=ScopeLevel.MARKET,
                        provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                    )
                )
            if DomainType.COMMODITIES in domains:
                evidence.append(
                    ScopeEvidence(
                        ScopeType.ASSET,
                        "commodity domain",
                        "sense3_domain_context",
                        DomainConfidence.LOW,
                        level=ScopeLevel.ASSET,
                        provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                    )
                )
            if domains.intersection({DomainType.BUSINESS, DomainType.OPERATIONS}):
                evidence.append(
                    ScopeEvidence(
                        ScopeType.BUSINESS,
                        "business domain",
                        "sense3_domain_context",
                        DomainConfidence.LOW,
                        provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                    )
                )
        if (
            sense2_result is not None
            and sense2_result.action.primary.value == "execute"
        ):
            evidence.append(
                ScopeEvidence(
                    ScopeType.FINANCIAL_MARKET,
                    "execute action",
                    "sense2_action",
                    DomainConfidence.MEDIUM,
                    level=ScopeLevel.MARKET,
                    provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                )
            )
        if source_input is not None and source_input.input_type.value == "market_data":
            evidence.append(
                ScopeEvidence(
                    ScopeType.FINANCIAL_MARKET,
                    source_input.input_type.value,
                    "sense1_input_type",
                    DomainConfidence.HIGH,
                    level=ScopeLevel.MARKET,
                    provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                )
            )
        if (
            context is not None
            and context.previous_result is not None
            and _REFERENCE.search(text)
            and not has_correction_marker(text)
        ):
            previous = context.previous_result
            if previous.scope_detection is not None:
                for item in previous.scope_detection.evidence:
                    evidence.append(
                        ScopeEvidence(
                            item.scope_type,
                            item.evidence,
                            "previous_scope_context",
                            DomainConfidence.MEDIUM,
                            item.subject,
                            item.level,
                            item.source_span,
                            EvidenceProvenance.UPSTREAM_CONTEXT,
                            item.source_text,
                        )
                    )
        return evidence
