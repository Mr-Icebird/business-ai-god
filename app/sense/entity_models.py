from dataclasses import dataclass, field
from enum import Enum


class EntityMentionType(str, Enum):
    """
    Describes how an entity appears in the owner's message.
    """

    EXPLICIT = "explicit"
    REFERENCE = "reference"
    IMPLICIT = "implicit"


class EntityReferenceType(str, Enum):
    """
    Describes the type of reference made to a previous entity.
    """

    PRONOUN = "pronoun"
    DEMONSTRATIVE = "demonstrative"
    DESCRIPTIVE = "descriptive"
    NONE = "none"


class RelationshipType(str, Enum):
    """
    Describes a relationship between the current message and
    a previously established entity or concept.
    """

    REFERS_TO = "refers_to"
    ATTRIBUTE_OF = "attribute_of"
    RELATED_TO = "related_to"
    COMPARISON_WITH = "comparison_with"
    NONE = "none"


@dataclass(frozen=True)
class EntityReference:
    """
    Represents a reference from the current message to another
    entity or concept already established in context.
    """

    text: str
    reference_type: EntityReferenceType
    refers_to: str | None = None
    relationship: RelationshipType = RelationshipType.NONE
    confidence: float = 0.0

    def to_dict(self) -> dict:
        """Convert the entity reference into a serializable dictionary."""

        return {
            "text": self.text,
            "reference_type": self.reference_type.value,
            "refers_to": self.refers_to,
            "relationship": self.relationship.value,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class EntityMention:
    """
    Represents one entity mention detected in a message.
    """

    text: str
    mention_type: EntityMentionType = EntityMentionType.EXPLICIT
    entity_id: str | None = None
    entity_type: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict:
        """Convert the entity mention into a serializable dictionary."""

        return {
            "text": self.text,
            "mention_type": self.mention_type.value,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Relationship:
    """
    Represents a relationship between concepts or entities.
    """

    source: str
    relationship: RelationshipType
    target: str

    def to_dict(self) -> dict:
        """Convert the relationship into a serializable dictionary."""

        return {
            "source": self.source,
            "relationship": self.relationship.value,
            "target": self.target,
        }


@dataclass(frozen=True)
class EntitySenseResult:
    """
    Structured result produced by the entity/reference layer of SENSE.
    """

    mentions: tuple[EntityMention, ...] = field(default_factory=tuple)
    references: tuple[EntityReference, ...] = field(default_factory=tuple)
    relationships: tuple[Relationship, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """Convert the entity sense result into a serializable dictionary."""

        return {
            "mentions": [
                mention.to_dict()
                for mention in self.mentions
            ],
            "references": [
                reference.to_dict()
                for reference in self.references
            ],
            "relationships": [
                relationship.to_dict()
                for relationship in self.relationships
            ],
        }
