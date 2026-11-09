from app.sense.domain.scope.knowledge import SCOPE_HIERARCHY
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeHierarchy,
    ScopeHierarchyNode,
    ScopeHierarchyPath,
    ScopeLevel,
)

_MAX_ASSOCIATION_GAP = 8
_MAX_GLOBAL_ASSOCIATION_GAP = 40
_SUBJECT_LEVEL_PRIORITY = (
    ScopeLevel.COMPANY,
    ScopeLevel.ASSET,
    ScopeLevel.MARKET,
    ScopeLevel.PRODUCT,
    ScopeLevel.INDUSTRY,
    ScopeLevel.TRANSACTION,
    ScopeLevel.COUNTRY,
    ScopeLevel.STATE_LOCAL,
    ScopeLevel.REGIONAL,
    ScopeLevel.GLOBAL,
)


class ScopeHierarchyResolver:
    def resolve(self, classification) -> ScopeHierarchy:
        boundaries = tuple(
            dict.fromkeys(
                boundary
                for boundary in classification.boundaries
                if boundary.source_span is not None
            )
        )
        if not boundaries:
            return ScopeHierarchy()

        explicit_company_industries = {
            (relationship.source_subject, relationship.target_subject)
            for relationship in classification.relationships
            if relationship.relation == "company_in_industry"
        }
        parent_by_child = {}
        for child_index, child in enumerate(boundaries):
            parents = [
                (parent_index, parent)
                for parent_index, parent in enumerate(boundaries)
                if parent_index != child_index
                and child.level in SCOPE_HIERARCHY.get(parent.level, ())
            ]
            if child.level == ScopeLevel.COMPANY:
                parents = [
                    (parent_index, parent)
                    for parent_index, parent in parents
                    if parent.level != ScopeLevel.INDUSTRY
                    or (parent.value, child.value) in explicit_company_industries
                ]
            related_parent = self._nearest_related_parent(child, parents)
            if related_parent is not None:
                parent_by_child[child_index] = related_parent

        parent_indices = set(parent_by_child.values())
        leaves = [
            index for index in range(len(boundaries)) if index not in parent_indices
        ]
        paths = []
        seen_paths = set()
        for leaf_index in leaves:
            chain = [leaf_index]
            while chain[-1] in parent_by_child:
                parent_index = parent_by_child[chain[-1]]
                if parent_index in chain:
                    break
                chain.append(parent_index)
            chain.reverse()
            nodes = tuple(
                ScopeHierarchyNode(
                    level=boundaries[index].level,
                    value=self._value(boundaries[index]),
                    parent_level=(
                        boundaries[chain[position - 1]].level if position else None
                    ),
                    parent_value=(
                        self._value(boundaries[chain[position - 1]])
                        if position
                        else None
                    ),
                    provenance=boundaries[index].provenance,
                    source_span=boundaries[index].source_span,
                    source_text=boundaries[index].source_text,
                    parent_provenance=EvidenceProvenance.INTERNAL_TAXONOMY,
                )
                for position, index in enumerate(chain)
            )
            subject = self._subject(chain, boundaries)
            path_key = (
                subject,
                tuple(
                    (node.level, node.value, node.parent_level, node.parent_value)
                    for node in nodes
                ),
            )
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)
            paths.append(ScopeHierarchyPath(subject=subject, nodes=nodes))
        return ScopeHierarchy(tuple(paths))

    @classmethod
    def _nearest_related_parent(cls, child, candidates):
        related = []
        for index, parent in candidates:
            gap = cls._span_distance(parent.source_span, child.source_span)
            maximum_gap = (
                _MAX_GLOBAL_ASSOCIATION_GAP
                if parent.level == ScopeLevel.GLOBAL
                else _MAX_ASSOCIATION_GAP
            )
            if gap <= maximum_gap:
                related.append((index, parent, gap))
        if not related:
            return None

        related.sort(
            key=lambda item: (
                item[2],
                -cls._overlap(item[1].source_span, child.source_span),
                item[1].source_span,
                item[1].value,
            )
        )
        best_distance = related[0][2]
        equally_near = [item for item in related if item[2] == best_distance]
        if len(equally_near) > 1:
            best_overlap = max(
                cls._overlap(item[1].source_span, child.source_span)
                for item in equally_near
            )
            equally_near = [
                item
                for item in equally_near
                if cls._overlap(item[1].source_span, child.source_span) == best_overlap
            ]
        if len(equally_near) != 1:
            return None
        return equally_near[0][0]

    @staticmethod
    def _span_distance(left, right):
        if left[1] < right[0]:
            return right[0] - left[1]
        if right[1] < left[0]:
            return left[0] - right[1]
        return 0

    @staticmethod
    def _overlap(left, right):
        return max(0, min(left[1], right[1]) - max(left[0], right[0]))

    @staticmethod
    def _value(boundary):
        if boundary.level == ScopeLevel.MARKET:
            return None
        return boundary.value

    @classmethod
    def _subject(cls, chain, boundaries):
        path_boundaries = tuple(boundaries[index] for index in chain)
        candidate_boundaries = path_boundaries + tuple(
            boundary
            for boundary in boundaries
            if boundary.level == ScopeLevel.COMPANY and boundary not in path_boundaries
        )
        for level in _SUBJECT_LEVEL_PRIORITY:
            candidate_scores = {}
            for boundary in candidate_boundaries:
                if boundary.level != level or not boundary.value:
                    continue
                scores = [
                    (
                        cls._span_distance(
                            boundary.source_span, boundaries[index].source_span
                        ),
                        -cls._overlap(
                            boundary.source_span, boundaries[index].source_span
                        ),
                    )
                    for index in chain
                    if cls._span_distance(
                        boundary.source_span, boundaries[index].source_span
                    )
                    <= _MAX_ASSOCIATION_GAP
                ]
                if scores:
                    candidate_scores[boundary] = min(scores)
            if candidate_scores:
                best_score = min(candidate_scores.values())
                subjects = {
                    boundary.value
                    for boundary, score in candidate_scores.items()
                    if score == best_score
                }
                if len(subjects) == 1:
                    return next(iter(subjects))
        return None
