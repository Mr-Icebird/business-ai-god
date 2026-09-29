import re

from app.sense.entity_models import (
    EntityMention,
    EntityMentionType,
    EntityReference,
    EntityReferenceType,
    EntitySenseResult,
    Relationship,
    RelationshipType,
)


class EntitySenseEngine:
    """
    Detects entity mentions and references in the owner's message.

    This engine does not maintain permanent knowledge about entities.
    It interprets the current message against conversational information
    supplied by the caller.
    """

    PRONOUN_PATTERNS = {
        "it": EntityReferenceType.PRONOUN,
        "its": EntityReferenceType.PRONOUN,
        "they": EntityReferenceType.PRONOUN,
        "them": EntityReferenceType.PRONOUN,
        "their": EntityReferenceType.PRONOUN,
        "this": EntityReferenceType.DEMONSTRATIVE,
        "that": EntityReferenceType.DEMONSTRATIVE,
        "these": EntityReferenceType.DEMONSTRATIVE,
        "those": EntityReferenceType.DEMONSTRATIVE,
    }

    DESCRIPTIVE_PATTERNS = (
        "the company",
        "the business",
        "the market",
        "the asset",
        "the instrument",
        "the commodity",
        "the stock",
        "the currency",
        "the product",
    )

    ATTRIBUTE_PATTERNS = (
        "revenue",
        "sales",
        "profit",
        "price",
        "cost",
        "supply",
        "demand",
        "production",
        "consumption",
        "volume",
        "market share",
        "growth",
    )

    NON_ENTITY_WORDS = {
        "tell",
        "show",
        "give",
        "explain",
        "what",
        "about",
        "how",
        "why",
        "when",
        "where",
        "which",
        "who",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "could",
        "would",
        "should",
        "will",
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "its",
        "it",
        "they",
        "them",
        "their",
        "and",
        "or",
        "to",
        "for",
        "of",
        "in",
        "on",
        "with",
        "from",
        "about",
        "please",
    }

    def understand(
        self,
        message: str,
        previous_entity: str | None = None,
    ) -> EntitySenseResult:
        """
        Analyze the current message for entity references and mentions.

        previous_entity is supplied by the conversation/context layer.
        The engine does not invent an entity when one is unavailable.
        """

        if not message or not message.strip():
            return EntitySenseResult()

        normalized = message.strip()

        references = self._detect_references(normalized)

        resolved_references = []
        relationships = []

        for reference in references:
            resolved = self._resolve_reference(
                reference,
                normalized,
                previous_entity,
            )

            relationship = self._infer_relationship(
                normalized,
                resolved.refers_to,
            )

            if relationship != RelationshipType.NONE:
                resolved = EntityReference(
                    text=resolved.text,
                    reference_type=resolved.reference_type,
                    refers_to=resolved.refers_to,
                    relationship=relationship,
                    confidence=resolved.confidence,
                )

            resolved_references.append(resolved)

            if resolved.refers_to and relationship != RelationshipType.NONE:
                relationships.append(
                    Relationship(
                        source=resolved.refers_to,
                        relationship=relationship,
                        target=self._relationship_target(
                            normalized,
                            relationship,
                        ),
                    )
                )

        mentions = self._detect_explicit_mentions(
            normalized,
            references,
        )

        return EntitySenseResult(
            mentions=tuple(mentions),
            references=tuple(resolved_references),
            relationships=tuple(relationships),
        )

    def _detect_references(
        self,
        message: str,
    ) -> list[EntityReference]:
        references: list[EntityReference] = []
        lowered = message.lower()

        for word, reference_type in self.PRONOUN_PATTERNS.items():
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                references.append(
                    EntityReference(
                        text=word,
                        reference_type=reference_type,
                    )
                )

        for phrase in self.DESCRIPTIVE_PATTERNS:
            if phrase in lowered:
                references.append(
                    EntityReference(
                        text=phrase,
                        reference_type=EntityReferenceType.DESCRIPTIVE,
                    )
                )

        return references

    def _resolve_reference(
        self,
        reference: EntityReference,
        message: str,
        previous_entity: str | None,
    ) -> EntityReference:
        if not previous_entity or not previous_entity.strip():
            return reference

        confidence = self._resolution_confidence(
            reference,
            message,
        )

        if confidence <= 0:
            return reference

        return EntityReference(
            text=reference.text,
            reference_type=reference.reference_type,
            refers_to=previous_entity,
            relationship=reference.relationship,
            confidence=confidence,
        )

    def _resolution_confidence(
        self,
        reference: EntityReference,
        message: str,
    ) -> float:
        if reference.reference_type == EntityReferenceType.PRONOUN:
            if reference.text in {"its", "their", "them"}:
                return 0.90

            if reference.text in {"it", "they"}:
                return 0.85

        if reference.reference_type == EntityReferenceType.DEMONSTRATIVE:
            if reference.text in {"this", "that"}:
                return 0.75

            if reference.text in {"these", "those"}:
                return 0.70

        if reference.reference_type == EntityReferenceType.DESCRIPTIVE:
            return 0.65

        return 0.0

    def _infer_relationship(
        self,
        message: str,
        entity: str | None,
    ) -> RelationshipType:
        lowered = message.lower()

        if any(
            re.search(
                rf"\b{re.escape(attribute)}\b",
                lowered,
            )
            for attribute in self.ATTRIBUTE_PATTERNS
        ):
            return RelationshipType.ATTRIBUTE_OF

        if any(
            word in lowered
            for word in (
                "compare",
                "versus",
                "vs",
                "difference",
                "different",
            )
        ):
            return RelationshipType.COMPARISON_WITH

        if any(
            word in lowered
            for word in (
                "about",
                "regarding",
                "related",
                "concerning",
            )
        ):
            return RelationshipType.RELATED_TO

        if entity and entity.lower() in lowered:
            return RelationshipType.REFERS_TO

        return RelationshipType.NONE

    @staticmethod
    def _relationship_target(
        message: str,
        relationship: RelationshipType,
    ) -> str:
        lowered = message.lower()

        if relationship == RelationshipType.ATTRIBUTE_OF:
            for attribute in EntitySenseEngine.ATTRIBUTE_PATTERNS:
                if re.search(
                    rf"\b{re.escape(attribute)}\b",
                    lowered,
                ):
                    return attribute

        if relationship == RelationshipType.COMPARISON_WITH:
            return "comparison"

        if relationship == RelationshipType.RELATED_TO:
            return "related_topic"

        return "current_message"

    def _detect_explicit_mentions(
        self,
        message: str,
        references: list[EntityReference],
    ) -> list[EntityMention]:
        """
        Detect conservative explicit entity candidates.

        This layer intentionally avoids treating ordinary words and
        analytical attributes as entities. Full entity recognition and
        classification will later belong to Entity / World Intelligence.
        """

        tokens = re.findall(
            r"[A-Za-z0-9][A-Za-z0-9&'_-]*",
            message,
        )

        if not tokens:
            return []

        reference_texts = {
            reference.text.lower()
            for reference in references
        }

        attribute_texts = {
            attribute.lower()
            for attribute in self.ATTRIBUTE_PATTERNS
        }

        stop_words = self.NON_ENTITY_WORDS | {
            "me",
            "please",
            "tell",
            "show",
            "give",
            "explain",
            "revenue",
            "sales",
            "profit",
            "price",
            "cost",
            "supply",
            "demand",
            "production",
            "consumption",
            "volume",
            "growth",
            "market",
        }

        candidates = []

        for token in tokens:
            lowered = token.lower()

            if lowered in reference_texts:
                continue

            if lowered in attribute_texts:
                continue

            if lowered in stop_words:
                continue

            # A conservative first-stage candidate rule:
            # preserve explicitly capitalized words, while leaving
            # classification to the Entity / World Intelligence layer.
            if token[0].isupper():
                candidates.append(token)

        if not candidates:
            return []

        return [
            EntityMention(
                text=" ".join(candidates),
                mention_type=EntityMentionType.EXPLICIT,
            )
        ]



ENTITY_SENSE = EntitySenseEngine()
