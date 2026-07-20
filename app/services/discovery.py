from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable
from loguru import logger

from app.models import Company
from app.discover import SOURCE_REGISTRY
from app.discover import remoteok as _remoteok_mod
from app.discover import wwr as _wwr_mod
from app.discover.seed import load_seed_slugs
from app.filters import apply_filters
from app.saved_search import SavedSearch, load_saved_searches, save_saved_searches
from app.repositories import CompanyRepository, ProfileRepository
from app.config import Settings
from app.profiles import SearchProfile

class DiscoveryService:
    def __init__(self, company_repo: CompanyRepository, profile_repo: ProfileRepository, settings: Settings):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
        self.settings = settings

    def discover(
        self,
        sources: str,
        limit: int = 100,
        profile: Optional[SearchProfile] = None,
        remote: Optional[bool] = None,
        country: Optional[str] = None,
        keyword: Optional[str] = None,
        exclude: Optional[str] = None,
        days: Optional[int] = None,
        seed_companies: Optional[list[Company]] = None,
        event_callback: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """Perform discovery from selected sources, merge with existing database, apply filters, and persist."""
        import sys
        local_registry = SOURCE_REGISTRY
        local_load_seed_slugs = load_seed_slugs

        if "app.cli" in sys.modules:
            cli_mod = sys.modules["app.cli"]
            local_registry = getattr(cli_mod, "SOURCE_REGISTRY", local_registry)
            local_load_seed_slugs = getattr(cli_mod, "load_seed_slugs", local_load_seed_slugs)


        # 1. Parse sources
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        unknown = [s for s in source_list if s not in local_registry and s not in ("remoteok", "wwr")]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

        # 2. Load seeds
        seed_map = local_load_seed_slugs(source_list)

        # 3. Query sources
        all_new: list[Company] = []
        for src in source_list:
            if event_callback:
                event_callback("query_start", {"source": src})

            try:
                if src == "remoteok":
                    discovered = _remoteok_mod.discover(limit=limit)
                elif src == "wwr":
                    discovered = _wwr_mod.discover(limit=limit)
                else:
                    slugs = seed_map.get(src, [])
                    if not slugs:
                        if event_callback:
                            event_callback("no_slugs", {"source": src})
                        continue
                    if event_callback:
                        event_callback("slugs_loaded", {"source": src, "count": len(slugs)})
                    discovered = local_registry[src](slugs)

                all_new.extend(discovered)
                if event_callback:
                    event_callback("query_success", {"source": src, "count": len(discovered)})
            except Exception as exc:  # noqa: BLE001
                if event_callback:
                    event_callback("query_error", {"source": src, "error": str(exc)})
                logger.warning("{src}: error during discovery — {exc}", src=src, exc=exc)

        # Merge resolved seed companies
        if seed_companies:
            all_new.extend(seed_companies)

        # 4. Load existing from repository
        existing = []
        if self.company_repo.filepath.exists():
            try:
                existing = self.company_repo.load_all()
                if event_callback:
                    event_callback("existing_loaded", {"count": len(existing), "filepath": self.company_repo.filepath})
            except Exception as exc:  # noqa: BLE001
                if event_callback:
                    event_callback("existing_load_failed", {"error": str(exc)})

        before_filter_count = len(existing)

        # 5. Merge and deduplicate
        merged: dict[str, Company] = {c.dedupe_key(): c for c in existing}
        pre_existing_keys = set(merged.keys())

        for new_co in all_new:
            key = new_co.dedupe_key()
            if key in merged:
                existing_urls = {j.job_url for j in merged[key].jobs}
                merged[key].jobs.extend(j for j in new_co.jobs if j.job_url not in existing_urls)
                merged[key].last_updated = new_co.last_updated
            else:
                merged[key] = new_co

        # 6. Apply Filters
        filtered = apply_filters(
            list(merged.values()),
            profile=profile,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
        )
        final = filtered[:limit]

        # 7. Save using repository
        self.company_repo.save_all(final)

        # 8. Compute stats for returned dict
        new_companies_written = [c for c in final if c.dedupe_key() not in pre_existing_keys]
        unchanged_count = len(final) - len(new_companies_written)
        total_new_jobs = sum(len(c.jobs) for c in new_companies_written)
        total_jobs = sum(len(c.jobs) for c in final)

        return {
            "source_list": source_list,
            "all_new_count": len(all_new),
            "before_filter_count": before_filter_count + len(new_companies_written),
            "final_count": len(final),
            "total_jobs": total_jobs,
            "new_companies_written": len(new_companies_written),
            "unchanged_companies_count": unchanged_count,
            "new_jobs": total_new_jobs,
            "new_companies_list": new_companies_written,
            "final_companies": final,
        }

    def save_saved_search(self, name: str, sources: str, limit: int, profile: Optional[str] = None, **kwargs) -> None:
        """Create or update a saved search definition."""
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        unknown = [s for s in source_list if s not in SOURCE_REGISTRY and s not in ("remoteok", "wwr")]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

        searches = load_saved_searches()
        s = SavedSearch(
            name=name,
            profile=profile,
            sources=source_list,
            limit=limit,
            remote=kwargs.get("remote"),
            country=kwargs.get("country"),
            keyword=kwargs.get("keyword"),
            exclude=kwargs.get("exclude"),
            days=kwargs.get("days"),
        )
        searches[name] = s
        save_saved_searches(searches)

    def load_saved_searches(self) -> dict[str, SavedSearch]:
        """Expose loaded searches to presenter."""
        return load_saved_searches()
