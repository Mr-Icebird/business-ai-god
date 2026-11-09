from dataclasses import dataclass, field

from app.sense.domain.models import DomainType, EvidenceProvenance


@dataclass(frozen=True)
class DomainHierarchyNode:
    domain: DomainType
    parent: DomainType | None = None
    children: tuple[DomainType, ...] = field(default_factory=tuple)
    ancestors: tuple[DomainType, ...] = field(default_factory=tuple)
    depth: int = 0
    provenance: EvidenceProvenance = EvidenceProvenance.INTERNAL_TAXONOMY


@dataclass(frozen=True)
class DomainHierarchy:
    nodes: tuple[DomainHierarchyNode, ...] = field(default_factory=tuple)

    def node_for(self, domain: DomainType) -> DomainHierarchyNode | None:
        return next((node for node in self.nodes if node.domain == domain), None)
