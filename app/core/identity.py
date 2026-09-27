from dataclasses import dataclass


@dataclass(frozen=True)
class BAIGIdentity:
    """Official identity information for the BAIG system."""

    name: str = "BUSINESS AI GOD"
    short_name: str = "BAIG"
    version: str = "0.1.0"
    environment: str = "development"


IDENTITY = BAIGIdentity()
