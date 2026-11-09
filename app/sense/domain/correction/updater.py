import re
from dataclasses import replace

from app.sense.domain.correction.models import DomainScopeCorrection
from app.sense.domain.models import EvidenceProvenance
from app.sense.domain.scope.models import (
    ScopeBoundary,
    ScopeClassification,
    ScopeType,
)

_FINANCIAL_SCOPE_EVIDENCE = re.compile(
    r"\b(?:stock|shares?|futures?|ticker|financial market|market price|share price)\b",
    re.I,
)


class DomainScopeCorrectionUpdater:
    def update(self, current, context, correction: DomainScopeCorrection):
        if (
            not correction.detected
            or context is None
            or context.previous_result is None
        ):
            return current

        previous = context.previous_result
        changed = {item.field_name for item in correction.updates}
        classification = current.classification
        scope_classification = current.scope_classification

        if "domains" not in changed:
            classification = previous.classification
        else:
            domains = tuple(
                dict.fromkeys(correction.preserved_domains + correction.updated_domains)
            )
            primary = current.classification.primary_domain
            if primary not in domains:
                primary = (
                    domains[0] if domains else current.classification.primary_domain
                )
            classification = replace(
                current.classification,
                primary_domain=primary,
                secondary_domains=tuple(item for item in domains if item != primary),
                subdomains=tuple(
                    dict.fromkeys(
                        previous.classification.subdomains
                        + current.classification.subdomains
                    )
                ),
                domains=domains,
                candidate_domains=tuple(
                    dict.fromkeys(
                        previous.classification.candidate_domains
                        + current.classification.candidate_domains
                    )
                ),
            )

        if not {"scopes", "scope_subjects"}.intersection(changed):
            scope_classification = self._as_inherited_context(
                previous.scope_classification
            )
        elif "scopes" not in changed:
            scope_classification = current.scope_classification
        else:
            scopes = correction.updated_scopes
            if scopes:
                current_primary = (
                    current.scope_classification.primary_scope
                    if current.scope_classification is not None
                    else None
                )
                primary = current_primary if current_primary in scopes else scopes[0]
                preserved_evidence = self._preserved_scope_evidence(
                    correction,
                    scopes,
                    (
                        current.scope_detection.evidence
                        if current.scope_detection is not None
                        else ()
                    ),
                )
                preserved_evidence = tuple(
                    item
                    for item in preserved_evidence
                    if item.provenance == EvidenceProvenance.HISTORICAL
                    and item.source_span is not None
                    and item.source_text is not None
                )
                previous_subjects = tuple(
                    dict.fromkeys(
                        item.subject for item in preserved_evidence if item.subject
                    )
                )
                current_subjects = (
                    current.scope_classification.scope_subjects
                    if current.scope_classification is not None
                    else ()
                )
                subjects = tuple(dict.fromkeys(current_subjects + previous_subjects))
                previous_levels = tuple(
                    dict.fromkeys(
                        item.level
                        for item in preserved_evidence
                        if item.level is not None
                    )
                )
                current_levels = (
                    current.scope_classification.scope_levels
                    if current.scope_classification is not None
                    else ()
                )
                scope_classification = ScopeClassification(
                    primary_scope=primary,
                    secondary_scopes=tuple(item for item in scopes if item != primary),
                    scope_subjects=subjects,
                    scope_levels=tuple(dict.fromkeys(current_levels + previous_levels)),
                    boundaries=tuple(
                        dict.fromkeys(
                            (
                                current.scope_classification.boundaries
                                if current.scope_classification is not None
                                else ()
                            )
                            + self._preserved_scope_boundaries(preserved_evidence)
                        )
                    ),
                    direction=(
                        current.scope_classification.direction
                        if current.scope_classification is not None
                        else None
                    ),
                    relationships=(
                        current.scope_classification.relationships
                        if current.scope_classification is not None
                        else ()
                    ),
                )

        return replace(
            current,
            classification=classification,
            scope_classification=scope_classification,
        )

    @staticmethod
    def _as_inherited_context(classification):
        if classification is None:
            return None
        boundaries = tuple(
            replace(
                boundary,
                provenance=(
                    boundary.provenance
                    if boundary.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
                    else EvidenceProvenance.UPSTREAM_CONTEXT
                ),
            )
            for boundary in classification.boundaries
        )
        relationships = tuple(
            replace(
                relationship,
                provenance=(
                    relationship.provenance
                    if relationship.provenance == EvidenceProvenance.INTERNAL_TAXONOMY
                    else EvidenceProvenance.UPSTREAM_CONTEXT
                ),
            )
            for relationship in classification.relationships
        )
        unresolved = tuple(
            replace(
                item,
                provenance=EvidenceProvenance.UPSTREAM_CONTEXT,
            )
            for item in classification.unresolved_relationships
        )
        return replace(
            classification,
            boundaries=boundaries,
            relationships=relationships,
            unresolved_relationships=unresolved,
        )

    @staticmethod
    def _preserved_scope_evidence(correction, scopes, current_evidence=()):
        physical_replacement = (
            ScopeType.PHYSICAL_COMMERCE in correction.updated_scopes
            and ScopeType.FINANCIAL_MARKET not in correction.updated_scopes
        )
        current_keys = {
            (
                item.scope_type,
                item.evidence.casefold(),
                item.subject.casefold() if item.subject else None,
            )
            for item in current_evidence
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
        }
        return tuple(
            item
            for item in correction.previous_scope_evidence
            if item.scope_type in scopes
            and (
                item.scope_type,
                item.evidence.casefold(),
                item.subject.casefold() if item.subject else None,
            )
            not in current_keys
            and not (
                physical_replacement
                and item.scope_type == ScopeType.ASSET
                and _FINANCIAL_SCOPE_EVIDENCE.search(item.evidence)
            )
        )

    @staticmethod
    def _preserved_scope_boundaries(evidence):
        return tuple(
            ScopeBoundary(
                item.level,
                item.subject or item.evidence,
                item.evidence,
                item.source_span,
                EvidenceProvenance.UPSTREAM_CONTEXT,
                item.source_text,
            )
            for item in evidence
            if item.level is not None
        )
