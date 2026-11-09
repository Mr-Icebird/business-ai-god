from dataclasses import dataclass, field
from enum import Enum

from app.sense.domain.evidence import validate_source_span
from app.sense.domain.models import (
    DomainConfidence,
    DomainType,
    EvidenceProvenance,
)


class ScopeType(str, Enum):
    FINANCIAL_MARKET = "financial_market"
    COMMERCIAL_MARKET = "commercial_market"
    PHYSICAL_COMMERCE = "physical_commerce"
    BUSINESS = "business"
    ECONOMIC = "economic"
    INDUSTRY = "industry"
    COMPANY = "company"
    ASSET = "asset"
    GEOGRAPHIC = "geographic"
    REGULATORY = "regulatory"
    OPERATIONAL = "operational"
    STRATEGIC = "strategic"
    CROSS_DOMAIN = "cross_domain"
    UNKNOWN = "unknown"


class ScopeLevel(str, Enum):
    GLOBAL = "global"
    REGIONAL = "regional"
    COUNTRY = "country"
    STATE_LOCAL = "state_local"
    INDUSTRY = "industry"
    MARKET = "market"
    COMPANY = "company"
    PRODUCT = "product"
    ASSET = "asset"
    TRANSACTION = "transaction"
    INDIVIDUAL_EVENT = "individual_event"


class ScopeContextType(str, Enum):
    FINANCIAL = "financial"
    COMMERCIAL = "commercial"
    ECONOMIC = "economic"
    MARKET = "market"
    BUSINESS = "business"
    OPERATIONAL = "operational"
    GEOGRAPHIC = "geographic"
    REGULATORY = "regulatory"
    TEMPORAL = "temporal"


@dataclass(frozen=True)
class ScopeEvidence:
    scope_type: ScopeType
    evidence: str
    source: str
    confidence: DomainConfidence
    subject: str | None = None
    level: ScopeLevel | None = None
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class ScopeDetection:
    evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)

    @property
    def candidates(self) -> tuple[ScopeEvidence, ...]:
        return self.evidence


@dataclass(frozen=True)
class ScopeBoundary:
    level: ScopeLevel
    value: str
    evidence: str
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class ScopeRelationship:
    source_scope: ScopeType
    target_scope: ScopeType
    relation: str
    evidence: str | None = None
    source_subject: str | None = None
    target_subject: str | None = None
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class UnresolvedScopeRelationship:
    subjects: tuple[str, ...] = field(default_factory=tuple)
    source_spans: tuple[tuple[int, int], ...] = field(default_factory=tuple)
    reason: str = "co_occurrence_only"
    source_texts: tuple[str, ...] = field(default_factory=tuple)
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT

    def __post_init__(self) -> None:
        if self.source_spans and len(self.source_spans) != len(self.source_texts):
            raise ValueError("Each unresolved source span requires its source text.")
        for span, source_text in zip(self.source_spans, self.source_texts):
            validate_source_span(source_text, span)


@dataclass(frozen=True)
class ScopeClassification:
    primary_scope: ScopeType = ScopeType.UNKNOWN
    secondary_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    scope_subjects: tuple[str, ...] = field(default_factory=tuple)
    scope_levels: tuple[ScopeLevel, ...] = field(default_factory=tuple)
    boundaries: tuple[ScopeBoundary, ...] = field(default_factory=tuple)
    direction: str | None = None
    relationships: tuple[ScopeRelationship, ...] = field(default_factory=tuple)
    unresolved_relationships: tuple[UnresolvedScopeRelationship, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class ScopeHierarchyNode:
    level: ScopeLevel
    value: str | None = None
    parent_level: ScopeLevel | None = None
    parent_value: str | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.INTERNAL_TAXONOMY
    source_span: tuple[int, int] | None = None
    source_text: str | None = None
    parent_provenance: EvidenceProvenance = EvidenceProvenance.INTERNAL_TAXONOMY

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span)


@dataclass(frozen=True)
class ScopeHierarchyPath:
    subject: str | None = None
    nodes: tuple[ScopeHierarchyNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopeHierarchy:
    paths: tuple[ScopeHierarchyPath, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopeContext:
    context_type: ScopeContextType
    evidence: str
    subject: str | None = None
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class ScopeContextDetection:
    contexts: tuple[ScopeContext, ...] = field(default_factory=tuple)
    cross_domain: bool = False
    interaction_evidence: str | None = None
    domain_types: tuple[DomainType, ...] = field(default_factory=tuple)
