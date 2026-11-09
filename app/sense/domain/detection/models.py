from dataclasses import dataclass, field

from app.sense.domain.evidence import validate_source_span
from app.sense.domain.models import (
    DomainConfidence,
    DomainType,
    EvidenceProvenance,
)


@dataclass(frozen=True)
class DomainSignal:
    domain: DomainType
    evidence: str
    source: str
    confidence: DomainConfidence
    explicit: bool = False
    source_span: tuple[int, int] | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    source_text: str | None = None

    def __post_init__(self) -> None:
        validate_source_span(self.source_text, self.source_span, self.evidence)


@dataclass(frozen=True)
class DomainCandidate:
    domain: DomainType
    confidence: DomainConfidence
    signals: tuple[DomainSignal, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DomainDetection:
    candidates: tuple[DomainCandidate, ...] = field(default_factory=tuple)
    signals: tuple[DomainSignal, ...] = field(default_factory=tuple)
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None
