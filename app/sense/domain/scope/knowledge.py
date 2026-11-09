import re

from app.sense.domain.models import DomainConfidence
from app.sense.domain.scope.models import ScopeContextType, ScopeLevel, ScopeType

_SCOPE_CUES = (
    (
        ScopeType.FINANCIAL_MARKET,
        re.compile(
            r"\b(?:futures?|stock market|share price|stock price|equities market|forex market|financial markets?|oil prices?|gold prices?|crude oil prices?|commodity prices?|ticker|traded on exchange|market capitalization)\b|\b(?:analy[sz]e|compare|research|check|what is happening with)\s+(?:eur/?usd|gbp/?usd|usd/?jpy|xau/?usd|bitcoin|btc|ethereum|eth)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.FINANCIAL_MARKET,
        re.compile(
            r"\b(?:stock|share)\s+(?:performing|react(?:ed|s)?|traded)\b|\b(?:its|the company'?s|Apple's|Microsoft's|Amazon's|Google's|Dangote's|Apple|Microsoft|Amazon|Google|Dangote)\s+(?:stock|shares?)\b|\b(?:gold|oil|commodity|forex)\s+markets?\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.FINANCIAL_MARKET,
        re.compile(
            r"\b(?:earnings|announcement|earnings release|market crash|oil crash)\b",
            re.I,
        ),
        DomainConfidence.MEDIUM,
    ),
    (
        ScopeType.COMMERCIAL_MARKET,
        re.compile(
            r"\b(?:retail|wholesale|consumer|service|smartphone|e-commerce|online|"
            r"petroleum|logistics|agricultural produce|gold|commodity)\s+markets?\b|"
            r"\b(?:online\s+)?marketplaces?\b|"
            r"\b(?:retail|consumer|agricultural|product|goods?)\s+"
            r"(?:consumer\s+)?(?:supply|demand)\b|"
            r"\b(?:agricultural produce|commodity)\s+(?:wholesale\s+)?"
            r"(?:trading|trade|buying|selling)\b|"
            r"\b(?:consumer demand|retail consumer demand|retail prices?|"
            r"supply and demand|petroleum prices?)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.PHYSICAL_COMMERCE,
        re.compile(
            r"\b(?:physical (?:supply|market|commodity|gold|oil|crude)|"
            r"produc(?:e|es|ed|tion)|manufactur(?:e|es|ing)|"
            r"transport(?:ed|ing|ation)?|shipment|buyers?|available|"
            r"supply chain|crude oil supply|physical oil supply|"
            r"buy(?:ing|s)?|sell(?:ing|s|d)?|delivered|mining|"
            r"distribution|extraction|refining|smelting)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.STRATEGIC,
        re.compile(
            r"\b(?:strategy|strategic|market entry|enter the .{0,24} market|expansion|competitive advantage|positioning|compete|long[- ]term plan|capital allocation strategy)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.REGULATORY,
        re.compile(
            r"\b(?:regulation|regulatory|regulator|compliance|license|licensing|rules?|SEC|CBN|central bank rule)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.OPERATIONAL,
        re.compile(
            r"\b(?:operat(?:ion|ions|ing|ional)|supply chain|manufactur(?:e|es|ing)|production costs?|shipping costs?|transportation costs?|logistics|reduce costs?|how .* work)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.INDUSTRY,
        re.compile(
            r"\b(?:airline industry|banking industry|banking sector|energy sector|oil industry|agriculture industry|mining industry|airlines?)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.COMPANY,
        re.compile(
            r"\b(?:company|companies|corporation|business entity|firm|Apple|Microsoft|Amazon|Google|Dangote|Tesla)\b",
            re.I,
        ),
        DomainConfidence.MEDIUM,
    ),
    (
        ScopeType.ECONOMIC,
        re.compile(
            r"\b(?:inflation|GDP|gross domestic product|interest rates?|econom(?:y|ic)|recession|unemployment|exports?|imports?)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.BUSINESS,
        re.compile(
            r"\b(?:business|revenue|profit|operating costs?|company performance|business costs?|commercial bank lending|bank lending|commercial banking)\b",
            re.I,
        ),
        DomainConfidence.HIGH,
    ),
    (
        ScopeType.ASSET,
        re.compile(
            r"\b(?:EURUSD|EUR/USD|GBPUSD|GBP/USD|USDJPY|USD/JPY|XAUUSD|gold|silver|crude oil|oil|Bitcoin|BTC|stock|shares?|bond|futures?)\b",
            re.I,
        ),
        DomainConfidence.MEDIUM,
    ),
)

_GEOGRAPHIC = (
    (re.compile(r"\bglobal(?:ly)?\b|\bworldwide\b", re.I), ScopeLevel.GLOBAL),
    (
        re.compile(
            r"\b(?:West Africa|East Africa|North America|South America|Europe|Asia|Africa|Middle East)\b",
            re.I,
        ),
        ScopeLevel.REGIONAL,
    ),
    (
        re.compile(
            r"\b(?:Nigeria|Nigerian|Ghana|Ghanaian|Kenya|Kenyan|Japan|Japanese|United States|US|UK|United Kingdom|China|India|Canada|Australia|South Africa)\b",
            re.I,
        ),
        ScopeLevel.COUNTRY,
    ),
    (
        re.compile(
            r"\b(?:Lagos|Abuja|Nairobi|Accra|New York|California|London)\b", re.I
        ),
        ScopeLevel.STATE_LOCAL,
    ),
)

_CONTEXT_CUES = (
    (
        ScopeContextType.FINANCIAL,
        re.compile(
            r"\b(?:stock|share|forex|futures?|bond|EURUSD|Bitcoin|portfolio|revenue|profit)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.COMMERCIAL,
        re.compile(
            r"\b(?:buyers?|selling|buying|exports?|imports?|shipment|trade goods|delivered)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.ECONOMIC,
        re.compile(
            r"\b(?:inflation|GDP|interest rates?|economy|recession|unemployment)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.MARKET,
        re.compile(r"\b(?:market|markets|price|prices|futures?)\b", re.I),
    ),
    (
        ScopeContextType.BUSINESS,
        re.compile(
            r"\b(?:company|business|firm|revenue|profit|airline|banks?)\b", re.I
        ),
    ),
    (
        ScopeContextType.OPERATIONAL,
        re.compile(
            r"\b(?:production|manufactur\w*|logistics|shipping|supply chain|transportation|operating costs?)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.GEOGRAPHIC,
        re.compile(
            r"\b(?:global|worldwide|Nigeria|Nigerian|Ghana|Ghanaian|Kenya|Kenyan|West Africa|Europe|Asia|Lagos|Abuja)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.REGULATORY,
        re.compile(
            r"\b(?:regulation|regulatory|compliance|license|licensing|CBN|SEC|rule)\b",
            re.I,
        ),
    ),
    (
        ScopeContextType.TEMPORAL,
        re.compile(
            r"\b(?:today|currently|this year|last year|in 20\d{2}|during|earnings|announcement)\b",
            re.I,
        ),
    ),
)

CROSS_DOMAIN_RELATION = re.compile(
    r"\b(?:affect\w*|impact\w*|influenc\w*|cause\w*|increase\w*|reduce\w*|drive\w*|effect of|effect on)\b",
    re.I,
)

SCOPE_HIERARCHY = {
    ScopeLevel.GLOBAL: (
        ScopeLevel.REGIONAL,
        ScopeLevel.INDUSTRY,
        ScopeLevel.MARKET,
        ScopeLevel.INDIVIDUAL_EVENT,
    ),
    ScopeLevel.REGIONAL: (ScopeLevel.COUNTRY,),
    ScopeLevel.COUNTRY: (ScopeLevel.STATE_LOCAL,),
    ScopeLevel.INDUSTRY: (ScopeLevel.COMPANY,),
    ScopeLevel.COMPANY: (ScopeLevel.PRODUCT,),
    ScopeLevel.MARKET: (ScopeLevel.ASSET,),
    ScopeLevel.ASSET: (ScopeLevel.TRANSACTION,),
}
