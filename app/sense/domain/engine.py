from dataclasses import replace

from app.sense.domain.ambiguity.models import AmbiguityType
from app.sense.domain.ambiguity.detector import DomainScopeAmbiguityDetector
from app.sense.domain.classification.classifier import DomainClassifier
from app.sense.domain.confidence.evaluator import DomainScopeConfidenceEvaluator
from app.sense.domain.correction.detector import DomainScopeCorrectionDetector
from app.sense.domain.correction.updater import DomainScopeCorrectionUpdater
from app.sense.domain.detection.detector import DomainDetector
from app.sense.domain.hierarchy.resolver import DomainHierarchyResolver
from app.sense.domain.models import (
    DomainContext,
    DomainUnderstandingResult,
    build_explanation,
)
from app.sense.domain.multi_domain.detector import MultiDomainDetector
from app.sense.domain.scope.classifier import ScopeClassifier
from app.sense.domain.scope.context import ScopeContextDetector
from app.sense.domain.scope.detector import ScopeDetector
from app.sense.domain.scope.hierarchy import ScopeHierarchyResolver
from app.sense.input.models import InputUnderstandingResult
from app.sense.intent.models import Sense2Result


class DomainUnderstandingEngine:
    """Coordinates SENSE-3 domain, scope, and interpretation components."""

    def __init__(
        self,
        detector: DomainDetector | None = None,
        classifier: DomainClassifier | None = None,
        hierarchy_resolver: DomainHierarchyResolver | None = None,
        multi_domain_detector: MultiDomainDetector | None = None,
        scope_detector: ScopeDetector | None = None,
        scope_classifier: ScopeClassifier | None = None,
        scope_hierarchy_resolver: ScopeHierarchyResolver | None = None,
        scope_context_detector: ScopeContextDetector | None = None,
        ambiguity_detector: DomainScopeAmbiguityDetector | None = None,
        confidence_evaluator: DomainScopeConfidenceEvaluator | None = None,
        correction_detector: DomainScopeCorrectionDetector | None = None,
        correction_updater: DomainScopeCorrectionUpdater | None = None,
    ) -> None:
        self.detector = detector or DomainDetector()
        self.classifier = classifier or DomainClassifier()
        self.hierarchy_resolver = hierarchy_resolver or DomainHierarchyResolver()
        self.multi_domain_detector = multi_domain_detector or MultiDomainDetector()
        self.scope_detector = scope_detector or ScopeDetector()
        self.scope_classifier = scope_classifier or ScopeClassifier()
        self.scope_hierarchy_resolver = (
            scope_hierarchy_resolver or ScopeHierarchyResolver()
        )
        self.scope_context_detector = scope_context_detector or ScopeContextDetector()
        self.ambiguity_detector = ambiguity_detector or DomainScopeAmbiguityDetector()
        self.confidence_evaluator = (
            confidence_evaluator or DomainScopeConfidenceEvaluator()
        )
        self.correction_detector = (
            correction_detector or DomainScopeCorrectionDetector()
        )
        self.correction_updater = correction_updater or DomainScopeCorrectionUpdater()

    def understand(
        self,
        value: str | InputUnderstandingResult | Sense2Result,
        *,
        sense2_result: Sense2Result | None = None,
        context: DomainContext | None = None,
    ) -> DomainUnderstandingResult:
        if isinstance(value, Sense2Result):
            sense2_result = value
            source_input = value.source_input
            raw_text = value.raw_text
            normalized_text = value.normalized_text
        elif isinstance(value, InputUnderstandingResult):
            source_input = value
            raw_text = value.raw_input
            normalized_text = value.normalized_text or raw_text
        else:
            source_input = None
            raw_text = str(value)
            normalized_text = raw_text

        if sense2_result is not None and not normalized_text:
            normalized_text = sense2_result.normalized_text
        detection = self.detector.detect(
            normalized_text,
            source_input=source_input,
            sense2_result=sense2_result,
            context=context,
        )
        classification = self.classifier.classify(detection)
        hierarchy = self.hierarchy_resolver.resolve(classification.domains)
        multi_domain = self.multi_domain_detector.detect(
            normalized_text, classification, detection
        )
        domain_result = DomainUnderstandingResult(
            raw_text=raw_text,
            normalized_text=normalized_text,
            detection=detection,
            classification=classification,
            hierarchy=hierarchy,
            multi_domain=multi_domain,
            source_input=source_input,
            source_sense2=sense2_result,
        )
        scope_detection = self.scope_detector.detect(
            normalized_text,
            domain_result=domain_result,
            source_input=source_input,
            sense2_result=sense2_result,
            context=context,
        )
        scope_classification = self.scope_classifier.classify(
            scope_detection,
            text=normalized_text,
            domain_result=domain_result,
            sense2_result=sense2_result,
        )
        scope_hierarchy = self.scope_hierarchy_resolver.resolve(scope_classification)
        scope_context = self.scope_context_detector.detect(
            normalized_text,
            domain_result=domain_result,
            scope_classification=scope_classification,
            sense2_result=sense2_result,
            source_input=source_input,
        )
        result = replace(
            domain_result,
            scope_detection=scope_detection,
            scope_classification=scope_classification,
            scope_hierarchy=scope_hierarchy,
            scope_context=scope_context,
        )
        correction = self.correction_detector.detect(normalized_text, result, context)
        result = self.correction_updater.update(result, context, correction)
        if correction.detected:
            result = replace(
                result,
                hierarchy=self.hierarchy_resolver.resolve(
                    result.classification.domains
                ),
                multi_domain=self.multi_domain_detector.detect(
                    normalized_text, result.classification, result.detection
                ),
                scope_hierarchy=self.scope_hierarchy_resolver.resolve(
                    result.scope_classification
                ),
            )
            result = replace(
                result,
                scope_context=self.scope_context_detector.detect(
                    normalized_text,
                    domain_result=result,
                    scope_classification=result.scope_classification,
                    sense2_result=sense2_result,
                    source_input=source_input,
                ),
            )
        ambiguity = self.ambiguity_detector.detect(normalized_text, result, context)
        confidence = self.confidence_evaluator.evaluate(result, ambiguity, correction)
        result = replace(
            result,
            multi_domain=replace(
                result.multi_domain,
                is_ambiguous=(ambiguity.domain_ambiguity_type != AmbiguityType.NONE),
            ),
            ambiguity=ambiguity,
            confidence=confidence,
            correction=correction,
            requires_clarification=ambiguity.clarification_required,
        )
        return replace(result, explanation=build_explanation(result))


DOMAIN_SENSE = DomainUnderstandingEngine()
