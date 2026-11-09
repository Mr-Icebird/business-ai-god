from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.sense.domain.models import DomainConfidence

if TYPE_CHECKING:
    from app.sense.domain.detection.models import DomainSignal
    from app.sense.domain.scope.models import ScopeEvidence


@dataclass(frozen=True)
class DomainScopeConfidence:
    domain: DomainConfidence = DomainConfidence.UNKNOWN
    scope: DomainConfidence = DomainConfidence.UNKNOWN
    overall: DomainConfidence = DomainConfidence.UNKNOWN
    domain_reasons: tuple[str, ...] = field(default_factory=tuple)
    scope_reasons: tuple[str, ...] = field(default_factory=tuple)
    overall_reasons: tuple[str, ...] = field(default_factory=tuple)
    domain_evidence: tuple[DomainSignal, ...] = field(default_factory=tuple)
    scope_evidence: tuple[ScopeEvidence, ...] = field(default_factory=tuple)
