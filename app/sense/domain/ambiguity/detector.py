import re

from app.sense.domain.ambiguity.models import (
    AmbiguityType,
    DomainScopeAmbiguity,
    ScopeInterpretation,
)
from app.sense.domain.evidence import is_negated_source_span
from app.sense.domain.models import DomainConfidence, DomainType
from app.sense.domain.scope.models import ScopeType

_CONFLICTING_APPLE = re.compile(
    r"\bapple\b.{0,32}\b(?:fruit|orchard)\b.{0,24}\bstock\b|"
    r"\bapple\b.{0,24}\bstock\b.{0,32}\b(?:fruit|orchard)\b",
    re.I,
)
_CONFLICTING_SCOPES = re.compile(
    r"\bfinancial[- ]market(?: scope)? only\b.{0,48}"
    r"\bphysical[- ]commerce(?: scope)? only\b|"
    r"\bphysical[- ]commerce(?: scope)? only\b.{0,48}"
    r"\bfinancial[- ]market(?: scope)? only\b",
    re.I,
)
_GENERIC_SCOPE_TERMS = {
    "amazon": (
        ScopeType.COMPANY,
        ScopeType.BUSINESS,
        ScopeType.INDUSTRY,
    ),
    "apple": (
        ScopeType.COMPANY,
        ScopeType.BUSINESS,
        ScopeType.FINANCIAL_MARKET,
    ),
    "bank": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
    ),
    "capital": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
    ),
    "energy": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.INDUSTRY,
    ),
    "exchange": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
    ),
    "interest": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
    ),
    "market": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
        ScopeType.COMMERCIAL_MARKET,
    ),
    "rate": (
        ScopeType.BUSINESS,
        ScopeType.ECONOMIC,
        ScopeType.FINANCIAL_MARKET,
    ),
    "stock": (
        ScopeType.ASSET,
        ScopeType.BUSINESS,
        ScopeType.FINANCIAL_MARKET,
    ),
    "trade": (
        ScopeType.BUSINESS,
        ScopeType.FINANCIAL_MARKET,
        ScopeType.PHYSICAL_COMMERCE,
        ScopeType.COMMERCIAL_MARKET,
    ),
    "oil": (
        ScopeType.ASSET,
        ScopeType.FINANCIAL_MARKET,
        ScopeType.PHYSICAL_COMMERCE,
        ScopeType.COMMERCIAL_MARKET,
    ),
    "gold": (
        ScopeType.ASSET,
        ScopeType.FINANCIAL_MARKET,
        ScopeType.PHYSICAL_COMMERCE,
        ScopeType.COMMERCIAL_MARKET,
    ),
}
_GENERIC_DOMAIN_TERMS = {
    "amazon": (DomainType.BUSINESS, DomainType.TECHNOLOGY),
    "apple": (
        DomainType.AGRICULTURE,
        DomainType.BUSINESS,
        DomainType.EQUITIES,
        DomainType.TECHNOLOGY,
    ),
    "bank": (DomainType.BANKING, DomainType.BUSINESS, DomainType.FINANCE),
    "capital": (DomainType.BUSINESS, DomainType.FINANCE, DomainType.INVESTMENT),
    "energy": (DomainType.BUSINESS, DomainType.ECONOMICS, DomainType.ENERGY),
    "exchange": (DomainType.BUSINESS, DomainType.FOREX, DomainType.MARKETS),
    "interest": (DomainType.BANKING, DomainType.ECONOMICS, DomainType.FINANCE),
    "market": (DomainType.BUSINESS, DomainType.ECONOMICS, DomainType.MARKETS),
    "rate": (DomainType.BANKING, DomainType.ECONOMICS, DomainType.FOREX),
    "stock": (DomainType.BUSINESS, DomainType.EQUITIES, DomainType.OPERATIONS),
}
_SCOPE_RESOLVERS = re.compile(
    r"\b(?:commercial|central|river|shore|stock price|share price|stock market|"
    r"share market|futures?|ticker|physical|production|produced|mining|mine|"
    r"supply|shipment|refin(?:e|ing)|extract(?:ion)?|housing|mortgage|loan|"
    r"lending|deposits?|currency|foreign exchange|forex|currency exchange|"
    r"stock exchange|capital allocation|invest(?:ment|ing)|cloud|AWS|"
    r"software|online retail|e-commerce|retailer|profit|revenue|company|"
    r"business|industry|sector|energy prices?|manufactur\w*|import costs?|"
    r"retail markets?|smartphone markets?|e-commerce markets?|"
    r"online marketplaces?|agricultural produce|wholesale trading|"
    r"petroleum markets?|consumer markets?|service markets?|"
    r"transportation costs?|logistics|airline|near my house|went to the bank|"
    r"sat by the bank|bank branch|(?:Apple|Amazon|Google|Microsoft)\s+"
    r"(?:stock|shares?)|(?:company|business)\s+(?:stock|shares?))\b",
    re.I,
)
_DOMAIN_RESOLVERS = (
    re.compile(
        r"\b(?:apple\s+(?:stock|shares?|company|business|fruit|orchard)|"
        r"(?:fruit|orchard|harvest)\s+apple)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:amazon(?:'s)?\s+(?:AWS|cloud|retail|e-commerce|business|company)|"
        r"(?:AWS|cloud|retail|e-commerce)\s+amazon)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:(?:commercial|central)\s+bank|bank(?:ing)?\s+"
        r"(?:loan|lending|deposit|regulation)|(?:loan|lending|deposit)\s+"
        r"(?:from|at)\s+(?:a\s+)?bank)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:interest rates?|housing markets?|stock prices?|share prices?|"
        r"stock market|foreign exchange|currency exchange|capital allocation|"
        r"energy prices?|commercial banks?|bank lending|bank deposits?|"
        r"market trends?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:Apple|Amazon|Google|Microsoft)(?:'s)?\s+"
        r"(?:business|operations?).{0,32}\b(?:stock|shares?)\b",
        re.I,
    ),
)
_RELATION = re.compile(
    r"\b(?:affect\w*|impact\w*|influenc\w*|cause\w*|increase\w*|"
    r"reduce\w*|drive\w*|compare\w*|versus|vs\.?)\b",
    re.I,
)
_CONTEXTUAL_RELATION_CUES = re.compile(
    r"\b(?:housing|airline|business(?:es)?|industry|industries|production|"
    r"prices?|imports?|"
    r"manufactur\w*|employment|inflation|operating costs?|transportation costs?|"
    r"logistics|profitability)\b",
    re.I,
)


class DomainScopeAmbiguityDetector:
    def detect(self, text, result, context=None) -> DomainScopeAmbiguity:
        domain_candidates = tuple(item.domain for item in result.detection.candidates)
        unresolved_domain_terms = self._unresolved_domain_terms(text)
        detected_scopes = {
            item.scope_type
            for item in result.scope_detection.evidence
            if item.scope_type != ScopeType.CROSS_DOMAIN
        }
        domain_ambiguous = self._domain_ambiguous(text, result, unresolved_domain_terms)
        scope_ambiguous, scope_candidates, scope_evidence = self._scope_ambiguity(
            text, result, context
        )
        domain_evidence = self._domain_evidence(result)

        domain_conflict_match = _CONFLICTING_APPLE.search(text)
        scope_conflict_match = _CONFLICTING_SCOPES.search(text)
        domain_conflict = domain_conflict_match is not None
        scope_conflict = scope_conflict_match is not None
        insufficient_context = self._missing_context(text, result, context)

        conflicting_domains = ()
        if domain_conflict:
            conflicting_domains = tuple(
                item
                for item in domain_candidates
                if item
                in {
                    DomainType.AGRICULTURE,
                    DomainType.TECHNOLOGY,
                    DomainType.BUSINESS,
                    DomainType.EQUITIES,
                }
            )
        conflicting_scopes = (
            (ScopeType.FINANCIAL_MARKET, ScopeType.PHYSICAL_COMMERCE)
            if scope_conflict
            else ()
        )

        domain_type = (
            AmbiguityType.DOMAIN_AMBIGUOUS if domain_ambiguous else AmbiguityType.NONE
        )
        scope_type = (
            AmbiguityType.MULTI_SCOPE_UNCLEAR
            if scope_ambiguous and len(scope_candidates) > 2
            else (
                AmbiguityType.SCOPE_AMBIGUOUS if scope_ambiguous else AmbiguityType.NONE
            )
        )

        if domain_conflict:
            ambiguity_type = AmbiguityType.DOMAIN_CONFLICT
        elif scope_conflict:
            ambiguity_type = AmbiguityType.SCOPE_CONFLICT
        elif insufficient_context:
            ambiguity_type = AmbiguityType.INSUFFICIENT_CONTEXT
        elif domain_ambiguous and scope_ambiguous:
            ambiguity_type = AmbiguityType.DOMAIN_AND_SCOPE_AMBIGUOUS
        elif domain_ambiguous and len(domain_candidates) > 2:
            ambiguity_type = AmbiguityType.MULTI_DOMAIN_UNCLEAR
        elif domain_ambiguous:
            ambiguity_type = AmbiguityType.DOMAIN_AMBIGUOUS
        elif scope_ambiguous and len(scope_candidates) > 2:
            ambiguity_type = AmbiguityType.MULTI_SCOPE_UNCLEAR
        elif scope_ambiguous:
            ambiguity_type = AmbiguityType.SCOPE_AMBIGUOUS
        elif insufficient_context:
            ambiguity_type = AmbiguityType.INSUFFICIENT_CONTEXT
        else:
            ambiguity_type = AmbiguityType.NONE

        ambiguity_present = any(
            (
                domain_ambiguous,
                scope_ambiguous,
                domain_conflict,
                scope_conflict,
                insufficient_context,
            )
        )
        clarification = ambiguity_present
        lexical_domain_candidates = tuple(
            dict.fromkeys(
                domain
                for _, alternatives in unresolved_domain_terms
                for domain in alternatives
            )
        )
        possible_domains = (
            tuple(dict.fromkeys((*domain_candidates, *lexical_domain_candidates)))
            if domain_ambiguous
            else conflicting_domains if domain_conflict else ()
        )
        possible_scopes = (
            tuple(
                sorted(
                    scope_candidates | set(conflicting_scopes),
                    key=lambda item: item.value,
                )
            )
            if scope_ambiguous
            else tuple(
                sorted(
                    detected_scopes | set(conflicting_scopes),
                    key=lambda item: item.value,
                )
            )
        )
        interpretations = self._interpretations(
            possible_domains,
            possible_scopes,
            result,
            scope_evidence,
        )
        conflict_evidence = tuple(
            item.group()
            for item in (domain_conflict_match, scope_conflict_match)
            if item is not None
        )
        evidence = tuple(
            dict.fromkeys(
                (
                    *domain_evidence,
                    *scope_evidence,
                    *(
                        f"Unresolved domain term: {term}"
                        for term, _ in unresolved_domain_terms
                    ),
                    *(f"Conflict evidence: {item}" for item in conflict_evidence),
                    *self._reference_evidence(text, insufficient_context),
                )
            )
        )
        reasons = []
        if domain_conflict:
            reasons.append(
                "The message assigns incompatible fruit and equity readings to Apple."
            )
        if scope_conflict:
            reasons.append(
                "The same interpretation is constrained to incompatible financial "
                "and physical scopes."
            )
        if domain_ambiguous:
            reasons.append(
                "Domain evidence supports multiple plausible interpretations."
            )
        if scope_ambiguous:
            reasons.append("Scope evidence does not resolve the highlighted subject.")
        if insufficient_context:
            reasons.append(
                "A contextual reference cannot be resolved from the supplied input."
            )

        return DomainScopeAmbiguity(
            ambiguity_present=ambiguity_present,
            ambiguity_type=ambiguity_type,
            possible_domains=possible_domains,
            possible_scopes=possible_scopes,
            conflicting_domains=conflicting_domains,
            conflicting_scopes=conflicting_scopes,
            possible_interpretations=interpretations,
            clarification_required=clarification,
            clarification_reason=" ".join(reasons) or None,
            confidence=(
                DomainConfidence.CONFLICTING
                if domain_conflict or scope_conflict
                else (
                    DomainConfidence.LOW
                    if clarification
                    else (
                        DomainConfidence.HIGH
                        if domain_candidates or detected_scopes
                        else DomainConfidence.UNKNOWN
                    )
                )
            ),
            domain_ambiguity_type=domain_type,
            scope_ambiguity_type=scope_type,
            evidence=evidence,
            conflict_evidence=conflict_evidence,
        )

    @classmethod
    def _domain_ambiguous(cls, text, result, unresolved_terms):
        if unresolved_terms:
            return True
        if not result.detection.is_ambiguous:
            return False
        ambiguous_signals = [
            item
            for item in result.detection.signals
            if item.source.startswith("ambiguous_")
        ]
        if ambiguous_signals:
            for signal in ambiguous_signals:
                if signal.source_span is None:
                    return True
                start = max(0, signal.source_span[0] - 32)
                end = min(len(text), signal.source_span[1] + 32)
                context = text[start:end]
                if not any(resolver.search(context) for resolver in _DOMAIN_RESOLVERS):
                    return True
            return False
        if cls._has_evidence_backed_interaction(text, result):
            return False
        return True

    @classmethod
    def _unresolved_domain_terms(cls, text):
        unresolved = []
        company_stock_context = re.search(
            r"\b(?:Apple|Amazon|Google|Microsoft)(?:'s)?\s+"
            r"(?:business|operations?).{0,32}\b(?:stock|shares?)\b",
            text,
            re.I,
        )
        for term, alternatives in _GENERIC_DOMAIN_TERMS.items():
            matches = tuple(re.finditer(rf"\b{re.escape(term)}\b", text, re.I))
            for match in matches:
                context = text[max(0, match.start() - 24) : match.end() + 24]
                if any(resolver.search(context) for resolver in _DOMAIN_RESOLVERS):
                    continue
                if term in {"apple", "stock"} and company_stock_context:
                    continue
                unresolved.append((match.group(), alternatives))
        return tuple(unresolved)

    @staticmethod
    def _reference_evidence(text, insufficient_context):
        if not insufficient_context:
            return ()
        match = re.search(r"\b(?:this|that|it|its|they|them|those|such)\b", text, re.I)
        return (f"Unresolved reference: {match.group()}",) if match else ()

    @staticmethod
    def _scope_ambiguity(text, result, context):
        lower = text.casefold()
        unresolved = []
        for term, scopes in _GENERIC_SCOPE_TERMS.items():
            for match in re.finditer(rf"\b{re.escape(term)}\b", lower):
                if is_negated_source_span(text, match.span()):
                    continue
                surrounding = text[max(0, match.start() - 16) : match.end() + 16]
                if _SCOPE_RESOLVERS.search(surrounding):
                    continue
                clause_start = (
                    max(
                        text.rfind(delimiter, 0, match.start())
                        for delimiter in (".", ";", "!", "?")
                    )
                    + 1
                )
                clause_endings = [
                    position
                    for delimiter in (".", ";", "!", "?")
                    if (position := text.find(delimiter, match.end())) >= 0
                ]
                clause_end = min(clause_endings, default=len(text))
                clause = text[clause_start:clause_end]
                has_scope_evidence = any(
                    item.source_span
                    and clause_start <= item.source_span[0] < clause_end
                    for item in result.scope_detection.evidence
                )
                if (
                    _RELATION.search(clause)
                    and _CONTEXTUAL_RELATION_CUES.search(clause)
                    and has_scope_evidence
                ):
                    continue
                unresolved.append((match.group(), scopes))

        if not unresolved:
            return False, set(), ()
        candidates = set()
        evidence = []
        for term, scopes in unresolved:
            candidates.update(scopes)
            evidence.append(f"Unresolved scope term: {term}")
        return True, candidates, tuple(evidence)

    @classmethod
    def _has_evidence_backed_interaction(cls, text, result):
        for match in _RELATION.finditer(text):
            left, right = cls._relation_sides(match, result)
            if left and right:
                return True
        return False

    @staticmethod
    def _relation_sides(match, result):
        before_boundary = max(
            text_position
            for text_position in (
                match.string.rfind(".", 0, match.start()),
                match.string.rfind(";", 0, match.start()),
                match.string.rfind("!", 0, match.start()),
                match.string.rfind("?", 0, match.start()),
                -1,
            )
        )
        after_candidates = [
            position
            for position in (
                match.string.find(".", match.end()),
                match.string.find(";", match.end()),
                match.string.find("!", match.end()),
                match.string.find("?", match.end()),
            )
            if position >= 0
        ]
        after_boundary = min(after_candidates, default=len(match.string))
        left = {
            item.domain
            for item in result.detection.signals
            if item.source_span
            and before_boundary < item.source_span[1] <= match.start()
        }
        right = {
            item.domain
            for item in result.detection.signals
            if item.source_span and match.end() <= item.source_span[0] < after_boundary
        }
        return left, right

    @classmethod
    def _domain_evidence(cls, result):
        if not result.detection.is_ambiguous:
            return ()
        return tuple(
            dict.fromkeys(
                f"{item.domain.value}: {item.evidence}"
                for item in result.detection.signals
            )
        )

    @staticmethod
    def _missing_context(text, result, context):
        has_context = bool(
            context
            and (
                context.previous_result
                or context.previous_text
                or context.previous_entities
                or context.previous_input
                or context.previous_sense2
            )
        )
        if has_context:
            return False
        return (
            bool(
                re.search(r"\b(?:this|that|it|its|they|them|those|such)\b", text, re.I)
            )
            and not result.scope_detection.evidence
        )

    @staticmethod
    def _interpretations(domains, scopes, result, scope_evidence):
        interpretations = []
        signals_by_domain = {}
        for signal in result.detection.signals:
            signals_by_domain.setdefault(signal.domain, []).append(signal.evidence)
        scope_evidence_by_type = {}
        for item in scope_evidence:
            scope_evidence_by_type.setdefault(item, [])
        for item in result.scope_detection.evidence:
            scope_evidence_by_type.setdefault(item.scope_type, []).append(item.evidence)
        interpretations.extend(
            ScopeInterpretation(
                domain=domain,
                description=f"Domain interpretation: {domain.value}.",
                evidence=tuple(dict.fromkeys(signals_by_domain.get(domain, ()))),
            )
            for domain in domains
        )
        interpretations.extend(
            ScopeInterpretation(
                scope=scope,
                description=f"Scope interpretation: {scope.value}.",
                evidence=tuple(dict.fromkeys(scope_evidence_by_type.get(scope, ()))),
            )
            for scope in scopes
        )
        return tuple(interpretations)
