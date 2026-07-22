"""Synchronization Engine coordinating incremental crawls and change detection."""

from __future__ import annotations

import asyncio
from datetime import datetime
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from app.models import Company
from app.discovery.registry import ProviderRegistry
from app.discovery.rate_limit import build_limiter
from app.sync.checkpoint import SyncCheckpoint
from app.sync.snapshot import Snapshot
from app.sync.diff import DiffEngine
from app.sync.metrics import SyncMetrics
from app.sync.history import SyncHistory, SyncHistoryEntry
from app.sync.storage import SyncStorage


class SyncEngine:
    """Core synchronization engine for the discovery pipeline."""

    def __init__(self, container: Any, settings: Any) -> None:
        self.container = container
        self.settings = settings
        self.storage = container.storage
        self.company_repo = container.company_repo
        
        self.sync_storage = SyncStorage(settings.output_dir, storage=self.storage)
        self.history = SyncHistory(settings.output_dir / "sync_history.json", storage=self.storage)
        self.cooldown_seconds = 300.0  # 5 minutes default cooldown

    async def sync_provider(
        self,
        provider_name: str,
        slugs: List[str],
        limit: int,
    ) -> SyncMetrics:
        """Run the synchronization pipeline for a single provider.

        1. Load checkpoint
        2. Check cooldown to minimize HTTP requests
        3. Query provider and create snapshot
        4. Diff against previous snapshot
        5. Reconcile database changes (batch updates & soft deletions)
        6. Persist snapshot & checkpoint
        7. Record history & metrics
        """
        start_time = time.monotonic()
        checkpoint = self.sync_storage.load_checkpoint(provider_name)
        metrics = SyncMetrics(provider=provider_name)

        # Calculate estimated HTTP requests (1 per slug for ATS, 1 for feeds)
        estimated_requests = 1 if not slugs else len(slugs)

        # Check cooldown cache hit
        now = datetime.utcnow()
        if (
            checkpoint.last_successful_run
            and (now - checkpoint.last_successful_run).total_seconds() < self.cooldown_seconds
        ):
            logger.info(
                "sync: provider '{p}' is within cooldown window — skipping queries.",
                p=provider_name,
            )
            metrics.skipped_requests = estimated_requests
            metrics.cache_hits = 1
            metrics.duration = time.monotonic() - start_time
            return metrics

        metrics.cache_misses = 1
        metrics.http_requests = estimated_requests

        logger.info("sync: starting sync run for provider '{p}'", p=provider_name)

        # Run provider query
        try:
            provider = ProviderRegistry.get(provider_name)
        except Exception as exc:
            checkpoint.last_failed_run = now
            self.sync_storage.save_checkpoint(checkpoint)
            self.history.append(
                SyncHistoryEntry(
                    provider=provider_name,
                    status="failed",
                    duration=time.monotonic() - start_time,
                    error_message=str(exc),
                )
            )
            raise exc

        limiter = build_limiter(provider_name)

        try:
            async with limiter:
                companies = await provider.discover(slugs=slugs, limit=limit)
        except Exception as exc:
            checkpoint.last_failed_run = now
            self.sync_storage.save_checkpoint(checkpoint)
            self.history.append(
                SyncHistoryEntry(
                    provider=provider_name,
                    status="failed",
                    duration=time.monotonic() - start_time,
                    error_message=str(exc),
                )
            )
            raise exc

        # Create current snapshot
        current_snapshot = Snapshot(provider=provider_name, companies=companies)
        current_snapshot.checksum = current_snapshot.calculate_checksum()

        # Load previous snapshot
        previous_snapshot = self.sync_storage.load_snapshot(provider_name)

        # Checksum check to skip redundant database operations
        if previous_snapshot and previous_snapshot.checksum == current_snapshot.checksum:
            logger.info("sync: checksum matches for '{p}' — no changes detected.", p=provider_name)
            metrics.cache_hits += 1
            checkpoint.last_successful_run = now
            checkpoint.duration = time.monotonic() - start_time
            self.sync_storage.save_checkpoint(checkpoint)
            self.sync_storage.save_snapshot(current_snapshot)
            self.history.append(
                SyncHistoryEntry(
                    provider=provider_name,
                    status="success",
                    duration=checkpoint.duration,
                    added_companies=0,
                    updated_companies=0,
                    removed_companies=0,
                    added_jobs=0,
                    updated_jobs=0,
                    removed_jobs=0,
                )
            )
            metrics.duration = checkpoint.duration
            return metrics

        # Compute difference
        diff = DiffEngine.diff(previous_snapshot, current_snapshot)

        # Load existing main database companies for reconciliation
        existing_companies = self.company_repo.load_all()
        db_by_key = {c.dedupe_key(): c for c in existing_companies}

        # 1. Apply added companies
        for co in diff.added_companies:
            db_by_key[co.dedupe_key()] = co
            metrics.companies_discovered += 1

        # 2. Apply updated companies (merging notes and jobs)
        now_str = datetime.now().isoformat()
        for co in diff.updated_companies:
            key = co.dedupe_key()
            if key in db_by_key:
                existing_co = db_by_key[key]
                
                # Check for removed jobs to add soft deletion notes
                existing_urls = {j.job_url for j in existing_co.jobs}
                current_urls = {j.job_url for j in co.jobs}
                removed_urls = existing_urls - current_urls
                
                merged_notes = list(existing_co.notes)
                for note in co.notes:
                    if note not in merged_notes:
                        merged_notes.append(note)
                        
                for job in existing_co.jobs:
                    if job.job_url in removed_urls:
                        note_msg = f"job_removed: {job.job_title} ({job.job_url}) at {now_str}"
                        if note_msg not in merged_notes:
                            merged_notes.append(note_msg)
                            
                co.notes = merged_notes
                db_by_key[key] = co
                metrics.companies_updated += 1

        # 3. Soft-delete removed companies (log notes, clear jobs list)
        for co in diff.removed_companies:
            key = co.dedupe_key()
            if key in db_by_key:
                existing_co = db_by_key[key]
                
                merged_notes = list(existing_co.notes)
                for job in existing_co.jobs:
                    note_msg = f"job_removed: {job.job_title} ({job.job_url}) at {now_str}"
                    if note_msg not in merged_notes:
                        merged_notes.append(note_msg)
                        
                existing_co.jobs = []
                note_msg = f"company_removed: {now_str}"
                if note_msg not in merged_notes:
                    merged_notes.append(note_msg)
                
                existing_co.notes = merged_notes
                existing_co.last_updated = datetime.now()
                metrics.companies_removed += 1


        # Update metrics for jobs
        metrics.jobs_added = len(diff.added_jobs)
        metrics.jobs_updated = len(diff.updated_jobs)
        metrics.jobs_removed = len(diff.removed_jobs)

        # Batch save reconciled companies
        self.company_repo.save_all(list(db_by_key.values()))

        # Save snapshot and update checkpoint
        self.sync_storage.save_snapshot(current_snapshot)
        
        checkpoint.last_successful_run = now
        checkpoint.duration = time.monotonic() - start_time
        self.sync_storage.save_checkpoint(checkpoint)

        # Record history entry
        self.history.append(
            SyncHistoryEntry(
                provider=provider_name,
                status="success",
                duration=checkpoint.duration,
                added_companies=metrics.companies_discovered,
                updated_companies=metrics.companies_updated,
                removed_companies=metrics.companies_removed,
                added_jobs=metrics.jobs_added,
                updated_jobs=metrics.jobs_updated,
                removed_jobs=metrics.jobs_removed,
            )
        )

        metrics.duration = checkpoint.duration
        return metrics

    def sync_all(
        self,
        sources: List[str],
        slugs_by_source: Dict[str, List[str]],
        limit: int,
    ) -> List[SyncMetrics]:
        """Synchronously run sync for multiple sources, bridging to async execution."""
        return asyncio.run(self.sync_all_async(sources, slugs_by_source, limit))

    async def sync_all_async(
        self,
        sources: List[str],
        slugs_by_source: Dict[str, List[str]],
        limit: int,
    ) -> List[SyncMetrics]:
        """Asynchronously run sync for multiple sources concurrently."""
        tasks = [
            self.sync_provider(src, slugs_by_source.get(src, []), limit)
            for src in sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics_list = []
        for src, res in zip(sources, results):
            if isinstance(res, Exception):
                logger.error("sync: source '{s}' failed with error — {e}", s=src, e=res)
            elif isinstance(res, SyncMetrics):
                metrics_list.append(res)
        return metrics_list
