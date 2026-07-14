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
from app.discover import greenhouse, lever

SOURCE_REGISTRY: dict[str, Callable[[list[str]], list[Company]]] = {
    "greenhouse": greenhouse.discover,
    "lever": lever.discover,
    # "remoteok": remoteok.discover,  # added in step 1.4
    # "wwr":      wwr.discover,       # added in step 1.5
}

__all__ = ["SOURCE_REGISTRY"]
