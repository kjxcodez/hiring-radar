"""Base step abstraction and implementations for all domain pipelines."""

from __future__ import annotations

import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from app.models import Company, JobPosting
from app.filters import apply_filters
from app.discover.seed import load_seed_slugs
from app.discover import SOURCE_REGISTRY
from app.discover import remoteok as _remoteok_mod
from app.discover import wwr as _wwr_mod
from app.utils import RateLimiter, get_http_client
from app.resume.parser import load_resume_text
from app.resume.score import score_company
from app.resume.suggestions import suggest_resume_tailoring
from app.outreach.email import generate_email


class WorkflowStep:
    """Interface for a single execution block in a pipeline."""
    name: str = "BaseStep"
    description: str = "Base step description"

    def execute(self, context: Any) -> Any:
        """Run the step's unit of work and update execution context state."""
        raise NotImplementedError("Steps must implement execute()")


# ===========================================================================
# 1. Discover Steps
# ===========================================================================

class DiscoverStep(WorkflowStep):
    """Step to discover new companies from job boards.

    Routes requests to the async ``DiscoveryCoordinator`` for all providers
    registered in ``ProviderRegistry`` (Greenhouse, Lever, Ashby, etc.).
    Sources that are only in the legacy ``SOURCE_REGISTRY`` (e.g. test mocks)
    are handled via the original synchronous fallback path so existing tests
    continue to work without modification.
    """
    name = "Discover"
    description = "Query job boards and seed files for hiring companies."

    def execute(self, context: Any) -> list[Company]:
        if context.metadata.get("skip_discover", False):
            return []
        sources = context.metadata.get("sources", "greenhouse,lever,remoteok,wwr")
        limit = context.metadata.get("limit", 100)
        seed_companies = context.metadata.get("seed_companies")

        import sys
        local_registry = SOURCE_REGISTRY.copy()
        local_load_seed_slugs = load_seed_slugs

        if "app.cli" in sys.modules:
            cli_mod = sys.modules["app.cli"]
            cli_reg = getattr(cli_mod, "SOURCE_REGISTRY", None)
            if cli_reg is not None:
                if "mock" in type(cli_reg).__name__.lower():
                    local_registry = cli_reg
                else:
                    local_registry.update(cli_reg)
            local_load_seed_slugs = getattr(cli_mod, "load_seed_slugs", local_load_seed_slugs)

        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        unknown = [
            s for s in source_list
            if s not in local_registry
            and s not in ("remoteok", "wwr")
            and not s.startswith("mock")
        ]
        if unknown:
            # Also allow sources registered in ProviderRegistry
            from app.discovery.registry import ProviderRegistry as _PR
            unknown = [s for s in unknown if not _PR.has(s)]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

        seed_map = local_load_seed_slugs(source_list)
        all_new: list[Company] = []
        context.metadata["source_list"] = source_list

        # ------------------------------------------------------------------
        # Route to the async DiscoveryCoordinator for registered providers;
        # fall back to the synchronous SOURCE_REGISTRY path for test mocks.
        # ------------------------------------------------------------------
        from app.discovery.registry import ProviderRegistry

        coordinator_sources = [s for s in source_list if ProviderRegistry.has(s)]
        legacy_sources = [s for s in source_list if not ProviderRegistry.has(s)]

        # Async coordinator path (production providers)
        if coordinator_sources:
            from app.discovery.coordinator import DiscoveryCoordinator

            def _progress_cb(src_name: str, companies: list[Company]) -> None:  # type: ignore[misc]
                # Progress already emitted per-source above for legacy; no
                # double-emit for coordinator sources — they log internally.
                pass

            try:
                coordinator = DiscoveryCoordinator(
                    settings=getattr(context, "settings", None),
                )
                coordinator_results = coordinator.discover(
                    sources=coordinator_sources,
                    slugs_by_source=seed_map,
                    limit=limit,
                    progress_callback=_progress_cb,
                )
                all_new.extend(coordinator_results)
            except Exception as exc:  # noqa: BLE001
                logger.warning("coordinator: discovery failed — {exc}", exc=exc)

        # Synchronous legacy path (test mocks / SOURCE_REGISTRY-only sources)
        for src in legacy_sources:
            context.progress.advance(self.name, f"Querying source: {src}", percent=None)
            try:
                if src == "remoteok":
                    discovered = _remoteok_mod.discover(limit=limit)
                elif src == "wwr":
                    discovered = _wwr_mod.discover(limit=limit)
                else:
                    slugs = seed_map.get(src, [])
                    if not slugs:
                        continue
                    discovered = local_registry[src](slugs)

                all_new.extend(discovered)
            except Exception as exc:  # noqa: BLE001
                logger.warning("{src}: error during discovery — {exc}", src=src, exc=exc)

        if seed_companies:
            all_new.extend(seed_companies)

        context.metadata["discovered_companies"] = all_new
        return all_new


class ScrapeStep(WorkflowStep):
    """Step to scrape career page details for companies."""
    name = "Scrape"
    description = "Fetch career pages and extract contact details."

    def execute(self, context: Any) -> dict[str, int]:
        if context.metadata.get("skip_scrape", True):
            context.progress.advance(self.name, "Scrape step bypassed.", percent=None)
            return {"processed": 0, "skipped": 0, "new_emails": 0, "failures": 0}

        company_filter = context.metadata.get("company_filter")
        force = context.metadata.get("force", False)

        # Scrape newly discovered companies or all from repo
        targets = context.metadata.get("discovered_companies")
        if not targets:
            targets = context.metadata.get("companies")
        if not targets:
            targets = context.repositories.company_repo.load_all()

        if company_filter:
            targets = [c for c in targets if company_filter.lower() in c.name.lower()]

        if not targets:
            return {"processed": 0, "skipped": 0, "new_emails": 0, "failures": 0}

        n_processed = 0
        n_skipped = 0
        n_new_emails = 0
        n_failures = 0
        stale_threshold = datetime.now() - datetime.fromtimestamp(0)  # arbitrary large delta if error
        from datetime import timedelta
        stale_threshold = timedelta(days=7)

        rate_limiter = RateLimiter()
        from app.scraper.company import scrape_company_page
        from app.scraper.contacts import extract_contacts

        with get_http_client() as client:
            total_targets = len(targets)
            for idx, co in enumerate(targets):
                context.progress.advance(
                    self.name,
                    f"Scraping {co.name}",
                    percent=(idx / total_targets) * 100 if total_targets else 100,
                    co_name=co.name,
                    idx=idx,
                    total=total_targets,
                )
                if not force:
                    has_contacts = bool(co.generic_emails or co.recruiter_email)
                    recently_scraped = (
                        (datetime.now() - co.last_updated) < stale_threshold
                    )
                    if has_contacts and recently_scraped:
                        n_skipped += 1
                        continue

                try:
                    emails_before = len(co.generic_emails) + (1 if co.recruiter_email else 0)
                    co, page_text = scrape_company_page(co, client, rate_limiter)
                    if page_text is not None:
                        extract_contacts(co, page_text)

                    emails_after = len(co.generic_emails) + (1 if co.recruiter_email else 0)
                    if emails_after > emails_before:
                        n_new_emails += 1

                    n_processed += 1
                    if any(n.startswith("scrape_failed") for n in co.notes):
                        n_failures += 1
                except Exception as exc:  # noqa: BLE001
                    n_failures += 1
                    n_processed += 1
                    co.notes.append(f"scrape_failed: unexpected error — {exc}")

        # Update metadata back
        context.metadata["discovered_companies"] = targets
        return {
            "processed": n_processed,
            "skipped": n_skipped,
            "new_emails": n_new_emails,
            "failures": n_failures,
        }


class DeduplicateStep(WorkflowStep):
    """Step to deduplicate and filter discovered companies against existing repository."""
    name = "Deduplicate"
    description = "Merge and filter discovered jobs with existing database."

    def execute(self, context: Any) -> list[Company]:
        if context.metadata.get("skip_discover", False):
            return context.metadata.get("companies", [])
        all_new = context.metadata.get("discovered_companies", [])
        limit = context.metadata.get("limit", 100)
        profile = context.metadata.get("profile")
        remote = context.metadata.get("remote")
        country = context.metadata.get("country")
        keyword = context.metadata.get("keyword")
        exclude = context.metadata.get("exclude")
        days = context.metadata.get("days")

        existing = []
        if context.repositories.company_repo.filepath.exists():
            existing = context.repositories.company_repo.load_all()

        before_filter_count = len(existing)
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

        new_companies_written = [c for c in final if c.dedupe_key() not in pre_existing_keys]
        unchanged_count = len(final) - len(new_companies_written)
        total_new_jobs = sum(len(c.jobs) for c in new_companies_written)
        total_jobs = sum(len(c.jobs) for c in final)

        context.metadata["companies"] = final
        context.metadata["discover_results"] = {
            "source_list": context.metadata.get("source_list", []),
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
        return final


# ===========================================================================
# 2. General Load & Persist Steps
# ===========================================================================

class LoadCompaniesStep(WorkflowStep):
    """Step to load companies from the database."""
    name = "LoadCompanies"
    description = "Load existing company list from JSON storage."

    def execute(self, context: Any) -> list[Company]:
        companies = context.repositories.company_repo.load_all()
        context.metadata["companies"] = companies
        return companies


class PersistCompaniesStep(WorkflowStep):
    """Step to save companies back to the database."""
    name = "PersistCompanies"
    description = "Save mutated company list back to JSON storage."

    def execute(self, context: Any) -> None:
        companies = context.metadata.get("companies")
        if companies is not None:
            context.repositories.company_repo.save_all(companies)


# ===========================================================================
# 3. Enrichment & Research Steps
# ===========================================================================

class EnrichStep(WorkflowStep):
    """Step to enrich companies with AI summary profiling."""
    name = "Enrich"
    description = "Enrich target companies with LLM summary profiles."

    def execute(self, context: Any) -> dict[str, Any]:
        all_companies = context.metadata.get("companies", [])
        model = context.metadata.get("model")
        dry_run = context.metadata.get("dry_run", False)
        force = context.metadata.get("force", False)

        targets = []
        skipped_count = 0
        for company in all_companies:
            if force or not company.ai_summary:
                targets.append(company)
            else:
                skipped_count += 1

        if not targets:
            return {
                "targets": [],
                "n_enriched": 0,
                "n_failures": 0,
                "skipped_count": skipped_count,
            }

        n_enriched = 0
        n_failures = 0
        rate_limiter = RateLimiter()
        from app.enrich import enrich as _enrich_ai

        total_targets = len(targets)
        for idx, co in enumerate(targets):
            context.progress.advance(
                self.name,
                f"Enriching {co.name}",
                percent=(idx / total_targets) * 100 if total_targets else 100,
                co_name=co.name,
                idx=idx,
                total=total_targets,
            )
            if not dry_run:
                rate_limiter.wait("https://openrouter.ai")

            try:
                _enrich_ai(co, model=model, dry_run=dry_run, ai_gateway=context.ai_gateway)
                if any(n.startswith("enrich_failed") for n in co.notes):
                    n_failures += 1
                else:
                    n_enriched += 1
            except Exception as exc:  # noqa: BLE001
                n_failures += 1
                co.notes.append(f"enrich_failed: unexpected error — {exc}")

        # Update list in metadata
        if not dry_run:
            updated_map = {c.dedupe_key(): c for c in targets}
            final = [updated_map.get(c.dedupe_key(), c) for c in all_companies]
            context.metadata["companies"] = final

        return {
            "targets": targets,
            "n_enriched": n_enriched,
            "n_failures": n_failures,
            "skipped_count": skipped_count,
        }


class ResearchStep(WorkflowStep):
    """Step to perform deeper AI-based Github & profile intelligence research."""
    name = "Research"
    description = "Conduct deep GitHub and web intelligence query research."

    def execute(self, context: Any) -> Company:
        company_name = context.metadata.get("company_name")
        model = context.metadata.get("model")
        dry_run = context.metadata.get("dry_run", False)

        all_companies = context.metadata.get("companies", [])
        if not all_companies:
            all_companies = context.repositories.company_repo.load_all()
            context.metadata["companies"] = all_companies

        # Find target company
        target_co = None
        for co in all_companies:
            if company_name.lower() in co.name.lower():
                target_co = co
                break

        if not target_co:
            from app.exceptions import CompanyNotFoundError
            raise CompanyNotFoundError(f"Company '{company_name}' not found in database.")

        rate_limiter = RateLimiter()
        from app.enrich.research import research_company

        with get_http_client() as client:
            target_co = research_company(
                target_co,
                client,
                rate_limiter,
                model=model,
                dry_run=dry_run,
                ai_gateway=context.ai_gateway,
            )

        if not dry_run:
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == target_co.dedupe_key():
                    all_companies[idx] = target_co
                    break
            context.metadata["companies"] = all_companies

        context.metadata["researched_company"] = target_co
        return target_co


# ===========================================================================
# 4. Resume & Scoring Steps
# ===========================================================================

class LoadResumeStep(WorkflowStep):
    """Step to load and parse candidate resume text."""
    name = "LoadResume"
    description = "Find and parse TXT/PDF candidate resume files."

    def execute(self, context: Any) -> str:
        resume_label = context.metadata.get("resume_label")
        resume_service = context.services.resume_service

        resume_path = resume_service.resolve_version_path(resume_label)
        if not resume_path:
            raise ValueError("Resume path is not set in settings or passed options.")

        resume_text = resume_service.parse_resume(resume_path)
        context.metadata["resume_text"] = resume_text
        context.metadata["resume_path"] = resume_path
        return resume_text


class ScoreResumeStep(WorkflowStep):
    """Step to score companies compatibility against parsed resume."""
    name = "ScoreResume"
    description = "Compare resume skills against target company requirements."

    def execute(self, context: Any) -> dict[str, Any]:
        company_name = context.metadata.get("company_name")
        resume_text = context.metadata.get("resume_text")
        model = context.metadata.get("model")
        dry_run = context.metadata.get("dry_run", False)

        co = context.repositories.company_repo.find_by_name(company_name)

        result = score_company(
            co,
            resume_text,
            model=model,
            dry_run=dry_run,
            ai_gateway=context.ai_gateway,
        )

        context.metadata["score_results"] = {
            "company": co,
            "resume_path": context.metadata.get("resume_path"),
            "overall_match_percent": result.get("overall_match_percent", 0),
            "skill_breakdown": result.get("skill_breakdown", {}),
            "missing_skills": result.get("missing_skills", []),
        }
        return context.metadata["score_results"]


class TailorResumeStep(WorkflowStep):
    """Step to suggest tailoring recommendations."""
    name = "TailorResume"
    description = "Generate keywords, project highlights and summary tweaks."

    def execute(self, context: Any) -> dict[str, Any]:
        company_name = context.metadata.get("company_name")
        resume_text = context.metadata.get("resume_text")
        model = context.metadata.get("model")
        dry_run = context.metadata.get("dry_run", False)

        co = context.repositories.company_repo.find_by_name(company_name)

        suggestions = suggest_resume_tailoring(
            co,
            resume_text,
            model=model,
            dry_run=dry_run,
            ai_gateway=context.ai_gateway,
        )

        all_companies = context.metadata.get("companies", [])
        if not all_companies:
            all_companies = context.repositories.company_repo.load_all()

        target_co = None
        for idx, item in enumerate(all_companies):
            if item.dedupe_key() == co.dedupe_key():
                target_co = item
                if not dry_run:
                    note_text = f"tailoring_suggested: {date.today().isoformat()}"
                    if note_text not in target_co.notes:
                        target_co.notes.append(note_text)
                    target_co.last_updated = datetime.now()
                    all_companies[idx] = target_co
                break

        context.metadata["companies"] = all_companies
        context.metadata["tailor_results"] = {
            "company": target_co or co,
            "resume_path": context.metadata.get("resume_path"),
            "suggestions": suggestions,
        }
        return context.metadata["tailor_results"]


# ===========================================================================
# 5. Recommendation Steps
# ===========================================================================

class RecommendStep(WorkflowStep):
    """Step to rank and recommend companies to apply to."""
    name = "Recommend"
    description = "Rank target companies based on scores and compatibility overlap."

    def execute(self, context: Any) -> list[dict[str, Any]]:
        top = context.metadata.get("top", 5)
        resume_label = context.metadata.get("resume_label")
        resume_service = context.services.resume_service
        company_repo = context.repositories.company_repo
        settings = context.settings

        all_companies = context.metadata.get("companies", [])
        if not all_companies:
            all_companies = company_repo.load_all()

        uncontacted = [
            c for c in all_companies
            if not any(n.startswith("email_sent:") for n in c.notes)
        ]

        resume_text = None
        resume_path = None
        if resume_label or settings.resume_path:
            try:
                resume_path = resume_service.resolve_version_path(resume_label)
                if resume_path and resume_path.exists():
                    resume_text = load_resume_text(resume_path)
            except Exception:  # noqa: BLE001
                pass

        def get_recency(co: Company) -> datetime:
            dates = [
                datetime.combine(j.posted_date, datetime.min.time())
                for j in co.jobs if j.posted_date
            ]
            if dates:
                return max(dates)
            return co.discovered_at or datetime.min

        def calculate_heuristic_fit(co: Company, r_text: str) -> int:
            r_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", r_text.lower()))
            if not r_words:
                return 0
            co_text = (
                (co.description or "")
                + " "
                + " ".join(j.job_title + " " + (j.description or "") for j in co.jobs)
            )
            co_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", co_text.lower()))
            return len(r_words.intersection(co_words))

        scored_list = []
        unscored_list = []

        for co in uncontacted:
            is_scored = co.company_score_overall is not None
            recency = get_recency(co)
            fit_score = 0
            if resume_text:
                fit_score = calculate_heuristic_fit(co, resume_text)

            item = {
                "company": co,
                "is_scored": is_scored,
                "overall": co.company_score_overall,
                "recency": recency,
                "fit_score": fit_score,
            }
            if is_scored:
                scored_list.append(item)
            else:
                unscored_list.append(item)

        scored_list.sort(key=lambda x: (x["overall"], x["recency"]), reverse=True)
        unscored_list.sort(key=lambda x: x["recency"], reverse=True)

        ranked = scored_list + unscored_list
        top_items = ranked[:top]

        result = []
        for item in top_items:
            co = item["company"]
            result.append({
                "company": co,
                "is_scored": item["is_scored"],
                "overall": item["overall"],
                "recency": item["recency"],
                "fit_score": item["fit_score"],
                "resume_path": resume_path,
            })

        context.metadata["recommendations"] = result
        return result


# ===========================================================================
# 6. Outreach Steps
# ===========================================================================

class OutreachSubjectStep(WorkflowStep):
    """Step to generate subject lines candidate list."""
    name = "OutreachSubject"
    description = "Generate cold outreach subject candidates."

    def execute(self, context: Any) -> list[str]:
        # Handled inside OutreachEmailStep or OutreachService internally
        return []


class OutreachEmailStep(WorkflowStep):
    """Step to generate outreach body variables and templates."""
    name = "OutreachEmail"
    description = "Draft cold outreach email templates using LLM gateway."

    def execute(self, context: Any) -> dict[str, Any]:
        company_name = context.metadata.get("company_name")
        template = context.metadata.get("template", "startup")
        model = context.metadata.get("model")
        dry_run = context.metadata.get("dry_run", False)

        co = context.repositories.company_repo.find_by_name(company_name)

        res = generate_email(
            co,
            template_name=template,
            model=model,
            dry_run=dry_run,
            ai_gateway=context.ai_gateway,
        )
        recipient = co.recruiter_email or (co.generic_emails[0] if co.generic_emails else "(no email found)")

        context.metadata["outreach_results"] = {
            "company": co,
            "recipient": recipient,
            "subject": res.get("subject", ""),
            "body": res.get("body", ""),
            "template_used": res.get("template_used", template),
        }
        return context.metadata["outreach_results"]
