from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.sense.input.models import InputUnderstandingResult
    from app.sense.intent.models import Sense2Result
    from app.sense.domain.classification.models import DomainClassification
    from app.sense.domain.detection.models import DomainDetection
    from app.sense.domain.hierarchy.models import DomainHierarchy
    from app.sense.domain.multi_domain.models import MultiDomainResult
    from app.sense.domain.ambiguity.models import DomainScopeAmbiguity
    from app.sense.domain.confidence.models import DomainScopeConfidence
    from app.sense.domain.correction.models import DomainScopeCorrection
    from app.sense.domain.scope.models import (
        ScopeClassification,
        ScopeContextDetection,
        ScopeDetection,
        ScopeHierarchy,
    )


class DomainType(str, Enum):
    BUSINESS = "business"
    FINANCE = "finance"
    MARKETS = "markets"
    ECONOMICS = "economics"
    TRADING = "trading"
    ACCOUNTING = "accounting"
    BANKING = "banking"
    INVESTMENT = "investment"
    COMMODITIES = "commodities"
    FOREX = "forex"
    CRYPTO = "crypto"
    EQUITIES = "equities"
    BONDS = "bonds"
    MACROECONOMICS = "macroeconomics"
    MICROECONOMICS = "microeconomics"
    ENERGY = "energy"
    AGRICULTURE = "agriculture"
    REAL_ESTATE = "real_estate"
    TECHNOLOGY = "technology"
    GEOPOLITICS = "geopolitics"
    REGULATION = "regulation"
    TAX = "tax"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    SALES = "sales"
    SUPPLY_CHAIN = "supply_chain"
    UNKNOWN = "unknown"


class DomainConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class EvidenceProvenance(str, Enum):
    SOURCE_TEXT = "source_text"
    DERIVED = "derived"
    INTERNAL_TAXONOMY = "internal_taxonomy"
    UPSTREAM_CONTEXT = "upstream_context"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class DomainContext:
    previous_input: InputUnderstandingResult | None = None
    previous_sense2: Sense2Result | None = None
    previous_result: DomainUnderstandingResult | None = None
    previous_text: str | None = None
    previous_entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainUnderstandingResult:
    raw_text: str
    normalized_text: str
    detection: DomainDetection
    classification: DomainClassification
    hierarchy: DomainHierarchy
    multi_domain: MultiDomainResult
    source_input: InputUnderstandingResult | None = None
    source_sense2: Sense2Result | None = None
    scope_detection: ScopeDetection | None = None
    scope_classification: ScopeClassification | None = None
    scope_hierarchy: ScopeHierarchy | None = None
    scope_context: ScopeContextDetection | None = None
    ambiguity: DomainScopeAmbiguity | None = None
    confidence: DomainScopeConfidence | None = None
    correction: DomainScopeCorrection | None = None
    requires_clarification: bool = False
    explanation: str = ""

    @property
    def primary_domain(self) -> DomainType:
        return self.classification.primary_domain

    @property
    def secondary_domains(self) -> tuple[DomainType, ...]:
        return self.classification.secondary_domains

    @property
    def subdomains(self) -> tuple[DomainType, ...]:
        return self.classification.subdomains

    @property
    def domain_hierarchy(self):
        return self.hierarchy

    @property
    def domain_relationships(self):
        return self.multi_domain.relationships

    @property
    def scope(self):
        return self.scope_classification

    @property
    def scope_type(self):
        return (
            self.scope_classification.primary_scope
            if self.scope_classification is not None
            else None
        )

    @property
    def scope_level(self):
        return (
            self.scope_classification.scope_levels
            if self.scope_classification is not None
            else ()
        )

    @property
    def evidence(self):
        return {
            "domain": self.detection.signals,
            "scope": self.scope_detection.evidence if self.scope_detection else (),
        }

    @property
    def source_signals(self):
        return self.evidence

    def to_dict(self) -> dict[str, Any]:
        payload = _serialize(self)
        payload.update(
            {
                "primary_domain": _serialize(self.primary_domain),
                "secondary_domains": _serialize(self.secondary_domains),
                "subdomains": _serialize(self.subdomains),
                "domain_hierarchy": _serialize(self.hierarchy),
                "domain_relationships": _serialize(self.multi_domain.relationships),
                "scope": _serialize(self.scope_classification),
                "scope_context": _serialize(self.scope_context),
                "scope_type": _serialize(
                    self.scope_classification.primary_scope
                    if self.scope_classification
                    else None
                ),
                "scope_level": _serialize(
                    self.scope_classification.scope_levels
                    if self.scope_classification
                    else ()
                ),
                "evidence": _serialize(
                    {
                        "domain": self.detection.signals,
                        "scope": (
                            self.scope_detection.evidence
                            if self.scope_detection
                            else ()
                        ),
                    }
                ),
                "source_signals": _serialize(
                    {
                        "domain": self.detection.signals,
                        "scope": (
                            self.scope_detection.evidence
                            if self.scope_detection
                            else ()
                        ),
                    }
                ),
                "corrections": _serialize(self.correction),
            }
        )
        return payload


def build_explanation(result: DomainUnderstandingResult) -> str:
    parts = [f"Domain: {result.primary_domain.value}."]
    if result.scope_type is not None:
        parts.append(f"Scope: {result.scope_type.value}.")
    if result.confidence is not None:
        parts.append(
            "Confidence: domain "
            f"{result.confidence.domain.value}, scope "
            f"{result.confidence.scope.value}."
        )
    if result.ambiguity and result.ambiguity.ambiguity_present:
        parts.append(
            result.ambiguity.clarification_reason
            or "Domain or scope interpretation is uncertain."
        )
    if result.correction and result.correction.detected:
        parts.append("A contextual domain/scope correction was applied.")
    return " ".join(parts)


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _serialize(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value
