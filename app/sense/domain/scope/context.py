from app.sense.domain.scope.knowledge import _CONTEXT_CUES
from app.sense.domain.scope.models import (
    EvidenceProvenance,
    ScopeContext,
    ScopeContextDetection,
    ScopeContextType,
    ScopeType,
)


class ScopeContextDetector:
    def detect(
        self,
        text: str,
        *,
        domain_result=None,
        scope_classification=None,
        sense2_result=None,
        source_input=None,
    ):
        contexts = []
        for context_type, pattern in _CONTEXT_CUES:
            for match in pattern.finditer(text):
                contexts.append(
                    ScopeContext(
                        context_type=context_type,
                        evidence=match.group(),
                        subject=match.group(),
                        source_span=match.span(),
                        source_text=text,
                    )
                )
        if source_input is not None and source_input.dates:
            for date in source_input.dates:
                contexts.append(
                    ScopeContext(
                        ScopeContextType.TEMPORAL,
                        date.text,
                        date.text,
                        source_text=source_input.raw_input,
                    )
                )
        if sense2_result is not None and sense2_result.constraints:
            for constraint in sense2_result.constraints.constraints:
                if constraint.source_text:
                    contexts.append(
                        ScopeContext(
                            ScopeContextType.TEMPORAL,
                            constraint.source_text,
                            constraint.value,
                            constraint.source_span,
                            EvidenceProvenance.SOURCE_TEXT,
                            text,
                        )
                    )
        if scope_classification is not None:
            scopes = {
                scope_classification.primary_scope,
                *scope_classification.secondary_scopes,
            }
            projection = {
                ScopeType.FINANCIAL_MARKET: (
                    ScopeContextType.FINANCIAL,
                    ScopeContextType.MARKET,
                ),
                ScopeType.COMMERCIAL_MARKET: (
                    ScopeContextType.COMMERCIAL,
                    ScopeContextType.MARKET,
                ),
                ScopeType.PHYSICAL_COMMERCE: (ScopeContextType.COMMERCIAL,),
                ScopeType.BUSINESS: (ScopeContextType.BUSINESS,),
                ScopeType.COMPANY: (ScopeContextType.BUSINESS,),
                ScopeType.INDUSTRY: (ScopeContextType.BUSINESS,),
                ScopeType.ECONOMIC: (ScopeContextType.ECONOMIC,),
                ScopeType.REGULATORY: (ScopeContextType.REGULATORY,),
                ScopeType.OPERATIONAL: (ScopeContextType.OPERATIONAL,),
                ScopeType.GEOGRAPHIC: (ScopeContextType.GEOGRAPHIC,),
            }
            for scope in scopes:
                for context_type in projection.get(scope, ()):
                    contexts.append(
                        ScopeContext(
                            context_type,
                            f"classified scope: {scope.value}",
                            scope.value,
                            provenance=EvidenceProvenance.DERIVED,
                            source_text=text,
                        )
                    )
        domain_types = (
            tuple(domain_result.classification.domains) if domain_result else ()
        )
        scopes = (
            {
                scope_classification.primary_scope,
                *scope_classification.secondary_scopes,
            }
            if scope_classification is not None
            else set()
        )
        supported_cross_domain = ScopeType.CROSS_DOMAIN in scopes
        interaction_evidence = None
        if supported_cross_domain and scope_classification is not None:
            interaction_evidence = scope_classification.direction or next(
                (
                    item.relation
                    for item in scope_classification.relationships
                    if item.relation == "compares"
                    and item.source_scope != item.target_scope
                ),
                None,
            )
        return ScopeContextDetection(
            contexts=tuple(dict.fromkeys(contexts)),
            cross_domain=supported_cross_domain,
            interaction_evidence=interaction_evidence,
            domain_types=domain_types,
        )
