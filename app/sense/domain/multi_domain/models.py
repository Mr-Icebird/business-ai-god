from dataclasses import dataclass, field
from enum import Enum

from app.sense.domain.evidence import validate_source_span
from app.sense.domain.models import DomainConfidence, DomainType
from app.sense.domain.models import EvidenceProvenance


class DomainRelationshipType(str, Enum):
    HIERARCHICAL = "hierarchical"
    INTERACTS_WITH = "interacts_with"
    CO_OCCURS_WITH = "co_occurs_with"


@dataclass(frozen=True)
class DomainRelationship:
    source_domain: DomainType
    target_domain: DomainType
    relationship_type: DomainRelationshipType
    evidence: str | None = None
    confidence: DomainConfidence = DomainConfidence.MEDIUM
    source_subject: str | None = None
    target_subject: str | None = None
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class DomainInteraction:
    domains: tuple[DomainType, ...]
    interaction: str
    evidence: str
    confidence: DomainConfidence = DomainConfidence.MEDIUM
    source_subject: str | None = None
    target_subject: str | None = None
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class MultiDomainResult:
    primary_domain: DomainType = DomainType.UNKNOWN
    secondary_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    domains: tuple[DomainType, ...] = field(default_factory=tuple)
    relationships: tuple[DomainRelationship, ...] = field(default_factory=tuple)
    interactions: tuple[DomainInteraction, ...] = field(default_factory=tuple)
    confidence: DomainConfidence = DomainConfidence.UNKNOWN
    is_ambiguous: bool = False
    candidate_domains: tuple[DomainType, ...] = field(default_factory=tuple)
