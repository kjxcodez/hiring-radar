"""Seed-slug file loader and manual-lead resolution for the discover stage.

Reads company slugs or resolves manual company names by probing public ATS platforms.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger

from app.config import settings
from app.models import Company


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


def resolve_seed_companies(seed_file: Path) -> list[Company]:
    """Resolve manually collected company names to working slugs on ATS platforms.

    Probes Greenhouse, Lever, Ashby, Workable, and BambooHR sequentially.
    If a company name cannot be resolved, a bare Company is returned with a note.

    Args:
        seed_file: Path to a plain text file containing one company name per line.

    Returns:
        List of Company objects (resolved or unresolved).
    """
    if not seed_file.exists():
        logger.warning("Seed file {path} does not exist.", path=seed_file)
        return []

    names: list[str] = []
    for raw_line in seed_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)

    logger.info("Resolving {n} company name(s) from seed file: {path}", n=len(names), path=seed_file)

    # Import discover modules to perform the resolution probes
    from app.discover import ashby, bamboohr, greenhouse, lever, workable

    platforms = [
        ("greenhouse", greenhouse.discover),
        ("lever", lever.discover),
        ("ashby", ashby.discover),
        ("workable", workable.discover),
        ("bamboohr", bamboohr.discover),
    ]

    results: list[Company] = []
    total_probes = 0

    for name in names:
        # Derive plausible slug guesses (up to 3 unique guesses)
        g1 = name.lower().replace(" ", "-")
        g2 = name.lower().replace(" ", "")
        g3 = name.lower()

        guesses: list[str] = []
        for g in [g1, g2, g3]:
            g_clean = g.strip()
            if g_clean and g_clean not in guesses:
                guesses.append(g_clean)

        resolved_company = None

        for guess in guesses:
            if resolved_company is not None:
                break
            for platform_name, discover_fn in platforms:
                total_probes += 1
                logger.debug(
                    "Probing platform '{platform}' with guess '{guess}' for '{name}'",
                    platform=platform_name,
                    guess=guess,
                    name=name,
                )
                try:
                    # Call discover_fn with a single-item list
                    companies = discover_fn([guess])
                    if companies:
                        resolved_company = companies[0]
                        logger.info(
                            "Successfully resolved '{name}' to '{platform}' with slug '{guess}'",
                            name=name,
                            platform=platform_name,
                            guess=guess,
                        )
                        break
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Failed probe on '{platform}' for '{guess}': {exc}",
                        platform=platform_name,
                        guess=guess,
                        exc=exc,
                    )

        if resolved_company is not None:
            results.append(resolved_company)
        else:
            now = datetime.now()
            bare_co = Company(
                name=name,
                jobs=[],
                notes=["unresolved_seed: no ATS match found, needs manual follow-up"],
                discovered_at=now,
                last_updated=now,
            )
            results.append(bare_co)
            logger.info("Could not resolve '{name}' to any platform. Created bare company.", name=name)

    logger.info("Seed resolution complete. Total probe-calls made: {total_probes}", total_probes=total_probes)
    return results
