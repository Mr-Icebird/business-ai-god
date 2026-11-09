from dataclasses import dataclass

from app.sense.domain.models import DomainConfidence, DomainType


@dataclass(frozen=True)
class DomainCue:
    domain: DomainType
    pattern: str
    confidence: DomainConfidence
    cue_kind: str


DOMAIN_CUES = (
    DomainCue(
        DomainType.BUSINESS,
        r"\b(?:business(?:es)?|company|companies|corporate|revenue|profit|customer retention|business model)\b",
        DomainConfidence.HIGH,
        "business_context",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\b(?:transportation costs?|logistics companies|importers?|exporters?)\b",
        DomainConfidence.MEDIUM,
        "business_activity",
    ),
    DomainCue(
        DomainType.FINANCE,
        r"\b(?:revenue|profit|cash flow|budget|capital)\b",
        DomainConfidence.MEDIUM,
        "financial_measure",
    ),
    DomainCue(
        DomainType.FINANCE,
        r"\b(?:finance|financial|capital allocation|financial statement|cash flow|balance sheet)\b",
        DomainConfidence.HIGH,
        "finance_term",
    ),
    DomainCue(
        DomainType.FINANCE,
        r"\bbanking\s+sector\b",
        DomainConfidence.HIGH,
        "finance_banking_context",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\b(?:financial market|market price|market index|market performance|market rally|market selloff|share price|stock price)\b",
        DomainConfidence.HIGH,
        "market_context",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\b(?:analy[sz]e|compare|research|trade)\s+(?:the\s+)?(?:eur/?usd|gbp/?usd|usd/?jpy|xau/?usd|bitcoin|btc|ethereum|eth|gold|silver)\b",
        DomainConfidence.HIGH,
        "market_instrument_task",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\b(?:research|analy[sz]e|compare)\s+(?:crude oil|oil|gold|silver)\s+futures?\b",
        DomainConfidence.HIGH,
        "market_futures_task",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\b(?:Apple|Microsoft|Amazon|Google|Dangote)(?:'s)?\s+(?:stock|shares?)\b|"
        r"\b(?:its|the company'?s)\s+(?:stock|shares?)\b",
        DomainConfidence.HIGH,
        "company_equity_context",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\bwhat(?:'s| is)\s+(?:happening|going on)\s+with\s+(?:gold|silver|oil|crude|copper|bitcoin|btc|eurusd|eur/usd|stocks?|shares?|bonds?)\b",
        DomainConfidence.HIGH,
        "market_event_question",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\b(?:price|prices|fell|fall|dropped|rose|rallied|sold off|moving)\b.{0,32}\b(?:gold|silver|oil|crude|copper|bitcoin|btc|eurusd|eur/usd|stocks?|shares?|bonds?)\b|\b(?:gold|silver|oil|crude|copper|bitcoin|btc|eurusd|eur/usd|stocks?|shares?|bonds?)\b.{0,32}\b(?:price|prices|fell|fall|dropped|rose|rallied|sold off|moving)\b",
        DomainConfidence.HIGH,
        "asset_price_movement",
    ),
    DomainCue(
        DomainType.ECONOMICS,
        r"\b(?:econom(?:y|ic|ics)|inflation|interest rates?|gdp|gross domestic product|recession|unemployment|consumer prices?|central bank|exchange rate|imports?|exports?|importers?|exporters?)\b",
        DomainConfidence.HIGH,
        "economic_indicator",
    ),
    DomainCue(
        DomainType.ECONOMICS,
        r"\b(?:higher|rising|increased)\s+(?:oil|energy|fuel)\s+prices?\s+(?:affect|impact)\b|\bprices?\s+(?:affect|impact)\s+(?:transportation|logistics|production)\s+costs?",
        DomainConfidence.MEDIUM,
        "economic_effect",
    ),
    DomainCue(
        DomainType.FOREX,
        r"\b(?:weaker|weakening|weakened)\s+currenc(?:y|ies)\b",
        DomainConfidence.HIGH,
        "currency_change",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\b(?:currency|currenc(?:y|ies))\b.{0,32}\bimport costs?\b|"
        r"\bimport costs?\b.{0,32}\bcurrenc(?:y|ies)\b",
        DomainConfidence.MEDIUM,
        "import_cost_context",
    ),
    DomainCue(
        DomainType.TRADING,
        r"\b(?:trading strategy|trade execution|execute (?:this|the) trade|trading position|buy or sell|entry and exit|day trading)\b",
        DomainConfidence.HIGH,
        "trading_activity",
    ),
    DomainCue(
        DomainType.TRADING,
        r"\b(?:analy[sz]e|trade|monitor|compare)\s+(?:the\s+)?(?:eur/?usd|gbp/?usd|usd/?jpy|xau/?usd|forex pair|currency pair)\b",
        DomainConfidence.MEDIUM,
        "forex_trading_context",
    ),
    DomainCue(
        DomainType.ACCOUNTING,
        r"\b(?:accounting|bookkeeping|accounts payable|accounts receivable|ledger|journal entry|reconciliation|depreciation)\b",
        DomainConfidence.HIGH,
        "accounting_term",
    ),
    DomainCue(
        DomainType.BANKING,
        r"\b(?:banking|bank account|commercial bank|bank loan|deposit account|mortgage lending|credit facility)\b",
        DomainConfidence.HIGH,
        "banking_term",
    ),
    DomainCue(
        DomainType.BANKING,
        r"\bbank(?:s)?\s+(?:sector|shares|loans|deposits|earnings)\b",
        DomainConfidence.MEDIUM,
        "banking_context",
    ),
    DomainCue(
        DomainType.BANKING,
        r"\b(?:regulation|regulatory|rules?)\b.{0,32}\bbanks?\b|"
        r"\bbanks?\b.{0,32}\b(?:regulation|regulatory|rules?)\b",
        DomainConfidence.MEDIUM,
        "banking_regulatory_context",
    ),
    DomainCue(
        DomainType.INVESTMENT,
        r"\b(?:investment|investing|portfolio|asset allocation|equity holding|investment thesis|capital gains)\b",
        DomainConfidence.HIGH,
        "investment_term",
    ),
    DomainCue(
        DomainType.COMMODITIES,
        r"\b(?:gold|silver|platinum|palladium|oil|crude|natural gas|copper|wheat|corn|cocoa|soybeans?|commodity|commodities)\b",
        DomainConfidence.MEDIUM,
        "commodity_entity",
    ),
    DomainCue(
        DomainType.FOREX,
        r"\b(?:forex|foreign exchange|currency pair|eurusd|eur/usd|gbpusd|gbp/usd|usdjpy|usd/jpy|xauusd|xau/usd|naira|exchange rate)\b",
        DomainConfidence.HIGH,
        "forex_instrument",
    ),
    DomainCue(
        DomainType.CRYPTO,
        r"\b(?:crypto(?:currency)?|bitcoin|btc|ethereum|eth|blockchain|digital asset|altcoin)\b",
        DomainConfidence.HIGH,
        "crypto_asset",
    ),
    DomainCue(
        DomainType.EQUITIES,
        r"\b(?:equities|equity|dividends?|ticker|listed company|shareholders?)\b",
        DomainConfidence.HIGH,
        "equity_instrument",
    ),
    DomainCue(
        DomainType.EQUITIES,
        r"\b(?:stocks?|shares?)\b",
        DomainConfidence.MEDIUM,
        "equity_instrument",
    ),
    DomainCue(
        DomainType.BONDS,
        r"\b(?:bonds?|treasur(?:y|ies)|fixed income|yield curve|coupon rate|sovereign debt)\b",
        DomainConfidence.HIGH,
        "bond_instrument",
    ),
    DomainCue(
        DomainType.MACROECONOMICS,
        r"\b(?:macroeconom(?:y|ics)|inflation|gdp|recession|unemployment|interest rates?|monetary policy|fiscal policy|central bank)\b",
        DomainConfidence.HIGH,
        "macro_topic",
    ),
    DomainCue(
        DomainType.MICROECONOMICS,
        r"\b(?:microeconom(?:y|ics)|supply and demand|price elasticity|marginal cost|market demand|consumer behavior)\b",
        DomainConfidence.HIGH,
        "micro_topic",
    ),
    DomainCue(
        DomainType.ENERGY,
        r"\b(?:energy|oil|crude|petroleum|natural gas|electricity|power generation|renewables?|fuel)\b",
        DomainConfidence.MEDIUM,
        "energy_entity",
    ),
    DomainCue(
        DomainType.AGRICULTURE,
        r"\b(?:agricultur(?:e|al)|farming|farmers?|harvest|crop yields?|livestock|fertilizer|cocoa|maize)\b",
        DomainConfidence.HIGH,
        "agriculture_term",
    ),
    DomainCue(
        DomainType.AGRICULTURE,
        r"\b(?:apple|orange|mango|banana)\b.{0,24}\b(?:fruit|orchard|harvest|farm|crop)\b|\b(?:fruit|orchard|harvest|farm|crop)\b.{0,24}\b(?:apple|orange|mango|banana)\b",
        DomainConfidence.HIGH,
        "agricultural_context",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\bamazon\b",
        DomainConfidence.LOW,
        "ambiguous_brand_or_place",
    ),
    DomainCue(
        DomainType.TECHNOLOGY,
        r"\bamazon\b",
        DomainConfidence.LOW,
        "ambiguous_brand_or_place",
    ),
    DomainCue(
        DomainType.REAL_ESTATE,
        r"\b(?:real estate|property market|housing(?: market)?|rent(?:al)? yield|commercial property|mortgage rates?)\b",
        DomainConfidence.HIGH,
        "real_estate_term",
    ),
    DomainCue(
        DomainType.TECHNOLOGY,
        r"\b(?:technology|software|hardware|artificial intelligence|semiconductor|cloud computing|iphone|smartphone|app development|tech sector)\b",
        DomainConfidence.HIGH,
        "technology_term",
    ),
    DomainCue(
        DomainType.GEOPOLITICS,
        r"\b(?:geopolitics?|sanctions?|trade war|armed conflict|election|diplomacy|geopolitical|tariffs?)\b",
        DomainConfidence.HIGH,
        "geopolitical_term",
    ),
    DomainCue(
        DomainType.REGULATION,
        r"\b(?:regulation|regulatory|compliance|legislation|licensing rules?|regulator|policy requirements?)\b",
        DomainConfidence.HIGH,
        "regulatory_term",
    ),
    DomainCue(
        DomainType.TAX,
        r"\b(?:tax(?:ation|es)?|vat|capital gains tax|corporate tax|tax filing|tax relief)\b",
        DomainConfidence.HIGH,
        "tax_term",
    ),
    DomainCue(
        DomainType.OPERATIONS,
        r"\b(?:operations?|operational costs?|logistics|transportation costs?|manufacturing|capacity planning|warehousing)\b",
        DomainConfidence.HIGH,
        "operations_term",
    ),
    DomainCue(
        DomainType.OPERATIONS,
        r"\b(?:airline operating costs?|operating costs?|airline costs?|transportation costs?)\b",
        DomainConfidence.HIGH,
        "operations_cost_context",
    ),
    DomainCue(
        DomainType.MARKETING,
        r"\b(?:marketing|advertising|brand awareness|campaign performance|customer acquisition)\b",
        DomainConfidence.HIGH,
        "marketing_term",
    ),
    DomainCue(
        DomainType.SALES,
        r"\b(?:sales|sales pipeline|conversion rate|sales forecast|deal closing)\b",
        DomainConfidence.HIGH,
        "sales_term",
    ),
    DomainCue(
        DomainType.SUPPLY_CHAIN,
        r"\b(?:supply chain|sourcing|procurement|freight|shipping costs?|inventory movement|distribution network)\b",
        DomainConfidence.HIGH,
        "supply_chain_term",
    ),
    DomainCue(
        DomainType.SUPPLY_CHAIN,
        r"\b(?:logistics companies|importers?|exporters?)\b",
        DomainConfidence.MEDIUM,
        "supply_chain_activity",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\bapple\b",
        DomainConfidence.LOW,
        "ambiguous_brand_or_fruit",
    ),
    DomainCue(
        DomainType.TECHNOLOGY,
        r"\bapple\b",
        DomainConfidence.LOW,
        "ambiguous_brand_or_fruit",
    ),
    DomainCue(
        DomainType.AGRICULTURE,
        r"\bapple\b",
        DomainConfidence.LOW,
        "ambiguous_brand_or_fruit",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\bmarket\b",
        DomainConfidence.LOW,
        "ambiguous_market_mention",
    ),
    DomainCue(
        DomainType.BANKING, r"\bbank\b", DomainConfidence.LOW, "ambiguous_bank_mention"
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\bmarket\b",
        DomainConfidence.LOW,
        "ambiguous_market_mention",
    ),
    DomainCue(
        DomainType.BUSINESS,
        r"\bexchange\b",
        DomainConfidence.LOW,
        "ambiguous_exchange_mention",
    ),
    DomainCue(
        DomainType.MARKETS,
        r"\bexchange\b",
        DomainConfidence.LOW,
        "ambiguous_exchange_mention",
    ),
)
