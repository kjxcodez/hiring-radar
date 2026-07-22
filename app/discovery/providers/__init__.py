"""Discovery providers sub-package.

Importing this package triggers all provider self-registrations via the
``@ProviderRegistry.register(...)`` decorators on each provider class.
"""

from app.discovery.providers import (
    greenhouse,
    lever,
    ashby,
    workable,
    bamboohr,
    remoteok,
    wwr,
)

__all__ = [
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "bamboohr",
    "remoteok",
    "wwr",
]
