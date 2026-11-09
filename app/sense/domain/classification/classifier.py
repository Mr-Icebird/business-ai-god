from app.sense.domain.classification.models import DomainClassification
from app.sense.domain.detection.models import DomainDetection
from app.sense.domain.hierarchy.resolver import DomainHierarchyResolver
from app.sense.domain.models import DomainConfidence, DomainType

_RANK = {
    DomainConfidence.UNKNOWN: 0,
    DomainConfidence.LOW: 1,
    DomainConfidence.MEDIUM: 2,
    DomainConfidence.HIGH: 3,
    DomainConfidence.CONFLICTING: -1,
}
_PREFERRED_PARENT = {
    DomainType.FOREX: DomainType.MARKETS,
    DomainType.EQUITIES: DomainType.MARKETS,
    DomainType.BONDS: DomainType.MARKETS,
    DomainType.CRYPTO: DomainType.MARKETS,
    DomainType.BANKING: DomainType.FINANCE,
    DomainType.INVESTMENT: DomainType.FINANCE,
    DomainType.MACROECONOMICS: DomainType.ECONOMICS,
    DomainType.MICROECONOMICS: DomainType.ECONOMICS,
    DomainType.OPERATIONS: DomainType.BUSINESS,
    DomainType.MARKETING: DomainType.BUSINESS,
    DomainType.SALES: DomainType.BUSINESS,
    DomainType.SUPPLY_CHAIN: DomainType.BUSINESS,
    DomainType.ENERGY: DomainType.COMMODITIES,
}


class DomainClassifier:
    def classify(self, detection: DomainDetection) -> DomainClassification:
        if not detection.candidates:
            return DomainClassification()
        candidates = {item.domain: item for item in detection.candidates}
        if (
            detection.is_ambiguous
            and _RANK[detection.candidates[0].confidence]
            <= _RANK[DomainConfidence.MEDIUM]
        ):
            return DomainClassification(
                confidence=DomainConfidence.LOW,
                candidate_domains=tuple(item.domain for item in detection.candidates),
                primary_reason="The available evidence does not justify selecting one domain.",
            )
        primary = detection.candidates[0].domain
        parent = _PREFERRED_PARENT.get(primary)
        if (
            parent in candidates
            and _RANK[candidates[parent].confidence]
            >= _RANK[candidates[primary].confidence]
        ):
            primary = parent

        primary_candidate = candidates.get(
            primary, candidates[detection.candidates[0].domain]
        )
        subdomains = tuple(
            candidate.domain
            for candidate in detection.candidates
            if primary in DomainHierarchyResolver.ancestors(candidate.domain)
        )
        subdomain_set = set(subdomains)
        secondary = tuple(
            candidate.domain
            for candidate in detection.candidates
            if candidate.domain != primary
            and candidate.domain not in subdomain_set
            and primary not in DomainHierarchyResolver.ancestors(candidate.domain)
        )
        confidence = primary_candidate.confidence
        if detection.is_ambiguous and confidence in {
            DomainConfidence.HIGH,
            DomainConfidence.MEDIUM,
        }:
            confidence = DomainConfidence.LOW
        return DomainClassification(
            primary_domain=primary,
            secondary_domains=secondary,
            subdomains=subdomains,
            domains=tuple(dict.fromkeys((primary,) + subdomains + secondary)),
            candidate_domains=tuple(item.domain for item in detection.candidates),
            confidence=confidence,
            primary_reason=self._reason(
                primary_candidate.signals[0].source
                if primary_candidate.signals
                else None
            ),
        )

    @staticmethod
    def _reason(source: str | None) -> str | None:
        if source is None:
            return None
        return {
            "sense2_user_goal": "SENSE-2 user goal supports this domain.",
            "sense2_action": "The requested action provides domain evidence.",
            "sense1_input_type": "SENSE-1 identified market-data input.",
            "sense1_currency": "SENSE-1 detected currency information.",
        }.get(source, f"Domain evidence: {source.replace('_', ' ')}.")
