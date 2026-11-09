import re

from app.sense.domain.detection.knowledge import DOMAIN_CUES
from app.sense.domain.detection.models import (
    DomainCandidate,
    DomainDetection,
    DomainSignal,
)
from app.sense.domain.evidence import has_correction_marker, is_negated_source_span
from app.sense.domain.models import (
    DomainConfidence,
    DomainContext,
    DomainType,
    EvidenceProvenance,
)

_CONFIDENCE_RANK = {
    DomainConfidence.UNKNOWN: 0,
    DomainConfidence.LOW: 1,
    DomainConfidence.MEDIUM: 2,
    DomainConfidence.HIGH: 3,
    DomainConfidence.CONFLICTING: -1,
}
_OPERATION_DOMAINS = {
    "trading_research": (DomainType.TRADING, DomainType.INVESTMENT, DomainType.FINANCE),
    "investment_research": (DomainType.INVESTMENT, DomainType.FINANCE),
    "business_research": (DomainType.BUSINESS,),
}


class DomainDetector:
    def detect(
        self,
        text: str,
        *,
        source_input=None,
        sense2_result=None,
        context: DomainContext | None = None,
    ) -> DomainDetection:
        normalized = " ".join(text.split())
        signals: list[DomainSignal] = []
        for cue in DOMAIN_CUES:
            for match in re.finditer(cue.pattern, normalized, re.IGNORECASE):
                if is_negated_source_span(normalized, match.span()):
                    continue
                if cue.cue_kind == "ambiguous_bank_mention" and re.search(
                    r"\b(?:river|stream|shore|edge)\s+bank\b|\bbank\s+of\s+(?:the\s+)?river\b",
                    normalized,
                    re.IGNORECASE,
                ):
                    continue
                signals.append(
                    DomainSignal(
                        domain=cue.domain,
                        evidence=match.group(),
                        source=cue.cue_kind,
                        confidence=cue.confidence,
                        explicit=cue.confidence == DomainConfidence.HIGH,
                        source_span=match.span(),
                        source_text=normalized,
                    )
                )

        signals = self._refine_ambiguous_signals(normalized, signals)
        signals.extend(
            self._structured_signals(source_input, sense2_result, context, normalized)
        )
        grouped: dict[DomainType, list[DomainSignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.domain, []).append(signal)
        candidates = [
            DomainCandidate(
                domain=domain,
                confidence=self._candidate_confidence(items),
                signals=tuple(items),
            )
            for domain, items in grouped.items()
        ]
        candidates.sort(
            key=lambda candidate: (
                -_CONFIDENCE_RANK[candidate.confidence],
                min(
                    (
                        item.source_span[0]
                        for item in candidate.signals
                        if item.source_span
                    ),
                    default=10**9,
                ),
                -sum(_CONFIDENCE_RANK[item.confidence] for item in candidate.signals),
                candidate.domain.value,
            )
        )

        isolated_ambiguity = bool(
            re.fullmatch(
                r"(?:tell me about )?(?:oil|apple|bank|market)[.!? ]*",
                normalized,
                re.IGNORECASE,
            )
        )
        top_tier = (
            [item for item in candidates if item.confidence == candidates[0].confidence]
            if candidates
            else []
        )
        weak_ambiguous_signal = any(
            item.source.startswith("ambiguous_") for item in signals
        )
        has_disambiguating_context = bool(
            re.search(
                r"\b(?:physical|futures?|inflation|airlines?|operating costs?|"
                r"transportation costs?|supply|production|stock|shares?|"
                r"company|business|fruit|orchard|harvest|crop)\b",
                normalized,
                re.IGNORECASE,
            )
        )
        ambiguous = (
            isolated_ambiguity
            or weak_ambiguous_signal
            and bool(candidates)
            and candidates[0].confidence != DomainConfidence.HIGH
            or (
                len(top_tier) > 1
                and top_tier[0].confidence
                in {DomainConfidence.LOW, DomainConfidence.MEDIUM}
                and not has_disambiguating_context
            )
        )
        return DomainDetection(
            candidates=tuple(candidates),
            signals=tuple(signals),
            is_ambiguous=ambiguous,
            ambiguity_reason=(
                "The message has multiple plausible domain interpretations."
                if ambiguous
                else None
            ),
        )

    @staticmethod
    def _candidate_confidence(signals: list[DomainSignal]) -> DomainConfidence:
        if any(item.confidence == DomainConfidence.HIGH for item in signals):
            return DomainConfidence.HIGH
        if any(item.confidence == DomainConfidence.MEDIUM for item in signals):
            return DomainConfidence.MEDIUM
        if signals:
            return DomainConfidence.LOW
        return DomainConfidence.UNKNOWN

    @staticmethod
    def _refine_ambiguous_signals(
        text: str, signals: list[DomainSignal]
    ) -> list[DomainSignal]:
        has_disambiguating_context = bool(
            re.search(
                r"\b(?:price|prices|supply|demand|production|energy|fuel|logistics|"
                r"company|companies|business|revenue|profit|shares?|stocks?|trading|"
                r"shipping|transport|fruit|orchard|harvest|crop|river|shore|loans?|deposits?)\b",
                text,
                re.IGNORECASE,
            )
        )
        if not has_disambiguating_context:
            return signals
        ambiguous_sources = {
            "ambiguous_brand_or_fruit",
            "ambiguous_brand_or_place",
            "ambiguous_bank_mention",
            "ambiguous_market_mention",
            "ambiguous_exchange_mention",
        }
        return [item for item in signals if item.source not in ambiguous_sources]

    @staticmethod
    def _structured_signals(
        source_input, sense2_result, context, text: str
    ) -> list[DomainSignal]:
        signals: list[DomainSignal] = []
        if source_input is not None:
            if source_input.input_type.value == "market_data":
                signals.append(
                    DomainSignal(
                        DomainType.MARKETS,
                        source_input.input_type.value,
                        "sense1_input_type",
                        DomainConfidence.HIGH,
                        True,
                        provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                        source_text=text,
                    )
                )
            if source_input.currencies:
                signals.append(
                    DomainSignal(
                        DomainType.FINANCE,
                        "currency mention",
                        "sense1_currency",
                        DomainConfidence.MEDIUM,
                        provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                        source_text=text,
                    )
                )
            abbreviation_text = " ".join(
                item.text for item in source_input.abbreviations
            )
            for pattern, domain in (
                (r"\b(?:XAU|XAG)\b", DomainType.COMMODITIES),
                (r"\b(?:BTC|ETH)\b", DomainType.CRYPTO),
                (r"\b(?:GDP|CPI|PMI)\b", DomainType.ECONOMICS),
            ):
                match = re.search(pattern, abbreviation_text, re.IGNORECASE)
                if match:
                    signals.append(
                        DomainSignal(
                            domain,
                            match.group(),
                            "sense1_abbreviation",
                            DomainConfidence.HIGH,
                            True,
                            provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                            source_text=text,
                        )
                    )

        if sense2_result is not None:
            goal = sense2_result.goal.primary.value
            for domain in _OPERATION_DOMAINS.get(goal, ()):
                signals.append(
                    DomainSignal(
                        domain,
                        goal,
                        "sense2_user_goal",
                        DomainConfidence.MEDIUM,
                        provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                        source_text=text,
                    )
                )
            if sense2_result.action.primary.value == "execute":
                signals.append(
                    DomainSignal(
                        DomainType.TRADING,
                        "execute action",
                        "sense2_action",
                        DomainConfidence.HIGH,
                        True,
                        provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                        source_text=text,
                    )
                )
            if sense2_result.task.subject:
                subject_text = " ".join(sense2_result.task.subject)
                if re.search(
                    r"\b(?:gold|silver|oil|crude|copper)\b", subject_text, re.IGNORECASE
                ):
                    subject_source_text = text
                    if not re.search(re.escape(subject_text), text, re.IGNORECASE):
                        subject_source_text = (
                            context.previous_text if context is not None else None
                        )
                    signals.append(
                        DomainSignal(
                            DomainType.COMMODITIES,
                            subject_text,
                            "sense2_task_subject",
                            DomainConfidence.MEDIUM,
                            provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                            source_text=subject_source_text,
                        )
                    )

        if context is not None:
            has_reference = bool(
                re.search(
                    r"\b(?:it|its|they|them|that|those|this)\b",
                    text,
                    re.IGNORECASE,
                )
            )
            if (
                has_reference
                and not has_correction_marker(text)
                and context.previous_result is not None
            ):
                for domain in context.previous_result.classification.domains:
                    signals.append(
                        DomainSignal(
                            domain,
                            context.previous_result.raw_text,
                            "previous_domain_context",
                            (
                                context.previous_result.classification.confidence
                                if domain == context.previous_result.primary_domain
                                else DomainConfidence.MEDIUM
                            ),
                            provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                            source_text=context.previous_result.normalized_text,
                        )
                    )
            elif has_reference and not has_correction_marker(text):
                prior_parts = list(context.previous_entities)
                if context.previous_sense2 is not None:
                    prior_parts.extend(context.previous_sense2.task.subject)
                    if context.previous_sense2.task.objective:
                        prior_parts.append(context.previous_sense2.task.objective)
                    prior_parts.append(context.previous_sense2.goal.primary.value)
                    prior_parts.append(context.previous_sense2.action.primary.value)
                if context.previous_input is not None:
                    prior_parts.append(context.previous_input.raw_input)
                if context.previous_text:
                    prior_parts.append(context.previous_text)
                context_confidence = (
                    DomainConfidence.HIGH
                    if context.previous_sense2 is not None
                    else DomainConfidence.MEDIUM
                )
                signals.extend(
                    DomainDetector._context_signals(
                        " ".join(prior_parts),
                        context_confidence,
                        source_text=context.previous_text,
                    )
                )
        return signals

    @staticmethod
    def _context_signals(
        text: str,
        confidence: DomainConfidence,
        *,
        source_text: str | None = None,
    ) -> list[DomainSignal]:
        signals = []
        for cue in DOMAIN_CUES:
            match = re.search(cue.pattern, text, re.IGNORECASE)
            if match:
                signals.append(
                    DomainSignal(
                        domain=cue.domain,
                        evidence=match.group(),
                        source="previous_upstream_context",
                        confidence=confidence,
                        explicit=False,
                        provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
                        source_text=source_text,
                    )
                )
        return signals
