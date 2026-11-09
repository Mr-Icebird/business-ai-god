from app.sense.domain.models import DomainType

PARENT_BY_DOMAIN = {
    DomainType.BANKING: DomainType.FINANCE,
    DomainType.INVESTMENT: DomainType.FINANCE,
    DomainType.MARKETS: DomainType.FINANCE,
    DomainType.FOREX: DomainType.MARKETS,
    DomainType.EQUITIES: DomainType.MARKETS,
    DomainType.BONDS: DomainType.MARKETS,
    DomainType.COMMODITIES: DomainType.MARKETS,
    DomainType.CRYPTO: DomainType.MARKETS,
    DomainType.ENERGY: DomainType.COMMODITIES,
    DomainType.MACROECONOMICS: DomainType.ECONOMICS,
    DomainType.MICROECONOMICS: DomainType.ECONOMICS,
    DomainType.OPERATIONS: DomainType.BUSINESS,
    DomainType.MARKETING: DomainType.BUSINESS,
    DomainType.SALES: DomainType.BUSINESS,
    DomainType.SUPPLY_CHAIN: DomainType.BUSINESS,
}

CHILDREN_BY_DOMAIN = {}
for _child, _parent in PARENT_BY_DOMAIN.items():
    CHILDREN_BY_DOMAIN.setdefault(_parent, []).append(_child)
CHILDREN_BY_DOMAIN = {
    _parent: tuple(sorted(_children, key=lambda item: item.value))
    for _parent, _children in CHILDREN_BY_DOMAIN.items()
}
