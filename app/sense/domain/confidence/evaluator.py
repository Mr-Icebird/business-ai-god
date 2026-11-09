from app.sense.domain.ambiguity.models import AmbiguityType, DomainScopeAmbiguity
from app.sense.domain.confidence.models import DomainScopeConfidence
from app.sense.domain.correction.models import DomainScopeCorrection
from app.sense.domain.models import DomainConfidence, DomainUnderstandingResult

_RANK = {
    DomainConfidence.UNKNOWN: 0,
    DomainConfidence.LOW: 1,
    DomainConfidence.MEDIUM: 2,
    DomainConfidence.HIGH: 3,
    DomainConfidence.CONFLICTING: -1,
}
_DOMAIN_STRONG_SOURCES = {
    "asset_price_movement",
    "company_equity_context",
    "economic_effect",
    "market_futures_task",
    "market_instrument_task",
    "sense1_abbreviation",
    "sense1_input_type",
}
_INHERITED_DOMAIN_SOURCES = {
    "previous_domain_context",
    "previous_upstream_context",
}
_INHERITED_SCOPE_SOURCES = {
    "previous_scope_context",
    "sense3_domain_context",
}
_DOMAIN_AMBIGUITIES = {
    AmbiguityType.DOMAIN_AMBIGUOUS,
    AmbiguityType.DOMAIN_AND_SCOPE_AMBIGUOUS,
    AmbiguityType.DOMAIN_CONFLICT,
    AmbiguityType.INSUFFICIENT_CONTEXT,
    AmbiguityType.MULTI_DOMAIN_UNCLEAR,
}
_SCOPE_AMBIGUITIES = {
    AmbiguityType.SCOPE_AMBIGUOUS,
    AmbiguityType.DOMAIN_AND_SCOPE_AMBIGUOUS,
    AmbiguityType.INSUFFICIENT_CONTEXT,
    AmbiguityType.MULTI_SCOPE_UNCLEAR,
    AmbiguityType.SCOPE_CONFLICT,
}


class DomainScopeConfidenceEvaluator:
    def evaluate(
        self,
        result: DomainUnderstandingResult,
        ambiguity: DomainScopeAmbiguity,
        correction: DomainScopeCorrection | None = None,
    ) -> DomainScopeConfidence:
        domain_evidence = tuple(result.detection.signals)
        scope_evidence = (
            tuple(result.scope_detection.evidence)
            if result.scope_detection is not None
            else ()
        )
        correction_fields = (
            {item.field_name for item in correction.updates}
            if correction is not None and correction.detected
            else set()
        )

        if correction is not None and correction.detected:
            if "domains" not in correction_fields:
                domain = correction.previous_domain_confidence
                domain_evidence = correction.previous_domain_evidence
            else:
                domain = self._domain_confidence(domain_evidence, ambiguity)
            if "scopes" not in correction_fields:
                scope = correction.previous_scope_confidence
                scope_evidence = correction.previous_scope_evidence
            else:
                scope = self._scope_confidence(scope_evidence, ambiguity)
        else:
            domain = self._domain_confidence(domain_evidence, ambiguity)
            scope = self._scope_confidence(scope_evidence, ambiguity)

        overall = self._overall(domain, scope)
        return DomainScopeConfidence(
            domain=domain,
            scope=scope,
            overall=overall,
            domain_reasons=self._reasons("domain", domain, domain_evidence),
            scope_reasons=self._reasons("scope", scope, scope_evidence),
            overall_reasons=(
                "Overall confidence is limited by the weaker independent assessment.",
            ),
            domain_evidence=domain_evidence,
            scope_evidence=scope_evidence,
        )

    @classmethod
    def _domain_confidence(cls, evidence, ambiguity) -> DomainConfidence:
        if ambiguity.ambiguity_type == AmbiguityType.DOMAIN_CONFLICT or (
            ambiguity.conflicting_domains
        ):
            return DomainConfidence.CONFLICTING
        if not evidence:
            return DomainConfidence.UNKNOWN
        if any(item.confidence == DomainConfidence.CONFLICTING for item in evidence):
            return DomainConfidence.CONFLICTING
        if ambiguity.ambiguity_type in _DOMAIN_AMBIGUITIES:
            return DomainConfidence.LOW

        direct = tuple(
            item for item in evidence if item.source not in _INHERITED_DOMAIN_SOURCES
        )
        assessed = direct or evidence
        strongest = max((item.confidence for item in assessed), key=_RANK.__getitem__)
        if strongest == DomainConfidence.UNKNOWN:
            return DomainConfidence.UNKNOWN
        if strongest == DomainConfidence.LOW:
            return DomainConfidence.LOW
        if not direct:
            return DomainConfidence.MEDIUM
        if strongest == DomainConfidence.HIGH and any(
            item.source in _DOMAIN_STRONG_SOURCES for item in direct
        ):
            return DomainConfidence.HIGH
        return DomainConfidence.MEDIUM

    @classmethod
    def _scope_confidence(cls, evidence, ambiguity) -> DomainConfidence:
        if ambiguity.ambiguity_type == AmbiguityType.SCOPE_CONFLICT or (
            ambiguity.conflicting_scopes
        ):
            return DomainConfidence.CONFLICTING
        if not evidence:
            return DomainConfidence.UNKNOWN
        if any(item.confidence == DomainConfidence.CONFLICTING for item in evidence):
            return DomainConfidence.CONFLICTING
        if ambiguity.ambiguity_type in _SCOPE_AMBIGUITIES:
            return DomainConfidence.LOW

        direct = tuple(
            item for item in evidence if item.source not in _INHERITED_SCOPE_SOURCES
        )
        assessed = direct or evidence
        strongest = max((item.confidence for item in assessed), key=_RANK.__getitem__)
        if strongest in {DomainConfidence.UNKNOWN, DomainConfidence.LOW}:
            return strongest
        if not direct:
            return DomainConfidence.MEDIUM
        return strongest

    @staticmethod
    def _overall(domain: DomainConfidence, scope: DomainConfidence) -> DomainConfidence:
        if DomainConfidence.CONFLICTING in {domain, scope}:
            return DomainConfidence.CONFLICTING
        if DomainConfidence.UNKNOWN in {domain, scope}:
            return DomainConfidence.UNKNOWN
        if DomainConfidence.LOW in {domain, scope}:
            return DomainConfidence.LOW
        if DomainConfidence.MEDIUM in {domain, scope}:
            return DomainConfidence.MEDIUM
        return DomainConfidence.HIGH

    @staticmethod
    def _reasons(kind, confidence, evidence):
        labels = {
            DomainConfidence.HIGH: "strong",
            DomainConfidence.MEDIUM: "moderate",
            DomainConfidence.LOW: "weak or ambiguous",
            DomainConfidence.UNKNOWN: "insufficient",
            DomainConfidence.CONFLICTING: "conflicting",
        }
        if not evidence:
            return (f"{kind.capitalize()} evidence is insufficient.",)
        sources = tuple(dict.fromkeys(item.source for item in evidence))
        return (
            f"{kind.capitalize()} evidence is {labels[confidence]}.",
            *(f"{kind.capitalize()} evidence source: {source}." for source in sources),
        )
