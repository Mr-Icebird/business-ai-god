import re

from app.sense.domain.classification.models import DomainClassification
from app.sense.domain.detection.models import DomainDetection
from app.sense.domain.hierarchy.knowledge import PARENT_BY_DOMAIN
from app.sense.domain.models import DomainConfidence
from app.sense.domain.scope.models import EvidenceProvenance
from app.sense.domain.multi_domain.models import (
    DomainInteraction,
    DomainRelationship,
    DomainRelationshipType,
    MultiDomainResult,
)

_INTERACTION = re.compile(
    r"\b(?:affect\w*|impact\w*|influenc\w*|drive\w*|increase\w*|"
    r"reduce\w*|cause\w*|compare\w*|versus|vs\.?|because of|due to|"
    r"relates? to|effect on)\b",
    re.IGNORECASE,
)
_CLAUSE_CONTRAST = re.compile(
    r"\b(?:but|however|whereas|while|although|though|yet)\b", re.IGNORECASE
)


class MultiDomainDetector:
    def detect(
        self,
        text: str,
        classification: DomainClassification,
        detection: DomainDetection,
    ) -> MultiDomainResult:
        domains = classification.domains
        relationships = []
        linked_pairs = {}
        interactions = []
        for match in _INTERACTION.finditer(text):
            left, right = self._relation_sides(text, match, detection)
            if not left or not right:
                continue
            source, target = left[0], right[0]
            relation_span = (
                min(source.source_span[0], target.source_span[0]),
                max(source.source_span[1], target.source_span[1]),
            )
            relation_evidence = text[slice(*relation_span)]
            if source.domain == target.domain:
                continue
            linked_domains = (source.domain, target.domain)
            interactions.append(
                DomainInteraction(
                    domains=linked_domains,
                    interaction=match.group().casefold(),
                    evidence=relation_evidence,
                    confidence=DomainConfidence.MEDIUM,
                    source_subject=source.evidence,
                    target_subject=target.evidence,
                    source_span=relation_span,
                    source_text=text,
                )
            )
            linked_pairs[(source.domain, target.domain)] = (
                match.group().casefold(),
                relation_evidence,
                source.evidence,
                target.evidence,
                relation_span,
            )

        for index, source in enumerate(domains):
            for target in domains[index + 1 :]:
                if PARENT_BY_DOMAIN.get(target) == source:
                    relationships.append(
                        DomainRelationship(
                            source,
                            target,
                            DomainRelationshipType.HIERARCHICAL,
                            evidence="configured domain hierarchy",
                            confidence=DomainConfidence.HIGH,
                            provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                        )
                    )
                elif PARENT_BY_DOMAIN.get(source) == target:
                    relationships.append(
                        DomainRelationship(
                            target,
                            source,
                            DomainRelationshipType.HIERARCHICAL,
                            evidence="configured domain hierarchy",
                            confidence=DomainConfidence.HIGH,
                            provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                        )
                    )
                elif (source, target) in linked_pairs:
                    relation, evidence, source_subject, target_subject, span = (
                        linked_pairs[(source, target)]
                    )
                    relationships.append(
                        DomainRelationship(
                            source,
                            target,
                            DomainRelationshipType.INTERACTS_WITH,
                            evidence=evidence,
                            confidence=DomainConfidence.MEDIUM,
                            source_subject=source_subject,
                            target_subject=target_subject,
                            source_span=span,
                            source_text=text,
                        )
                    )
                elif (target, source) in linked_pairs:
                    relation, evidence, source_subject, target_subject, span = (
                        linked_pairs[(target, source)]
                    )
                    relationships.append(
                        DomainRelationship(
                            target,
                            source,
                            DomainRelationshipType.INTERACTS_WITH,
                            evidence=evidence,
                            confidence=DomainConfidence.MEDIUM,
                            source_subject=source_subject,
                            target_subject=target_subject,
                            source_span=span,
                            source_text=text,
                        )
                    )

        return MultiDomainResult(
            primary_domain=classification.primary_domain,
            secondary_domains=classification.secondary_domains,
            domains=domains,
            relationships=tuple(relationships),
            interactions=tuple(interactions),
            confidence=classification.confidence,
            is_ambiguous=(
                detection.is_ambiguous
                and not interactions
                or any(
                    signal.source.startswith("ambiguous_")
                    for signal in detection.signals
                )
            ),
            candidate_domains=tuple(item.domain for item in detection.candidates),
        )

    @staticmethod
    def _relation_sides(text, match, detection):
        boundaries_before = [
            text.rfind(delimiter, 0, match.start())
            for delimiter in (".", ";", "!", "?", "\n")
        ]
        start = max(boundaries_before, default=-1) + 1
        start = max(
            start,
            max(
                (
                    item.end()
                    for item in _CLAUSE_CONTRAST.finditer(text, 0, match.start())
                ),
                default=start,
            ),
        )
        boundaries_after = [
            position
            for delimiter in (".", ";", "!", "?", "\n")
            if (position := text.find(delimiter, match.end())) >= 0
        ]
        end = min(boundaries_after, default=len(text))
        after_contrast = [
            item.start() for item in _CLAUSE_CONTRAST.finditer(text, match.end())
        ]
        if after_contrast:
            end = min(end, min(after_contrast))
        left_candidates = tuple(
            item
            for item in detection.signals
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
            and item.source_span
            and start < item.source_span[1] <= match.start()
        )
        right_candidates = tuple(
            item
            for item in detection.signals
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
            and item.source_span
            and match.end() <= item.source_span[0] < end
        )
        if not left_candidates or not right_candidates:
            return (), ()
        closest_left = max(item.source_span[1] for item in left_candidates)
        closest_right = min(item.source_span[0] for item in right_candidates)
        left = sorted(
            (item for item in left_candidates if item.source_span[1] == closest_left),
            key=MultiDomainDetector._signal_priority,
            reverse=True,
        )
        right = sorted(
            (item for item in right_candidates if item.source_span[0] == closest_right),
            key=MultiDomainDetector._signal_priority,
            reverse=True,
        )
        return (left[0],), (right[0],)

    @staticmethod
    def _signal_priority(signal):
        rank = {
            DomainConfidence.UNKNOWN: 0,
            DomainConfidence.LOW: 1,
            DomainConfidence.MEDIUM: 2,
            DomainConfidence.HIGH: 3,
            DomainConfidence.CONFLICTING: -1,
        }
        span_length = signal.source_span[1] - signal.source_span[0]
        return rank[signal.confidence], span_length
