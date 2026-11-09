from app.sense.domain.hierarchy.knowledge import CHILDREN_BY_DOMAIN, PARENT_BY_DOMAIN
from app.sense.domain.hierarchy.models import DomainHierarchy, DomainHierarchyNode
from app.sense.domain.models import DomainType


class DomainHierarchyResolver:
    def resolve(self, domains: tuple[DomainType, ...]) -> DomainHierarchy:
        selected = set(domains)
        for domain in tuple(selected):
            selected.update(self.ancestors(domain))
        nodes = []
        for domain in sorted(selected, key=lambda item: item.value):
            ancestors = self.ancestors(domain)
            nodes.append(
                DomainHierarchyNode(
                    domain=domain,
                    parent=PARENT_BY_DOMAIN.get(domain),
                    children=tuple(
                        child
                        for child in CHILDREN_BY_DOMAIN.get(domain, ())
                        if child in selected
                    ),
                    ancestors=ancestors,
                    depth=len(ancestors),
                )
            )
        return DomainHierarchy(nodes=tuple(nodes))

    @staticmethod
    def parent_of(domain: DomainType) -> DomainType | None:
        return PARENT_BY_DOMAIN.get(domain)

    @staticmethod
    def ancestors(domain: DomainType) -> tuple[DomainType, ...]:
        result = []
        parent = PARENT_BY_DOMAIN.get(domain)
        while parent is not None:
            result.append(parent)
            parent = PARENT_BY_DOMAIN.get(parent)
        return tuple(result)

    @staticmethod
    def descendants(domain: DomainType) -> tuple[DomainType, ...]:
        result = []
        pending = list(CHILDREN_BY_DOMAIN.get(domain, ()))
        while pending:
            child = pending.pop(0)
            result.append(child)
            pending.extend(CHILDREN_BY_DOMAIN.get(child, ()))
        return tuple(result)
