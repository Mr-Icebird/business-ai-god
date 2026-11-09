from dataclasses import dataclass, field

from app.sense.domain.models import DomainConfidence, DomainType


@dataclass(frozen=True)
class DomainClassification:
    primary_domain: DomainType = DomainType.UNKNOWN
    secondary_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    subdomains: tuple[DomainType, ...] = field(default_factory=tuple)
    domains: tuple[DomainType, ...] = field(default_factory=tuple)
    candidate_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    confidence: DomainConfidence = DomainConfidence.UNKNOWN
    primary_reason: str | None = None
