"""Async discovery coordinator — the core of the Phase 2.0 engine.

Orchestrates concurrent provider execution, collects and merges results,
handles provider failures in isolation, and emits progress events.

The coordinator exposes a **synchronous** ``discover()`` entry point that
bridges to ``asyncio`` internally.  All callers above it (CLI, DiscoverStep,
DiscoveryService) remain fully synchronous — no ``async``/``await``
propagation required.

Architecture::

    coordinator.discover(...)       ← synchronous entry point
        asyncio.run(_discover_async)
            asyncio.gather(
                _run_provider("greenhouse", ...),
                _run_provider("lever", ...),
                _run_provider("remoteok", ...),
                ...
            )
            → merge results → filter → return

Usage::

    from app.discovery.coordinator import DiscoveryCoordinator

    coordinator = DiscoveryCoordinator(settings=settings)
    companies = coordinator.discover(
        sources=["greenhouse", "lever"],
        slugs_by_source={"greenhouse": ["stripe"], "lever": ["notion"]},
        limit=100,
    )
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional, TYPE_CHECKING

from loguru import logger

from app.models import Company
from app.discovery.registry import ProviderRegistry
from app.discovery.rate_limit import build_limiter
from app.discovery.deduplication import Deduplicator
from app.discovery.filters import DiscoveryFilter
from app.discovery.errors import ProviderNotFoundError

# Trigger all provider self-registrations
import app.discovery.providers  # noqa: F401

if TYPE_CHECKING:
    from app.config import Settings
    from app.profiles import SearchProfile


class DiscoveryCoordinator:
    """Concurrent provider coordinator for the discovery pipeline.

    Runs all requested providers in parallel using ``asyncio.gather``.
    Individual provider failures are caught and logged — they never abort
    other providers.

    Args:
        settings:        Application settings (for future rate-limit config).
        registry:        Optional custom :class:`ProviderRegistry` subclass.
                         Defaults to the global ``ProviderRegistry``.
        max_concurrency: Global limit on the number of providers running at
                         the same time.  Per-provider concurrency is
                         controlled separately by ``AsyncRateLimiter``.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        registry: type[ProviderRegistry] = ProviderRegistry,
        max_concurrency: int = 7,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.max_concurrency = max_concurrency
        self._deduplicator = Deduplicator()
        self._filter = DiscoveryFilter()

    # ------------------------------------------------------------------
    # Public synchronous entry point
    # ------------------------------------------------------------------

    def discover(
        self,
        sources: list[str],
        slugs_by_source: dict[str, list[str]],
        limit: int = 100,
        *,
        remote: Optional[bool] = None,
        country: Optional[str] = None,
        keyword: Optional[str] = None,
        exclude: Optional[str] = None,
        days: Optional[int] = None,
        profile: Optional["SearchProfile"] = None,
        progress_callback: Optional[Callable[[str, list[Company]], None]] = None,
    ) -> list[Company]:
        """Discover companies from *sources* concurrently.

        This method is **synchronous** — it bridges to ``asyncio`` internally
        so callers do not need to be in an async context.

        Args:
            sources:           List of provider names to query, e.g.
                               ``["greenhouse", "lever"]``.
            slugs_by_source:   Dict mapping each source to its slug list.
                               Feed-based providers (remoteok, wwr) should
                               map to ``[]``.
            limit:             Maximum number of jobs/companies per provider.
            remote:            Filter flag for remote-only jobs.
            country:           Country filter for job location.
            keyword:           Title keyword filter.
            exclude:           Title exclusion term.
            days:              Maximum age of job postings in days.
            profile:           Search profile with compound criteria.
            progress_callback: Called with ``(source_name, companies)`` after
                               each provider completes.  Used to emit progress
                               events to the workflow layer.

        Returns:
            Deduplicated list of :class:`~app.models.Company` objects.
        """
        if not sources:
            return []

        # Validate sources early — fail fast on typos
        unknown = [s for s in sources if not self.registry.has(s)]
        if unknown:
            logger.warning(
                "coordinator: unknown source(s) {unknown} — skipping",
                unknown=unknown,
            )
            sources = [s for s in sources if s not in unknown]
            if not sources:
                return []

        return asyncio.run(
            self._discover_async(
                sources=sources,
                slugs_by_source=slugs_by_source,
                limit=limit,
                remote=remote,
                country=country,
                keyword=keyword,
                exclude=exclude,
                days=days,
                profile=profile,
                progress_callback=progress_callback,
            )
        )

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    async def _discover_async(
        self,
        sources: list[str],
        slugs_by_source: dict[str, list[str]],
        limit: int,
        remote: Optional[bool],
        country: Optional[str],
        keyword: Optional[str],
        exclude: Optional[str],
        days: Optional[int],
        profile: Optional["SearchProfile"],
        progress_callback: Optional[Callable],
    ) -> list[Company]:
        """Run all providers concurrently and aggregate results."""
        # Global concurrency cap across all providers
        global_sem = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            self._run_provider(
                source=src,
                slugs=slugs_by_source.get(src, []),
                limit=limit,
                global_sem=global_sem,
                progress_callback=progress_callback,
            )
            for src in sources
        ]

        # gather with return_exceptions=True ensures one failure doesn't
        # cancel other providers
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_companies: list[Company] = []
        for src, result in zip(sources, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "coordinator: provider '{src}' raised an exception — {exc}",
                    src=src,
                    exc=result,
                )
            elif isinstance(result, list):
                all_companies.extend(result)

        logger.info(
            "coordinator: {n} total companies before deduplication",
            n=len(all_companies),
        )

        # Cross-provider deduplication (same company from Greenhouse + Lever)
        deduplicated = self._deduplicator.dedupe_incoming(all_companies)

        # Apply filters before returning to the caller
        filtered = self._filter.apply(
            deduplicated,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
            profile=profile,
        )

        logger.info(
            "coordinator: {n} companies after dedup + filter",
            n=len(filtered),
        )
        return filtered

    async def _run_provider(
        self,
        source: str,
        slugs: list[str],
        limit: int,
        global_sem: asyncio.Semaphore,
        progress_callback: Optional[Callable],
    ) -> list[Company]:
        """Execute a single provider with global concurrency control."""
        async with global_sem:
            logger.info("coordinator: starting provider '{source}'", source=source)

            try:
                provider = self.registry.get(source)
            except ProviderNotFoundError as exc:
                logger.warning("coordinator: {exc}", exc=exc)
                return []

            try:
                container = getattr(self.settings, "container", None) if self.settings else None
                if container and hasattr(container, "sync_engine") and container.sync_engine:
                    # Sync and reconcile via SyncEngine
                    await container.sync_engine.sync_provider(source, slugs, limit)
                    # Load reconciled companies from the database
                    all_db = container.company_repo.load_all()
                    companies = []
                    for c in all_db:
                        # Skip soft-deleted companies
                        if any(n.startswith("company_removed:") for n in c.notes):
                            continue
                        if c.ats_platform == source:
                            companies.append(c)
                        elif not c.ats_platform and any(j.source == source for j in c.jobs):
                            companies.append(c)
                else:
                    # Fallback to direct provider query (e.g. in simple tests)
                    limiter = build_limiter(source)
                    async with limiter:
                        companies = await provider.discover(
                            slugs=slugs,
                            limit=limit,
                        )
            except asyncio.CancelledError:
                logger.info(
                    "coordinator: provider '{source}' was cancelled",
                    source=source,
                )
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "coordinator: provider '{source}' failed — {exc}",
                    source=source,
                    exc=exc,
                )
                return []


            logger.info(
                "coordinator: provider '{source}' complete — {n} companies",
                source=source,
                n=len(companies),
            )

            if progress_callback:
                try:
                    progress_callback(source, companies)
                except Exception:  # noqa: BLE001
                    pass  # Progress callbacks must never crash the pipeline

            return companies
