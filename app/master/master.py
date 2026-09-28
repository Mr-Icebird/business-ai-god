from dataclasses import dataclass, field

from app.core.identity import IDENTITY
from app.master.registry import CORE_COMPONENTS, ComponentStatus


@dataclass
class BAIGMaster:
    """
    Central coordinator for BUSINESS AI GOD.

    Master coordinates BAIG subsystems but does not contain
    the intelligence logic belonging to those subsystems.
    """

    identity_name: str = IDENTITY.name
    identity_version: str = IDENTITY.version
    environment: str = IDENTITY.environment
    components: tuple = field(default_factory=lambda: CORE_COMPONENTS)

    def status(self) -> dict:
        """Return the current status of BAIG Master and its components."""

        return {
            "system": self.identity_name,
            "version": self.identity_version,
            "component": "BAIG Master",
            "status": "operational",
            "environment": self.environment,
            "components": self.component_statuses(),
        }

    def component_statuses(self) -> dict:
        """Return the current lifecycle state of each BAIG core component."""

        return {
            component.name: {
                "display_name": component.display_name,
                "status": component.status.value,
            }
            for component in self.components
        }

    def get_component(self, name: str):
        """Return a registered component by its internal name."""

        for component in self.components:
            if component.name == name:
                return component

        return None


MASTER = BAIGMaster()
