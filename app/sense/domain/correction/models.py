from dataclasses import dataclass, field
from enum import Enum

from app.sense.domain.detection.models import DomainSignal
from app.sense.domain.models import (
    DomainConfidence,
    DomainType,
    EvidenceProvenance,
)
from app.sense.domain.scope.models import ScopeEvidence, ScopeType


class CorrectionType(str, Enum):
    NONE = "none"
    DOMAIN_REPLACEMENT = "domain_replacement"
    SCOPE_REPLACEMENT = "scope_replacement"
    DOMAIN_REFINEMENT = "domain_refinement"
    SCOPE_REFINEMENT = "scope_refinement"
    DOMAIN_ADDITION = "domain_addition"
    SCOPE_ADDITION = "scope_addition"
    CONTEXT_UPDATE = "context_update"
    INTERPRETATION_REPLACEMENT = "interpretation_replacement"


@dataclass(frozen=True)
class InterpretationUpdate:
    field_name: str
    previous_value: str
    updated_value: str
    evidence: str
    source_span: tuple[int, int] | None = None
    source_text: str | None = None


@dataclass(frozen=True)
class CorrectionHistoryEntry:
    correction_type: CorrectionType
    updates: tuple[InterpretationUpdate, ...] = field(default_factory=tuple)
    previous_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    updated_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    previous_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    updated_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    previous_domain_evidence: tuple[DomainSignal, ...] = field(default_factory=tuple)
    updated_domain_evidence: tuple[DomainSignal, ...] = field(default_factory=tuple)
    previous_scope_evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)
    updated_scope_evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)
    previous_scope_subjects: tuple[str, ...] = field(default_factory=tuple)
    updated_scope_subjects: tuple[str, ...] = field(default_factory=tuple)
    evidence: str | None = None
    confidence: DomainConfidence = DomainConfidence.UNKNOWN
    evidence_provenance: EvidenceProvenance = EvidenceProvenance.HISTORICAL


@dataclass(frozen=True)
class DomainScopeCorrection:
    detected: bool = False
    correction_type: CorrectionType = CorrectionType.NONE
    updates: tuple[InterpretationUpdate, ...] = field(default_factory=tuple)
    previous_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    updated_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    previous_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    updated_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    preserved_context: tuple[str, ...] = field(default_factory=tuple)
    evidence: str | None = None
    confidence: DomainConfidence = DomainConfidence.UNKNOWN
    previous_domain_evidence: tuple[DomainSignal, ...] = field(default_factory=tuple)
    updated_domain_evidence: tuple[DomainSignal, ...] = field(default_factory=tuple)
    previous_scope_evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)
    updated_scope_evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)
    preserved_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    preserved_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    previous_domain_confidence: DomainConfidence = DomainConfidence.UNKNOWN
    previous_scope_confidence: DomainConfidence = DomainConfidence.UNKNOWN
    history: tuple[CorrectionHistoryEntry, ...] = field(default_factory=tuple)
    evidence_provenance: EvidenceProvenance = EvidenceProvenance.SOURCE_TEXT
    previous_scope_subjects: tuple[str, ...] = field(default_factory=tuple)
    updated_scope_subjects: tuple[str, ...] = field(default_factory=tuple)
