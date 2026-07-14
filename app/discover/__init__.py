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
from app.discover import ashby, greenhouse, lever, remoteok, wwr

SOURCE_REGISTRY: dict[str, Callable[[list[str]], list[Company]]] = {
    "ashby": ashby.discover,
    "greenhouse": greenhouse.discover,
    "lever": lever.discover,
    # NOTE: remoteok.discover has a different signature — it takes `limit: int`
    # instead of a slug list.  The cli.py discover command branches on this
    # source name explicitly rather than calling it through the registry.
    # It is still registered here so source-name validation works.
    "remoteok": remoteok.discover,  # type: ignore[dict-item]
    # NOTE: wwr.discover also takes `limit: int` (feed-based, not slug-based).
    # Same branching logic applies in cli.py.
    "wwr": wwr.discover,  # type: ignore[dict-item]
}

__all__ = ["SOURCE_REGISTRY"]
