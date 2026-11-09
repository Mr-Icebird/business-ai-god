import re
import unicodedata
from datetime import date, datetime
from typing import Any, Mapping

from app.sense.input.language import LANGUAGE_INTELLIGENCE
from app.sense.input.language.models import (
    LanguageDetection,
    SlangDetection,
    SpellingDetection,
)
from app.sense.input.models import (
    AbbreviationMention,
    CurrencyMention,
    DateMention,
    DetectionMetadata,
    DetectionSource,
    DialectStatus,
    InputType,
    InputUnderstandingResult,
    LanguageCandidate,
    LanguageRelationType,
    LanguageStatus,
    NumericMention,
    RecognitionStatus,
    SpellingIssue,
    SpellingIssueType,
    SlangMention,
    SymbolMention,
    TextSpan,
    TextSpanType,
    UnitMention,
    URLMention,
    confidence_level_for,
)


class InputUnderstandingEngine:
    """
    SENSE-1: Input Understanding.

    Responsibilities:
    - preserve raw input
    - normalize text safely
    - detect structure
    - detect language and multilingual input
    - detect spelling/slang
    - detect abbreviations
    - detect numbers, percentages, ratios and multipliers
    - detect currencies, units, dates, URLs and symbols
    - detect code and commands
    - determine whether external intelligence is required
    """

    RATIO_PATTERN = re.compile(
        r"(?<![\w.])[+-]?\d+(?:\.\d+)?\s*x\b",
        re.IGNORECASE,
    )

    BASIS_POINT_PATTERN = re.compile(
        r"(?<![\w.])[+-]?\d+(?:\.\d+)?\s*(?:bps?|basis\s+points?)\b",
        re.IGNORECASE,
    )

    URL_PATTERN = re.compile(
        r"\b(?:https?://|www\.)[^\s<>()]+",
        re.IGNORECASE,
    )

    DATE_ISO_PATTERN = re.compile(
        r"\b\d{4}-\d{1,2}-\d{1,2}\b"
    )

    DATE_LONG_PATTERN = re.compile(
        r"\b(?:"
        r"January|February|March|April|May|June|July|August|"
        r"September|October|November|December"
        r")\s+\d{1,2}(?:,\s*\d{4})?\b",
        re.IGNORECASE,
    )

    DATE_NUMERIC_PATTERN = re.compile(
        r"\b(?:"
        r"(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})"
        r"|"
        r"(?P<day_first>\d{1,2})[./](?P<month_first>\d{1,2})"
        r"[./](?P<year_first>\d{4})"
        r")\b"
    )

    DATE_RELATIVE_PATTERN = re.compile(
        r"\b(?:today|tonight|yesterday|tomorrow|"
        r"the\s+day\s+before\s+yesterday|the\s+day\s+after\s+tomorrow|"
        r"(?:this|last|next)\s+(?:week|month|quarter|year)|"
        r"(?:in|within)\s+\d+\s+(?:days?|weeks?|months?|years?)|"
        r"\d+\s+(?:days?|weeks?|months?|years?)\s+ago)\b",
        re.IGNORECASE,
    )

    CURRENCY_PATTERN = re.compile(
        r"(?:"
        r"[$₦€£¥₹¢₽₩฿]\s*[+-]?(?:\d[\d,.]*\d|\d)"
        r"(?:\s*(?:k|thousand|m|million|b|billion|t|trillion))?"
        r"|"
        r"\b(?:USD|NGN|EUR|GBP|JPY|CNY|GHS|ZAR|KES|CAD|AUD|INR|RUB|KRW|THB)"
        r"\s*[+-]?(?:\d[\d,.]*\d|\d)"
        r"(?:\s*(?:k|thousand|m|million|b|billion|t|trillion))?"
        r"|"
        r"[+-]?(?:\d[\d,.]*\d|\d)"
        r"(?:\s*(?:k|thousand|m|million|b|billion|t|trillion))?"
        r"\s*\b(?:USD|NGN|EUR|GBP|JPY|CNY|GHS|ZAR|KES|CAD|AUD|INR|RUB|KRW|THB)\b"
        r")",
        re.IGNORECASE,
    )

    UNIT_PATTERN = re.compile(
        r"\b(?:"
        r"bpd|barrels?|tonnes?|tons?|kg|kgs|g|grams?|"
        r"mg|km|kms|miles?|litres?|liters?|"
        r"mbpd|mmbpd|mw|gw|hz|mhz|ghz|"
        r"hours?|minutes?|seconds?|days?|months?|years?"
        r")\b",
        re.IGNORECASE,
    )

    ABBREVIATION_PATTERN = re.compile(
        r"\b(?:"
        r"GDP|CPI|PPI|PMI|GNP|TTM|FCF|ARR|MRR|NIM|NPL|NPA|DCF|"
        r"IPO|ETF|ATH|ATL|"
        r"EBITDA|EBIT|EPS|PE|P/E|ROE|ROA|ROIC|"
        r"YoY|MoM|QoQ|CAGR|bps?|"
        r"CBN|SEC|IMF|WHO|WTO|OPEC|"
        r"API|URL|AI|ML|LLM|"
        r"FX|USD|NGN|EUR|GBP|JPY|CNY|GHS|ZAR|KES|CAD|AUD|INR|"
        r"XAU|XAG|BTC|ETH"
        r")\b",
        re.IGNORECASE,
    )

    SYMBOL_PATTERN = re.compile(
        r"[$₦€£¥₹¢₽₩฿%‰+\-*/=<>@#&×÷±]"
    )

    COMMAND_PATTERN = re.compile(
        r"^\s*(?:please\s+)?"
        r"(?:"
        r"show|give|tell|find|search|research|analyze|analyse|"
        r"calculate|compute|check|compare|explain|create|build|"
        r"generate|make|open|close|buy|sell|run|execute|"
        r"monitor|track|alert|notify|list|fetch|load|"
        r"get|download|upload|continue|start|stop"
        r")\b(?:\s+(?:me\b|us\b|the\b|a\b|an\b|my\b|our\b|"
        r"[A-Za-z$₦€£¥₹0-9]).*|\s*[.!?]*)$",
        re.IGNORECASE,
    )

    QUESTION_PATTERN = re.compile(
        r"(?:\?\s*[\"'’)]*\s*$|^\s*(?:"
        r"what|why|how|when|where|who|which|whose|whom"
        r")\s+(?:do|does|did|is|are|was|were|can|could|would|"
        r"should|will|has|have|had|might|may|must)\b|"
        r"^\s*(?:can|could|would|should|is|are|was|were|do|does|"
        r"did|will|has|have|had|might|may|must)\b)",
        re.IGNORECASE,
    )

    CODE_PATTERN = re.compile(
        r"(?:"
        r"^\s*(?:def|class|import|from|return|if|elif|else|for|while|"
        r"function|const|let|var|async|await|SELECT|INSERT|UPDATE|DELETE)\b"
        r"|"
        r"```|^\s*(?:>>>|\$)\s+"
        r"|"
        r"(?:=>|:=|==|!=|<=|>=|&&|\|\|)"
        r"|"
        r"^\s*[A-Za-z_]\w*\s*=\s*[^=]"
        r"|"
        r"^\s*(?:print|console\.log)\s*\("
        r"|"
        r"^\s*[\[{].*[\]}]\s*$"
        r")",
        re.IGNORECASE,
    )

    CURRENCY_MAP = {
        "$": ("USD", "US Dollar"),
        "₦": ("NGN", "Nigerian Naira"),
        "€": ("EUR", "Euro"),
        "£": ("GBP", "British Pound"),
        "¥": ("JPY", "Japanese Yen"),
        "₹": ("INR", "Indian Rupee"),
        "¢": ("USD", "US Cent"),
        "₽": ("RUB", "Russian Ruble"),
        "₩": ("KRW", "South Korean Won"),
        "฿": ("THB", "Thai Baht"),
    }

    CURRENCY_CODES = {
        "USD": ("USD", "US Dollar"),
        "NGN": ("NGN", "Nigerian Naira"),
        "EUR": ("EUR", "Euro"),
        "GBP": ("GBP", "British Pound"),
        "JPY": ("JPY", "Japanese Yen"),
        "CNY": ("CNY", "Chinese Yuan"),
        "GHS": ("GHS", "Ghanaian Cedi"),
        "ZAR": ("ZAR", "South African Rand"),
        "KES": ("KES", "Kenyan Shilling"),
        "CAD": ("CAD", "Canadian Dollar"),
        "AUD": ("AUD", "Australian Dollar"),
        "INR": ("INR", "Indian Rupee"),
        "RUB": ("RUB", "Russian Ruble"),
        "KRW": ("KRW", "South Korean Won"),
        "THB": ("THB", "Thai Baht"),
    }

    ABBREVIATIONS = {
        "GDP": "Gross Domestic Product",
        "CPI": "Consumer Price Index",
        "PPI": "Producer Price Index",
        "PMI": "Purchasing Managers' Index",
        "GNP": "Gross National Product",
        "EBITDA": "Earnings Before Interest, Taxes, Depreciation and Amortization",
        "EBIT": "Earnings Before Interest and Taxes",
        "EPS": "Earnings Per Share",
        "P/E": "Price-to-Earnings Ratio",
        "PE": "Price-to-Earnings Ratio",
        "ROE": "Return on Equity",
        "ROA": "Return on Assets",
        "ROIC": "Return on Invested Capital",
        "YoY": "Year over Year",
        "MoM": "Month over Month",
        "QoQ": "Quarter over Quarter",
        "CAGR": "Compound Annual Growth Rate",
        "TTM": "Trailing Twelve Months",
        "FCF": "Free Cash Flow",
        "ARR": "Annual Recurring Revenue",
        "MRR": "Monthly Recurring Revenue",
        "NIM": "Net Interest Margin",
        "NPL": "Non-Performing Loan",
        "NPA": "Non-Performing Asset",
        "DCF": "Discounted Cash Flow",
        "IPO": "Initial Public Offering",
        "ETF": "Exchange-Traded Fund",
        "ATH": "All-Time High",
        "ATL": "All-Time Low",
        "bps": "Basis Points",
        "CBN": "Central Bank of Nigeria",
        "SEC": "Securities and Exchange Commission",
        "IMF": "International Monetary Fund",
        "WHO": "World Health Organization",
        "WTO": "World Trade Organization",
        "OPEC": "Organization of the Petroleum Exporting Countries",
        "API": "Application Programming Interface",
        "URL": "Uniform Resource Locator",
        "AI": "Artificial Intelligence",
        "ML": "Machine Learning",
        "LLM": "Large Language Model",
        "FX": "Foreign Exchange",
        "XAU": "Gold",
        "XAG": "Silver",
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
    }

    UNIT_NORMALIZATION = {
        "bpd": ("bpd", "production_rate"),
        "mbpd": ("million barrels per day", "production_rate"),
        "mmbpd": ("million barrels per day", "production_rate"),
        "barrel": ("barrel", "volume"),
        "barrels": ("barrel", "volume"),
        "tonne": ("tonne", "mass"),
        "tonnes": ("tonne", "mass"),
        "ton": ("ton", "mass"),
        "tons": ("ton", "mass"),
        "kg": ("kg", "mass"),
        "kgs": ("kg", "mass"),
        "mg": ("mg", "mass"),
        "g": ("g", "mass"),
        "gram": ("g", "mass"),
        "grams": ("g", "mass"),
        "km": ("km", "distance"),
        "kms": ("km", "distance"),
        "mile": ("mile", "distance"),
        "miles": ("mile", "distance"),
        "litre": ("litre", "volume"),
        "litres": ("litre", "volume"),
        "liter": ("litre", "volume"),
        "liters": ("litre", "volume"),
        "mw": ("MW", "power"),
        "gw": ("GW", "power"),
        "hz": ("Hz", "frequency"),
        "mhz": ("MHz", "frequency"),
        "ghz": ("GHz", "frequency"),
        "hour": ("hour", "time"),
        "hours": ("hour", "time"),
        "minute": ("minute", "time"),
        "minutes": ("minute", "time"),
        "second": ("second", "time"),
        "seconds": ("second", "time"),
        "day": ("day", "time"),
        "days": ("day", "time"),
        "month": ("month", "time"),
        "months": ("month", "time"),
        "year": ("year", "time"),
        "years": ("year", "time"),
    }

    def _normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\u00a0", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _metadata(confidence: float) -> DetectionMetadata:
        return DetectionMetadata(
            source=DetectionSource.LOCAL_RULE,
            confidence=confidence,
            confidence_level=confidence_level_for(confidence),
        )

    def _parse_scaled_number(self, text: str) -> float | None:
        cleaned = text.lower().replace(",", "").strip()
        percent = cleaned.endswith("%")
        cleaned = cleaned.rstrip("%").strip()

        multiplier = 1.0

        match = re.search(
            r"\s*([kmbt])(?:illion)?\s*$",
            cleaned,
            re.IGNORECASE,
        )

        if match:
            multiplier_map = {
                "k": 1_000,
                "m": 1_000_000,
                "b": 1_000_000_000,
                "t": 1_000_000_000_000,
            }
            multiplier = multiplier_map[match.group(1).lower()]
            cleaned = cleaned[:match.start()].strip()

        try:
            value = float(cleaned) * multiplier
            return value / 100 if percent else value
        except ValueError:
            return None

    def _detect_urls(self, text: str) -> tuple[URLMention, ...]:
        results = []

        for match in self.URL_PATTERN.finditer(text):
            raw = match.group(0).rstrip(".,!?;:)")
            parsed = re.match(
                r"(?P<scheme>https?://)?(?P<domain>[^/]+)(?P<path>/.*)?",
                raw,
                re.IGNORECASE,
            )

            if not parsed:
                continue

            scheme = parsed.group("scheme") or ""
            domain = parsed.group("domain") or ""
            path = parsed.group("path") or ""

            results.append(
                URLMention(
                    text=raw,
                    scheme=scheme.rstrip(":/"),
                    domain=domain,
                    path=path,
                    metadata=self._metadata(0.97),
                )
            )

        return tuple(results)

    def _detect_numbers(
        self,
        text: str,
        protected_spans: tuple[tuple[int, int], ...] = (),
    ) -> tuple[NumericMention, ...]:
        scale_map = {
            "k": 1_000.0,
            "thousand": 1_000.0,
            "m": 1_000_000.0,
            "million": 1_000_000.0,
            "b": 1_000_000_000.0,
            "billion": 1_000_000_000.0,
            "t": 1_000_000_000_000.0,
            "trillion": 1_000_000_000_000.0,
        }
        symbol_codes = {
            "$": "USD",
            "₦": "NGN",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "₹": "INR",
            "¢": "USD",
            "₽": "RUB",
            "₩": "KRW",
            "฿": "THB",
        }
        currency_codes = "USD|NGN|EUR|GBP|JPY|CNY|GHS|ZAR|KES|CAD|AUD|INR|RUB|KRW|THB"
        number_pattern = re.compile(
            r"(?<![\w.])(?P<open>\()?(?P<prefix>[$₦€£¥₹¢₽₩฿]|"
            rf"(?:{currency_codes})\s+)?"
            r"(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
            r"\d{1,3}(?:\.\d{3})+,\d+|\d+(?:[.,]\d+)?))"
            r"(?P<scale>\s*(?:k|thousand|m|million|b|billion|t|trillion))?"
            r"(?P<percent>\s*(?:%|percent|percentage))?"
            rf"(?:\s*(?P<suffix>{currency_codes})\b)?(?P<close>\))?"
            r"(?!\w|,(?=\d)|\.(?=\d))",
            re.IGNORECASE,
        )
        special: list[tuple[int, int, NumericMention]] = []

        for match in self.RATIO_PATTERN.finditer(text):
            value = float(match.group(0)[:-1].strip())
            special.append((match.start(), match.end(), NumericMention(
                text=match.group(0),
                value=value,
                ratio=value,
                normalized_value=value,
                quantity_type="ratio",
                metadata=self._metadata(0.98),
            )))

        for match in self.BASIS_POINT_PATTERN.finditer(text):
            value = float(re.search(r"[+-]?\d+(?:\.\d+)?", match.group(0)).group(0))
            special.append((match.start(), match.end(), NumericMention(
                text=match.group(0),
                value=value,
                basis_points=value,
                normalized_value=value / 10_000,
                quantity_type="basis_points",
                metadata=self._metadata(0.98),
            )))

        excluded = protected_spans + tuple(
            (start, end) for start, end, _ in special
        )
        found = list(special)

        for match in number_pattern.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in excluded):
                continue

            raw = match.group(0).strip()
            number_text = match.group("number")
            if "," in number_text and "." in number_text:
                if number_text.rfind(",") > number_text.rfind("."):
                    parsed_number = number_text.replace(".", "").replace(",", ".")
                else:
                    parsed_number = number_text.replace(",", "")
            elif "," in number_text:
                parsed_number = number_text.replace(",", ".") if re.search(r",\d{1,2}$", number_text) else number_text.replace(",", "")
            else:
                parsed_number = number_text
            value = float(parsed_number)
            if match.group("open") and match.group("close") and value > 0:
                value = -value

            scale_text = (match.group("scale") or "").strip().lower()
            multiplier = scale_map.get(scale_text, 1.0)
            is_percentage = bool(match.group("percent"))
            currency_token = (match.group("prefix") or "").strip()
            currency_token = currency_token or (match.group("suffix") or "")
            currency = symbol_codes.get(currency_token)
            if currency is None and currency_token:
                currency = currency_token.upper()

            mention = NumericMention(
                text=raw,
                value=value,
                currency=currency,
                percentage=value if is_percentage else None,
                multiplier=multiplier if multiplier != 1.0 else None,
                multiplier_text=scale_text or None,
                normalized_value=value if is_percentage else value * multiplier,
                quantity_type="percentage" if is_percentage else "number",
                metadata=self._metadata(0.98),
            )
            found.append((match.start(), match.end(), mention))

        found.sort(key=lambda item: (item[0], item[1]))
        return tuple(item for _, _, item in found)

    def _detect_currencies(self, text: str) -> tuple[CurrencyMention, ...]:
        results = []
        seen = set()

        for match in self.CURRENCY_PATTERN.finditer(text):
            raw = match.group(0).strip()
            if raw in seen:
                continue

            symbol = next(
                (s for s in self.CURRENCY_MAP if s in raw),
                None,
            )

            if symbol:
                code, name = self.CURRENCY_MAP[symbol]
            else:
                code_match = re.search(r"\b[A-Z]{3}\b", raw.upper())
                if not code_match:
                    continue
                code = code_match.group(0)
                if code not in self.CURRENCY_CODES:
                    continue
                _, name = self.CURRENCY_CODES[code]

            results.append(
                CurrencyMention(
                    text=raw,
                    code=code,
                    symbol=symbol or code,
                    name=name,
                    confidence=0.98,
                    metadata=self._metadata(0.98),
                )
            )
            seen.add(raw)

        return tuple(results)

    def _detect_units(self, text: str) -> tuple[UnitMention, ...]:
        results = []

        for match in self.UNIT_PATTERN.finditer(text):
            raw = match.group(0)
            key = raw.lower()

            if key not in self.UNIT_NORMALIZATION:
                continue

            normalized, category = self.UNIT_NORMALIZATION[key]

            results.append(
                UnitMention(
                    text=raw,
                    normalized=normalized,
                    category=category,
                    confidence=0.96,
                    metadata=self._metadata(0.96),
                )
            )

        return tuple(results)

    def _detect_dates(self, text: str) -> tuple[DateMention, ...]:
        results: list[tuple[int, DateMention]] = []

        for match in self.DATE_ISO_PATTERN.finditer(text):
            raw = match.group(0)
            normalized = None
            try:
                normalized = date.fromisoformat(raw).isoformat()
            except ValueError:
                continue
            results.append((match.start(), DateMention(
                text=raw,
                normalized=normalized,
                temporal_type="absolute",
                metadata=self._metadata(0.99),
            )))

        for match in self.DATE_LONG_PATTERN.finditer(text):
            raw = match.group(0)
            normalized = None
            valid_date = False
            for date_format in ("%B %d, %Y", "%B %d"):
                try:
                    parsed = datetime.strptime(raw, date_format)
                    normalized = parsed.strftime("%Y-%m-%d") if "," in raw else None
                    valid_date = True
                    break
                except ValueError:
                    continue
            if not valid_date:
                continue
            results.append((match.start(), DateMention(
                text=raw,
                normalized=normalized,
                temporal_type="absolute",
                metadata=self._metadata(0.98),
            )))

        for match in self.DATE_NUMERIC_PATTERN.finditer(text):
            raw = match.group(0)
            if match.group("year"):
                month = int(match.group("month"))
                day_value = int(match.group("day"))
                year = int(match.group("year"))
            else:
                day_value = int(match.group("day_first"))
                month = int(match.group("month_first"))
                year = int(match.group("year_first"))
            temporal_type = "absolute"
            try:
                normalized = date(year, month, day_value).isoformat()
            except ValueError:
                if match.group("year"):
                    try:
                        normalized = date(year, day_value, month).isoformat()
                    except ValueError:
                        continue
                else:
                    continue
            else:
                if match.group("year") and 1 <= day_value <= 12:
                    alternate = date(year, day_value, month).isoformat()
                    if alternate != normalized:
                        normalized = None
                        temporal_type = "ambiguous"
            results.append((match.start(), DateMention(
                text=raw,
                normalized=normalized,
                temporal_type=temporal_type,
                metadata=self._metadata(0.90),
            )))

        for match in self.DATE_RELATIVE_PATTERN.finditer(text):
            raw = match.group(0)
            results.append((match.start(), DateMention(
                text=raw,
                temporal_type="relative",
                metadata=self._metadata(0.92),
            )))

        unique: dict[tuple[int, int], DateMention] = {}
        for start, mention in results:
            unique[(start, start + len(mention.text))] = mention
        return tuple(mention for _, mention in sorted(unique.items()))

    def _detect_abbreviations(
        self,
        text: str,
    ) -> tuple[AbbreviationMention, ...]:
        results = []

        for match in self.ABBREVIATION_PATTERN.finditer(text):
            raw = match.group(0)
            key = raw if raw in self.ABBREVIATIONS else raw.upper()

            meaning = self.ABBREVIATIONS.get(key)

            if meaning is None:
                continue

            results.append(
                AbbreviationMention(
                    text=raw,
                    expanded_form=meaning,
                    confidence=0.96,
                    metadata=self._metadata(0.96),
                )
            )

        return tuple(results)

    def _detect_symbols(self, text: str) -> tuple[SymbolMention, ...]:
        meanings = {
            "$": "currency",
            "₦": "currency",
            "€": "currency",
            "£": "currency",
            "¥": "currency",
            "₹": "currency",
            "¢": "currency",
            "₽": "currency",
            "₩": "currency",
            "฿": "currency",
            "%": "percentage",
            "‰": "per_mille",
            "+": "addition_or_positive",
            "-": "negative_or_subtraction",
            "/": "ratio_or_division",
            "=": "assignment_or_equality",
            "<": "comparison",
            ">": "comparison",
            "@": "mention_or_rate",
            "#": "number_or_tag",
            "&": "and",
            "×": "multiplication",
            "÷": "division",
            "±": "plus_or_minus",
        }

        results = []

        for match in self.SYMBOL_PATTERN.finditer(text):
            symbol = match.group(0)

            results.append(
                SymbolMention(
                    text=symbol,
                    meaning=meanings.get(symbol, "symbol"),
                    category="mathematical_or_financial",
                    confidence=0.95,
                    metadata=self._metadata(0.95),
                )
            )

        return tuple(results)

    def _detect_spans(
        self,
        text: str,
        urls: tuple[URLMention, ...],
        numbers: tuple[NumericMention, ...],
        dates: tuple[DateMention, ...],
        currencies: tuple[CurrencyMention, ...],
        units: tuple[UnitMention, ...],
        abbreviations: tuple[AbbreviationMention, ...],
        slang: tuple[SlangMention, ...],
        spelling_issues: tuple[SpellingIssue, ...],
        symbols: tuple[SymbolMention, ...],
        is_code: bool,
    ) -> tuple[TextSpan, ...]:
        groups = (
            (urls, TextSpanType.URL),
            (numbers, TextSpanType.NUMBER),
            (dates, TextSpanType.DATE),
            (currencies, TextSpanType.CURRENCY),
            (units, TextSpanType.UNIT),
            (abbreviations, TextSpanType.ABBREVIATION),
            (slang, TextSpanType.SLANG),
            (spelling_issues, TextSpanType.SPELLING),
            (symbols, TextSpanType.SYMBOL),
        )
        spans = []
        for items, span_type in groups:
            cursor = 0
            for item in items:
                item_text = item.text
                start = text.find(item_text, cursor)
                if start < 0:
                    start = text.find(item_text)
                if start >= 0:
                    end = start + len(item_text)
                    spans.append(TextSpan(
                        text=item_text,
                        start=start,
                        end=end,
                        span_type=span_type,
                    ))
                    cursor = end

        if is_code and text:
            spans.append(TextSpan(
                text=text,
                start=0,
                end=len(text),
                span_type=TextSpanType.CODE,
            ))
        return tuple(sorted(spans, key=lambda span: (span.start or 0, span.end or 0)))

    def understand(
        self,
        text: str,
        input_type: InputType | str = InputType.TEXT,
        *,
        content_reference: str | None = None,
        input_metadata: Mapping[str, Any] | None = None,
    ) -> InputUnderstandingResult:

        raw_input = text if isinstance(text, str) else str(text)
        try:
            resolved_input_type = (
                input_type if isinstance(input_type, InputType)
                else InputType(input_type)
            )
        except (TypeError, ValueError):
            resolved_input_type = InputType.UNKNOWN

        normalized = self._normalize(raw_input)

        language: LanguageDetection = (
            LANGUAGE_INTELLIGENCE.detect(normalized)
            if normalized
            else LanguageDetection(
                language="unknown",
                dialect=None,
                confidence=0.0,
                candidates=(),
                code_switching_detected=False,
                signals=(),
                requires_external_intelligence=False,
                reason=None,
            )
        )

        spelling: tuple[SpellingDetection, ...] = (
            LANGUAGE_INTELLIGENCE.detect_spelling(normalized)
            if normalized
            else ()
        )

        slang: tuple[SlangDetection, ...] = (
            LANGUAGE_INTELLIGENCE.detect_slang(normalized)
            if normalized
            else ()
        )

        urls = self._detect_urls(normalized)
        dates = self._detect_dates(normalized)
        protected_spans = tuple(
            (start, start + len(item.text))
            for item in urls + dates
            if (start := normalized.find(item.text)) >= 0
        )
        numbers = self._detect_numbers(normalized, protected_spans)
        currencies = self._detect_currencies(normalized)
        units = self._detect_units(normalized)
        abbreviations = self._detect_abbreviations(normalized)
        symbols = self._detect_symbols(normalized)

        is_question = bool(self.QUESTION_PATTERN.search(normalized))
        command_match = self.COMMAND_PATTERN.match(normalized)
        command_lead = re.match(
            r"^\s*(?:please\s+)?[A-Za-z]+\b",
            normalized,
            re.IGNORECASE,
        )
        command_remainder = (
            normalized[command_lead.end():]
            if command_lead
            else ""
        )
        command_clause_is_statement = bool(
            command_match
            and re.match(
                r"\s+[A-Za-z][\w'-]*\s+(?:is|are|was|were|has|have|"
                r"rose|fell|increased|declined|remains|remained)\b",
                command_remainder,
                re.IGNORECASE,
            )
        )
        is_command = bool(command_match) and not command_clause_is_statement
        is_code = bool(self.CODE_PATTERN.search(normalized))
        is_statement = bool(normalized) and not any(
            (is_question, is_command, is_code)
        )

        language_candidates = tuple(
            LanguageCandidate(
                language=c[0] if isinstance(c, tuple) else c.language,
                confidence=c[1] if isinstance(c, tuple) else c.confidence,
                relation=(
                    LanguageRelationType.PRIMARY
                    if index == 0
                    else LanguageRelationType.SECONDARY
                ),
                metadata=self._metadata(
                    c[1] if isinstance(c, tuple) else c.confidence
                ),
            )
            for index, c in enumerate(language.candidates)
        )

        spelling_issues = tuple(
            SpellingIssue(
                text=item.text,
                issue_type=SpellingIssueType.MISSPELLING,
                suggested_correction=item.suggested_correction,
                confidence=item.confidence,
                metadata=self._metadata(item.confidence),
            )
            for item in spelling
        )
        slang_mentions = tuple(
            SlangMention(
                text=item.text,
                language=item.language,
                meaning=item.meaning,
                confidence=item.confidence,
                metadata=self._metadata(item.confidence),
            )
            for item in slang
        )

        external_required = bool(
            language.requires_external_intelligence
            or language.code_switching_detected
        )

        reason = language.reason if external_required else None

        confidence = (
            language.confidence
            if normalized and any(character.isalpha() for character in normalized)
            else 1.0
        )

        spans = self._detect_spans(
            normalized,
            urls,
            numbers,
            dates,
            currencies,
            units,
            abbreviations,
            slang_mentions,
            spelling_issues,
            symbols,
            is_code,
        )

        percentage_mentions = tuple(
            item
            for item in numbers
            if getattr(item, "percentage", None) is not None
        )

        # A non-empty input is a statement when it is not explicitly
        # classified as a question, command, or code.
        is_statement = bool(normalized) and not any(
            (is_question, is_command, is_code)
        )

        content_extraction_required = resolved_input_type in {
            InputType.DOCUMENT,
            InputType.PDF,
            InputType.IMAGE,
            InputType.CHART,
            InputType.TABLE,
            InputType.WEBSITE,
            InputType.WEBSITE_INFORMATION,
        }
        ambiguous_dates = tuple(
            item for item in dates if item.temporal_type == "ambiguous"
        )

        return InputUnderstandingResult(
            raw_input=raw_input,
            input_type=resolved_input_type,
            language=language.language,
            language_status=(
                LanguageStatus.MULTILINGUAL
                if language.code_switching_detected
                else LanguageStatus.DETECTED
                if language.language not in (None, "unknown") and language.confidence >= 0.70
                else LanguageStatus.UNCERTAIN
                if language.language not in (None, "unknown")
                else LanguageStatus.UNKNOWN
            ),
            dialect=language.dialect,
            dialect_status=DialectStatus(language.dialect_status.value),
            language_candidates=language_candidates,
            code_switching_detected=language.code_switching_detected,
            spelling_status=(
                RecognitionStatus.DETECTED
                if spelling_issues
                else RecognitionStatus.UNCERTAIN
                if external_required
                else RecognitionStatus.UNKNOWN
            ),
            spelling_errors_detected=bool(spelling_issues),
            spelling_issues=spelling_issues,
            slang=slang_mentions,
            slang_status=(
                RecognitionStatus.DETECTED
                if slang_mentions
                else RecognitionStatus.UNCERTAIN
                if external_required
                else RecognitionStatus.UNKNOWN
            ),
            slang_mentions=slang_mentions,
            abbreviations=tuple(abbreviations),
            abbreviation_mentions=abbreviations,
            numbers=numbers,
            percentages=percentage_mentions,
            currencies=tuple(currencies),
            currency_mentions=currencies,
            units=units,
            unit_mentions=units,
            symbols=symbols,
            symbol_mentions=symbols,
            dates=dates,
            urls=urls,
            spans=spans,
            is_code=is_code,
            is_command=is_command,
            is_question=is_question,
            is_statement=is_statement,
            normalized_text=normalized,
            requires_external_intelligence=external_required,
            external_intelligence_reason=reason,
            requires_content_extraction=content_extraction_required,
            content_extraction_reason=(
                "SENSE-1 classifies this input but does not extract content; "
                "an upstream fetcher or content parser is required."
                if content_extraction_required
                else None
            ),
            content_reference=content_reference,
            input_metadata=dict(input_metadata or {}),
            ambiguous=bool(ambiguous_dates),
            ambiguity_reason=(
                "Numeric date order is ambiguous without a locale hint."
                if ambiguous_dates
                else None
            ),
            confidence=confidence,
            confidence_level=confidence_level_for(confidence),
            metadata=DetectionMetadata(
                source=DetectionSource.LOCAL_KNOWLEDGE,
                confidence=confidence,
                confidence_level=confidence_level_for(confidence),
            ),
        )


INPUT_UNDERSTANDING = InputUnderstandingEngine()

# Backward-compatible public name used by the existing SENSE-1 tests.
INPUT_SENSE = INPUT_UNDERSTANDING
