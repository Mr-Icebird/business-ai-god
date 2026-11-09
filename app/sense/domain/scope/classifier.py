from dataclasses import replace
import re

from app.sense.domain.models import DomainConfidence
from app.sense.domain.scope.knowledge import CROSS_DOMAIN_RELATION
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeBoundary,
    ScopeClassification,
    ScopeDetection,
    ScopeEvidence,
    ScopeRelationship,
    ScopeType,
    UnresolvedScopeRelationship,
)

_TASK_FOCUS_CUES = (
    (
        re.compile(
            r"\b(?:retail|wholesale|consumer|service|smartphone|e-commerce|online|"
            r"petroleum|logistics|agricultural produce)\s+markets?\b|"
            r"\bmarketplaces?\b|\b(?:consumer demand|retail consumer demand|"
            r"agricultural demand|agricultural supply|supply and demand|"
            r"wholesale trading|petroleum prices?)\b",
            re.I,
        ),
        ScopeType.COMMERCIAL_MARKET,
    ),
    (
        re.compile(
            r"\b(?:futures?|stock|shares?|forex|financial markets?|"
            r"gold prices?|oil prices?|crude oil prices?|commodity prices?|"
            r"(?:gold|oil|commodity|forex)\s+markets?)\b",
            re.I,
        ),
        ScopeType.FINANCIAL_MARKET,
    ),
    (
        re.compile(
            r"\b(?:company|companies|corporation|firm|Apple|Microsoft|Amazon|"
            r"Google|Dangote|Tesla)\b",
            re.I,
        ),
        ScopeType.COMPANY,
    ),
    (
        re.compile(
            r"\b(?:retail|e-commerce|online)\s+(?:business|store)\b|"
            r"\b(?:business|revenue|profit|commercial bank lending|bank lending)\b",
            re.I,
        ),
        ScopeType.BUSINESS,
    ),
    (
        re.compile(
            r"\b(?:operations?|manufactur\w*|production costs?|logistics|"
            r"shipping costs?|transportation costs?|operating costs?)\b",
            re.I,
        ),
        ScopeType.OPERATIONAL,
    ),
    (
        re.compile(
            r"\b(?:physical gold|physical shipment|crude oil supply|"
            r"physical oil supply|supply chain|produc(?:e|es|ed|tion)|"
            r"transport(?:ed|ing|ation)?|shipment|mining|distribution|"
            r"extraction|refining|smelting|buy(?:ing|s)?|sell(?:ing|s|d)?)\b",
            re.I,
        ),
        ScopeType.PHYSICAL_COMMERCE,
    ),
    (
        re.compile(r"\b(?:airline industry|banking industry|sector|industry)\b", re.I),
        ScopeType.INDUSTRY,
    ),
    (
        re.compile(
            r"\b(?:inflation|GDP|interest rates?|econom(?:y|ic)|recession|"
            r"unemployment|exports?|imports?)\b",
            re.I,
        ),
        ScopeType.ECONOMIC,
    ),
    (
        re.compile(
            r"\b(?:strategy|strategic|expansion|competitive advantage|"
            r"positioning|market entry|long[- ]term plan)\b",
            re.I,
        ),
        ScopeType.STRATEGIC,
    ),
    (
        re.compile(
            r"\b(?:regulation|regulatory|regulator|compliance|license|"
            r"licensing|rules?|SEC|CBN)\b",
            re.I,
        ),
        ScopeType.REGULATORY,
    ),
    (
        re.compile(r"\b(?:gold|silver|crude oil|oil|Bitcoin|BTC)\b", re.I),
        ScopeType.ASSET,
    ),
    (
        re.compile(
            r"\b(?:global(?:ly)?|worldwide|West Africa|East Africa|North America|"
            r"South America|Europe|Asia|Africa|Middle East|Nigeria|Nigerian|"
            r"Ghana|Ghanaian|Kenya|Kenyan|Japan|Japanese|United States|US|UK|"
            r"United Kingdom|China|India|Canada|Australia|South Africa|"
            r"Lagos|Abuja|Nairobi|Accra|New York|California|London)\b",
            re.I,
        ),
        ScopeType.GEOGRAPHIC,
    ),
)
_SCOPE_ORDER = {
    ScopeType.FINANCIAL_MARKET: 1,
    ScopeType.PHYSICAL_COMMERCE: 2,
    ScopeType.STRATEGIC: 3,
    ScopeType.REGULATORY: 4,
    ScopeType.OPERATIONAL: 5,
    ScopeType.ECONOMIC: 6,
    ScopeType.COMPANY: 7,
    ScopeType.INDUSTRY: 8,
    ScopeType.BUSINESS: 9,
    ScopeType.ASSET: 10,
    ScopeType.GEOGRAPHIC: 11,
    ScopeType.CROSS_DOMAIN: 0,
    ScopeType.COMMERCIAL_MARKET: 12,
}
_EXPLICIT_COMPANY_INDUSTRY = re.compile(
    r"\b(?P<company>Apple|Microsoft|Amazon|Google|Dangote|Tesla)\s+in\s+"
    r"(?:the\s+)?(?P<industry>airline industry|banking industry|"
    r"banking sector|energy sector|oil industry|agriculture industry|"
    r"mining industry)\b",
    re.I,
)
_EXPLICIT_POSSESSIVE_OPERATIONS = re.compile(
    r"\b(?P<company>Apple|Microsoft|Amazon|Google|Dangote|Tesla|company)'s\s+"
    r"(?:business\s+)?"
    r"(?P<operations>operations?)\b",
    re.I,
)
_EXPLICIT_POSSESSIVE_EQUITY = re.compile(
    r"\b(?P<company>Apple|Microsoft|Amazon|Google|Dangote|Tesla)'s\s+"
    r"(?P<equity>stock|shares?)\b",
    re.I,
)
_EXPLICIT_ASSET_FUTURES = re.compile(
    r"\b(?P<asset>gold|oil|crude oil|silver|Bitcoin|EURUSD|EUR/USD)\s+"
    r"(?P<transaction>futures?)\b",
    re.I,
)
_EXPLICIT_COUNTRY_ECONOMIC = re.compile(
    r"\b(?P<geography>Nigerian|Nigeria|US|United States|Japanese|Japan)\s+"
    r"(?P<economic>inflation|interest rates?|unemployment|GDP|gross domestic product|"
    r"economy|recession|exports?|imports?)\b",
    re.I,
)
_CLAUSE_CONTRAST = re.compile(
    r"\b(?:but|however|whereas|while|although|though|yet)\b", re.I
)
_COORDINATOR = re.compile(r",|\b(?:and|or)\b", re.I)
_CROSS_DOMAIN_SCOPES = {
    ScopeType.FINANCIAL_MARKET,
    ScopeType.COMMERCIAL_MARKET,
    ScopeType.PHYSICAL_COMMERCE,
    ScopeType.ECONOMIC,
    ScopeType.INDUSTRY,
    ScopeType.ASSET,
    ScopeType.REGULATORY,
    ScopeType.OPERATIONAL,
    ScopeType.STRATEGIC,
}
_CROSS_SCOPE_COMPARISON_TYPES = _CROSS_DOMAIN_SCOPES - {ScopeType.ASSET}


class ScopeClassifier:
    def classify(
        self,
        detection: ScopeDetection,
        *,
        text="",
        domain_result=None,
        sense2_result=None,
    ):
        evidence = list(detection.evidence)
        supported_interactions = self._supported_interactions(text, detection.evidence)
        relationships = self._explicit_subject_relationships(text, evidence)
        relationships.extend(
            self._interaction_relationships(text, supported_interactions)
        )
        has_cross_scope_comparison = any(
            item.relation == "compares"
            and item.source_scope in _CROSS_SCOPE_COMPARISON_TYPES
            and item.target_scope in _CROSS_SCOPE_COMPARISON_TYPES
            and item.source_scope != item.target_scope
            for item in relationships
        )
        if supported_interactions or has_cross_scope_comparison:
            cross_evidence = (
                supported_interactions[0][0].group()
                if supported_interactions
                else "explicit comparison across scopes"
            )
            evidence.append(
                ScopeEvidence(
                    ScopeType.CROSS_DOMAIN,
                    cross_evidence,
                    "connected_multiple_scope_contexts",
                    DomainConfidence.MEDIUM,
                    provenance=EvidenceProvenance.DERIVED,
                    source_text=text,
                )
            )

        types = {item.scope_type for item in evidence}
        if not types:
            return ScopeClassification()
        primary = ScopeClassifier._primary_scope(
            types, evidence, text, sense2_result, relationships
        )
        ordered = sorted(types, key=lambda item: _SCOPE_ORDER.get(item, 99))
        subjects = tuple(
            dict.fromkeys(item.subject for item in evidence if item.subject)
        )
        levels = tuple(
            dict.fromkeys(item.level for item in evidence if item.level is not None)
        )
        boundaries = tuple(
            ScopeBoundary(
                item.level,
                item.subject or item.evidence,
                item.evidence,
                item.source_span,
                item.provenance,
                item.source_text,
            )
            for item in evidence
            if item.level is not None
        )
        direction = (
            ScopeClassifier._interaction_direction(supported_interactions[0][0])
            if supported_interactions
            else None
        )
        unresolved = self._unresolved_relationships(
            text, detection.evidence, relationships, supported_interactions
        )
        relationships = [
            (
                replace(item, source_text=text)
                if item.provenance == EvidenceProvenance.SOURCE_TEXT
                and item.source_span is not None
                else item
            )
            for item in relationships
        ]
        return ScopeClassification(
            primary_scope=primary,
            secondary_scopes=tuple(item for item in ordered if item != primary),
            scope_subjects=subjects,
            scope_levels=levels,
            boundaries=boundaries,
            direction=direction,
            relationships=tuple(relationships),
            unresolved_relationships=tuple(unresolved),
        )

    @staticmethod
    def _primary_scope(types, evidence, text, sense2_result, relationships):
        if ScopeType.CROSS_DOMAIN in types:
            return ScopeType.CROSS_DOMAIN
        comparison_scopes = {
            scope
            for item in relationships
            if item.relation == "compares"
            for scope in (item.source_scope, item.target_scope)
        }
        if ScopeType.FINANCIAL_MARKET in comparison_scopes:
            return ScopeType.FINANCIAL_MARKET
        if (
            ScopeType.COMMERCIAL_MARKET in types
            and re.search(
                r"\b(?:gold|oil|crude oil|commodity)\s+markets?\b",
                text,
                re.I,
            )
            and not any(item.relation == "compares" for item in relationships)
            and not re.search(
                r"\b(?:futures?|stock|shares?|forex|financial market|"
                r"prices?|traded on exchange)\b",
                text,
                re.I,
            )
        ):
            return ScopeType.UNKNOWN

        task = getattr(sense2_result, "task", None)
        task_subjects = getattr(task, "subject", ()) if task else ()
        focus = task_subjects[0] if task_subjects else text
        clause_start, clause_end = ScopeClassifier._clause_bounds(text, 0)
        if not task_subjects:
            focus = text[clause_start:clause_end]
            coordinator = _COORDINATOR.search(focus)
            if coordinator is not None:
                focus = focus[: coordinator.start()]
        if (
            ScopeType.COMPANY in types
            and ScopeType.BUSINESS in types
            and re.search(r"\b(?:business|revenue|profit|earnings)\b", focus, re.I)
            and not re.search(
                r"\b(?:operations?|manufactur\w*|logistics)\b", focus, re.I
            )
            and any(
                item.scope_type == ScopeType.COMPANY
                and item.subject
                and item.subject.casefold()
                not in {"company", "companies", "corporation", "firm"}
                for item in evidence
            )
        ):
            return ScopeType.COMPANY
        cue_matches = []
        for cue_index, (pattern, scope_type) in enumerate(_TASK_FOCUS_CUES):
            if scope_type not in types or (
                scope_type == ScopeType.GEOGRAPHIC
                and len(types - {ScopeType.GEOGRAPHIC}) > 0
            ):
                continue
            for match in pattern.finditer(focus):
                cue_matches.append((match.end(), -cue_index, scope_type))
        if cue_matches:
            return max(cue_matches)[2]

        source_evidence = [
            item
            for item in evidence
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
            and item.source_span is not None
        ]
        if source_evidence:
            first_span = min(item.source_span[0] for item in source_evidence)
            first_types = {
                item.scope_type
                for item in source_evidence
                if item.source_span[0] == first_span
            }
            if len(first_types) == 1:
                return first_types.pop()
        if len(types) == 1:
            return next(iter(types))
        return ScopeType.UNKNOWN

    @staticmethod
    def _explicit_subject_relationships(text, evidence):
        relationships = ScopeClassifier._comparison_relationships(text, evidence)

        for match in _EXPLICIT_POSSESSIVE_OPERATIONS.finditer(text):
            company = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.COMPANY
                    and item.source_span == match.span("company")
                ),
                None,
            )
            operations = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.OPERATIONAL
                    and item.source_span == match.span("operations")
                ),
                None,
            )
            if company is None or operations is None:
                continue
            relationships.append(
                ScopeRelationship(
                    ScopeType.OPERATIONAL,
                    ScopeType.COMPANY,
                    "belongs_to",
                    match.group(),
                    operations.subject,
                    company.subject or company.evidence,
                    match.span(),
                    source_text=text,
                )
            )

        for match in _EXPLICIT_POSSESSIVE_EQUITY.finditer(text):
            company = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.COMPANY
                    and item.source_span == match.span("company")
                ),
                None,
            )
            equity = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.ASSET
                    and item.source_span == match.span("equity")
                ),
                None,
            )
            if company is None or equity is None:
                continue
            relationships.append(
                ScopeRelationship(
                    ScopeType.COMPANY,
                    ScopeType.ASSET,
                    "has_equity",
                    match.group(),
                    company.subject or company.evidence,
                    equity.subject or equity.evidence,
                    match.span(),
                    source_text=text,
                )
            )

        for match in _EXPLICIT_ASSET_FUTURES.finditer(text):
            asset = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.ASSET
                    and item.source_span == match.span("asset")
                ),
                None,
            )
            market = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.FINANCIAL_MARKET
                    and item.source_span == match.span("transaction")
                ),
                None,
            )
            if asset is None or market is None:
                continue
            relationships.append(
                ScopeRelationship(
                    ScopeType.FINANCIAL_MARKET,
                    ScopeType.ASSET,
                    "market_instrument",
                    match.group(),
                    market.subject,
                    asset.subject or asset.evidence,
                    match.span(),
                    source_text=text,
                )
            )

        for match in _EXPLICIT_COMPANY_INDUSTRY.finditer(text):
            company_span = match.span("company")
            industry_span = match.span("industry")
            company = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.COMPANY
                    and item.source_span == company_span
                ),
                None,
            )
            industry = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.INDUSTRY
                    and item.source_span == industry_span
                ),
                None,
            )
            if company is None or industry is None:
                continue
            relationships.append(
                ScopeRelationship(
                    ScopeType.INDUSTRY,
                    ScopeType.COMPANY,
                    "company_in_industry",
                    match.group(),
                    industry.subject or industry.evidence,
                    company.subject or company.evidence,
                    match.span(),
                    source_text=text,
                )
            )

        for match in _EXPLICIT_COUNTRY_ECONOMIC.finditer(text):
            geography_span = match.span("geography")
            economic_span = match.span("economic")
            geography = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.GEOGRAPHIC
                    and item.source_span == geography_span
                ),
                None,
            )
            economic = next(
                (
                    item
                    for item in evidence
                    if item.scope_type == ScopeType.ECONOMIC
                    and item.source_span == economic_span
                ),
                None,
            )
            if geography is None or economic is None:
                continue
            relationships.append(
                ScopeRelationship(
                    ScopeType.GEOGRAPHIC,
                    ScopeType.ECONOMIC,
                    "qualifies",
                    match.group(),
                    geography.subject or geography.evidence,
                    economic.evidence,
                    match.span(),
                    source_text=text,
                )
            )
        return relationships

    @staticmethod
    def _interaction_relationships(text, interactions):
        relationships = []
        for match, left, right in interactions:
            if any(
                item.provenance != EvidenceProvenance.SOURCE_TEXT
                for item in left + right
            ):
                continue
            left_span = (
                min(item.source_span[0] for item in left),
                max(item.source_span[1] for item in left),
            )
            right_span = (
                min(item.source_span[0] for item in right),
                max(item.source_span[1] for item in right),
            )
            source_scope = ScopeClassifier._scope_for_span(left, left_span)
            target_scope = ScopeClassifier._scope_for_span(right, right_span)
            if source_scope is None or target_scope is None:
                continue
            relation_span = (min(match.start(), left_span[0]), right_span[1])
            relationships.append(
                ScopeRelationship(
                    source_scope.scope_type,
                    target_scope.scope_type,
                    ScopeClassifier._interaction_direction(match),
                    text[slice(*relation_span)],
                    text[slice(*left_span)],
                    text[slice(*right_span)],
                    relation_span,
                    source_text=text,
                )
            )
        return relationships

    @staticmethod
    def _interaction_direction(match):
        relation = match.group().casefold()
        return "affects" if relation == "effect of" else relation

    @staticmethod
    def _comparison_relationships(text, evidence):
        relationships = []
        for comparison in re.finditer(r"\bcompare\b", text, re.I):
            _, clause_end = ScopeClassifier._clause_bounds(text, comparison.start())
            operand_start, operand_end = ScopeClassifier._trim_span(
                text, comparison.end(), clause_end
            )
            segments = []
            segment_start = operand_start
            for separator in re.finditer(
                r",|\b(?:with|to|and|versus|vs\.?)\b",
                text[operand_start:operand_end],
                re.I,
            ):
                segment_end = operand_start + separator.start()
                segment = ScopeClassifier._trim_span(text, segment_start, segment_end)
                if segment[0] < segment[1]:
                    segments.append(segment)
                segment_start = operand_start + separator.end()
            segment = ScopeClassifier._trim_span(text, segment_start, operand_end)
            if segment[0] < segment[1]:
                segments.append(segment)
            if len(segments) < 2:
                continue

            operands = []
            for segment in segments:
                segment_evidence = [
                    item
                    for item in evidence
                    if item.provenance == EvidenceProvenance.SOURCE_TEXT
                    and item.source_span is not None
                    and max(
                        0,
                        min(segment[1], item.source_span[1])
                        - max(segment[0], item.source_span[0]),
                    )
                ]
                if not segment_evidence:
                    continue
                operand_span = (
                    min(item.source_span[0] for item in segment_evidence),
                    max(item.source_span[1] for item in segment_evidence),
                )
                scope = ScopeClassifier._scope_for_span(segment_evidence, operand_span)
                if scope is not None:
                    operands.append((scope, operand_span, segment))
            if len(operands) < 2:
                continue

            source_scope, source_span, source_segment = operands[0]
            source_subject = ScopeClassifier._comparison_subject(
                evidence,
                text[slice(*source_segment)],
                source_span,
                source_scope.scope_type,
            )
            for target_scope, target_span, target_segment in operands[1:]:
                relation_span = (comparison.start(), target_span[1])
                target_subject = ScopeClassifier._comparison_subject(
                    evidence,
                    text[slice(*target_segment)],
                    target_span,
                    target_scope.scope_type,
                )
                relationships.append(
                    ScopeRelationship(
                        source_scope.scope_type,
                        target_scope.scope_type,
                        "compares",
                        text[slice(*relation_span)],
                        source_subject,
                        target_subject,
                        relation_span,
                        source_text=text,
                    )
                )
        return relationships

    @staticmethod
    def _supported_interactions(text, evidence):
        interactions = []
        for match in CROSS_DOMAIN_RELATION.finditer(text):
            clause_start, clause_end = ScopeClassifier._clause_bounds(
                text, match.start()
            )
            if match.group().casefold() == "effect of":
                on_match = re.search(r"\bon\b", text[match.end() : clause_end], re.I)
                if on_match is None:
                    continue
                on_start = match.end() + on_match.start()
                on_end = match.end() + on_match.end()
                left = [
                    item
                    for item in evidence
                    if item.provenance == EvidenceProvenance.SOURCE_TEXT
                    and item.source_span
                    and match.end() <= item.source_span[0]
                    and item.source_span[1] <= on_start
                ]
                right_start = on_end
                right_end = clause_end
            else:
                left = [
                    item
                    for item in evidence
                    if item.provenance
                    in {
                        EvidenceProvenance.SOURCE_TEXT,
                        EvidenceProvenance.UPSTREAM_CONTEXT,
                    }
                    and item.source_span
                    and clause_start <= item.source_span[0]
                    and item.source_span[1] <= match.start()
                ]
                if not left and re.search(
                    r"\b(?:it|its|they|them|this|that|those)\b",
                    text[clause_start : match.start()],
                    re.I,
                ):
                    left = [
                        item
                        for item in evidence
                        if item.provenance == EvidenceProvenance.UPSTREAM_CONTEXT
                    ]
                right_start = match.end()
                right_end = clause_end
            if left:
                left = ScopeClassifier._nearest_evidence_group(left, right=False)
            right = [
                item
                for item in evidence
                if item.provenance == EvidenceProvenance.SOURCE_TEXT
                and item.source_span
                and right_start <= item.source_span[0]
                and item.source_span[1] <= right_end
            ]
            if right:
                right = ScopeClassifier._nearest_evidence_group(right, right=True)
            if (
                left
                and right
                and any(
                    source.scope_type in _CROSS_DOMAIN_SCOPES
                    and target.scope_type in _CROSS_DOMAIN_SCOPES
                    and source.scope_type != target.scope_type
                    for source in left
                    for target in right
                )
            ):
                interactions.append((match, tuple(left), tuple(right)))
        return interactions

    @staticmethod
    def _nearest_evidence_group(evidence, *, right):
        spanned = tuple(item for item in evidence if item.source_span is not None)
        if not spanned:
            return tuple(evidence)
        if right:
            anchor = min(item.source_span[0] for item in spanned)
            nearest = tuple(
                item for item in spanned if item.source_span[0] <= anchor + 20
            )
        else:
            anchor = max(item.source_span[1] for item in spanned)
            nearest = tuple(
                item for item in spanned if item.source_span[1] >= anchor - 20
            )
        return nearest + tuple(item for item in evidence if item.source_span is None)

    @staticmethod
    def _unresolved_relationships(text, evidence, relationships, interactions):
        unresolved = []
        for start, end in ScopeClassifier._clauses(text):
            if any(
                relationship.relation == "compares"
                and relationship.source_span
                and start <= relationship.source_span[0] < end
                for relationship in relationships
            ):
                continue
            if any(
                start <= interaction[0].start() < end for interaction in interactions
            ):
                continue
            coordinated_segments = []
            segment_start = start
            for connector in _COORDINATOR.finditer(text, start, end):
                coordinated_segments.append((segment_start, connector.start()))
                segment_start = connector.end()
            coordinated_segments.append((segment_start, end))
            evidence_segments = [
                segment
                for segment in coordinated_segments
                if any(
                    item.provenance == EvidenceProvenance.SOURCE_TEXT
                    and item.source_span
                    and segment[0] <= item.source_span[0]
                    and item.source_span[1] <= segment[1]
                    for item in evidence
                )
            ]
            if len(evidence_segments) < 2:
                continue

            candidates = {}
            for relationship in relationships:
                span = relationship.source_span
                if (
                    relationship.relation != "compares"
                    and span is not None
                    and start <= span[0]
                    and span[1] <= end
                    and relationship.evidence
                ):
                    candidates[span] = relationship.evidence
            for item in evidence:
                span = item.source_span
                if (
                    item.provenance != EvidenceProvenance.SOURCE_TEXT
                    or span is None
                    or not start <= span[0] < span[1] <= end
                    or (
                        item.scope_type == ScopeType.FINANCIAL_MARKET
                        and any(
                            other.scope_type == ScopeType.ASSET
                            and other.source_span is not None
                            and span[0] <= other.source_span[0]
                            and other.source_span[1] <= span[1]
                            for other in evidence
                        )
                    )
                    or any(
                        candidate_start <= span[0] and span[1] <= candidate_end
                        for candidate_start, candidate_end in candidates
                    )
                ):
                    continue
                candidates.setdefault(span, item.subject or item.evidence)

            subjects = []
            source_spans = []
            seen = set()
            for span, subject in sorted(candidates.items()):
                key = subject.casefold()
                if key in seen:
                    continue
                seen.add(key)
                subjects.append(subject)
                source_spans.append(span)
            if len(subjects) > 1:
                unresolved.append(
                    UnresolvedScopeRelationship(
                        tuple(subjects),
                        tuple(source_spans),
                        source_texts=tuple(text for _ in source_spans),
                    )
                )
        return unresolved

    @staticmethod
    def _scope_for_span(evidence, span):
        candidates = [
            item
            for item in evidence
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
            and item.source_span is not None
            and max(
                0, min(span[1], item.source_span[1]) - max(span[0], item.source_span[0])
            )
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                min(span[1], item.source_span[1]) - max(span[0], item.source_span[0]),
                -_SCOPE_ORDER.get(item.scope_type, 99),
            ),
        )

    @staticmethod
    def _comparison_subject(evidence, fallback, span, scope):
        matching = [
            item
            for item in evidence
            if item.provenance == EvidenceProvenance.SOURCE_TEXT
            and item.source_span is not None
            and max(
                0,
                min(span[1], item.source_span[1]) - max(span[0], item.source_span[0]),
            )
        ]
        if scope == ScopeType.INDUSTRY:
            matching = [
                item for item in matching if item.scope_type == ScopeType.COMPANY
            ] or matching
        else:
            matching = [item for item in matching if item.scope_type == scope]
        if not matching:
            return fallback
        matched_subject = max(
            matching,
            key=lambda item: (
                min(span[1], item.source_span[1]) - max(span[0], item.source_span[0]),
                item.subject is not None,
            ),
        ).subject
        if scope in {ScopeType.COMPANY, ScopeType.ASSET, ScopeType.INDUSTRY}:
            return matched_subject or fallback
        return fallback or matched_subject

    @staticmethod
    def _trim_span(text, start, end):
        while start < end and text[start].isspace():
            start += 1
        while end > start and (text[end - 1].isspace() or text[end - 1] == ","):
            end -= 1
        return start, end

    @staticmethod
    def _clause_bounds(text, position):
        starts = [text.rfind(char, 0, position) for char in ".;!?\n"]
        start = max(starts) + 1
        ends = [index for char in ".;!?\n" if (index := text.find(char, position)) >= 0]
        ends.extend(
            match.start() for match in _CLAUSE_CONTRAST.finditer(text, position)
        )
        return start, min(ends, default=len(text))

    @staticmethod
    def _clauses(text):
        boundaries = {0, len(text)}
        for match in re.finditer(r"[.;!?\n]", text):
            boundaries.update((match.start(), match.end()))
        for match in _CLAUSE_CONTRAST.finditer(text):
            boundaries.update((match.start(), match.end()))
        ordered = sorted(boundaries)
        return [
            (left, right)
            for left, right in zip(ordered, ordered[1:])
            if left < right and text[left:right].strip()
        ]
