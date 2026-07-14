"""discover sub-package — ATS source registry.

Add new sources here as they are implemented.  Each entry maps a source
name string to its ``discover(slugs: list[str]) -> list[Company]`` callable.

Usage (in cli.py)::

    from app.discover import SOURCE_REGISTRY
    fn = SOURCE_REGISTRY["greenhouse"]
    companies = fn(["acmecorp", "stripe"])
"""

from __future__ import annotations

from typing import Callable

from app.models import Company

# Lazy imports keep startup time fast; the functions are referenced, not called.
from app.discover import greenhouse, lever, remoteok

SOURCE_REGISTRY: dict[str, Callable[[list[str]], list[Company]]] = {
    "greenhouse": greenhouse.discover,
    "lever": lever.discover,
    # NOTE: remoteok.discover has a different signature — it takes `limit: int`
    # instead of a slug list.  The cli.py discover command branches on this
    # source name explicitly rather than calling it through the registry.
    # It is still registered here so source-name validation works.
    "remoteok": remoteok.discover,  # type: ignore[dict-item]
    # "wwr": wwr.discover,  # added in step 1.5
}

__all__ = ["SOURCE_REGISTRY"]
