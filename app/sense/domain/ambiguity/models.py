from dataclasses import dataclass, field
from enum import Enum

from app.sense.domain.models import DomainConfidence, DomainType
from app.sense.domain.scope.models import ScopeType


class AmbiguityType(str, Enum):
    NONE = "none"
    DOMAIN_AMBIGUOUS = "domain_ambiguous"
    SCOPE_AMBIGUOUS = "scope_ambiguous"
    DOMAIN_AND_SCOPE_AMBIGUOUS = "domain_and_scope_ambiguous"
    DOMAIN_CONFLICT = "domain_conflict"
    SCOPE_CONFLICT = "scope_conflict"
    MULTI_DOMAIN_UNCLEAR = "multi_domain_unclear"
    MULTI_SCOPE_UNCLEAR = "multi_scope_unclear"
    INSUFFICIENT_CONTEXT = "insufficient_context"


@dataclass(frozen=True)
class ScopeInterpretation:
    domain: DomainType | None = None
    scope: ScopeType | None = None
    description: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DomainScopeAmbiguity:
    ambiguity_present: bool = False
    ambiguity_type: AmbiguityType = AmbiguityType.NONE
    possible_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    possible_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    conflicting_domains: tuple[DomainType, ...] = field(default_factory=tuple)
    conflicting_scopes: tuple[ScopeType, ...] = field(default_factory=tuple)
    possible_interpretations: tuple[ScopeInterpretation, ...] = field(
        default_factory=tuple
    )
    clarification_required: bool = False
    clarification_reason: str | None = None
    confidence: DomainConfidence = DomainConfidence.UNKNOWN
    domain_ambiguity_type: AmbiguityType = AmbiguityType.NONE
    scope_ambiguity_type: AmbiguityType = AmbiguityType.NONE
    evidence: tuple[str, ...] = field(default_factory=tuple)
    conflict_evidence: tuple[str, ...] = field(default_factory=tuple)
