"""Seed-slug file loader for the discover stage.

Until a proper company-discovery crawler exists (Phase 3.4), the discover
command reads company slugs/tokens from plain-text files:

    output/seed_slugs_{source}.txt

Format — one slug per line; lines starting with ``#`` are comments:

    # Greenhouse board tokens
    stripe
    notion
    acmecorp

These files are never committed to git (covered by ``output/*`` in
``.gitignore``).  Create them manually before running ``discover``.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.config import settings


def load_seed_slugs(sources: list[str]) -> dict[str, list[str]]:
    """Return a mapping of source → slug list, read from per-source seed files.

    For each source in *sources*, looks for::

        {settings.output_dir}/seed_slugs_{source}.txt

    If the file exists, parses it (strips whitespace, drops blank lines and
    lines beginning with ``#``) and returns the resulting slug list.

    If the file does not exist, logs an ``INFO`` message explaining where
    to create it, and returns an empty list for that source — the caller
    will simply skip that source rather than erroring.

    Args:
        sources: List of source names, e.g. ``["greenhouse", "lever"]``.

    Returns:
        Dict mapping each source name to its (possibly empty) slug list.
    """
    result: dict[str, list[str]] = {}

    for source in sources:
        seed_path: Path = settings.output_dir / f"seed_slugs_{source}.txt"

        if not seed_path.exists():
            logger.info(
                "discover: no seed file for '{source}' — "
                "create {path} to add slugs (one per line, # for comments)",
                source=source,
                path=seed_path,
            )
            result[source] = []
            continue

        slugs: list[str] = []
        for raw_line in seed_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            slugs.append(line)

        logger.info(
            "discover: loaded {n} slug(s) for '{source}' from {path}",
            n=len(slugs),
            source=source,
            path=seed_path,
        )
        result[source] = slugs

    return result
