from dataclasses import dataclass
from enum import Enum


class ComponentStatus(str, Enum):
    """Lifecycle state for a BAIG core component."""

    PLANNED = "planned"
    INITIALIZED = "initialized"
    OPERATIONAL = "operational"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass(frozen=True)
class ComponentDefinition:
    """Definition of a BAIG core component."""

    name: str
    display_name: str
    status: ComponentStatus = ComponentStatus.PLANNED


CORE_COMPONENTS = (
    ComponentDefinition("sense", "Sense"),
    ComponentDefinition("memory", "Memory"),
    ComponentDefinition("knowledge_system", "Knowledge System"),
    ComponentDefinition(
        "entity_world_intelligence",
        "Entity / World Intelligence",
    ),
    ComponentDefinition("research_engine", "Research Engine"),
    ComponentDefinition("economic_taxonomy", "Economic Taxonomy"),
    ComponentDefinition("analysis_boards", "Nine Analysis Boards"),
    ComponentDefinition("hypothesis_engine", "Hypothesis Engine"),
    ComponentDefinition("testing_lab", "Testing Lab"),
    ComponentDefinition(
        "financial_intelligence_memory",
        "Financial Intelligence Memory",
    ),
    ComponentDefinition("agent_factory", "Agent Factory"),
)
