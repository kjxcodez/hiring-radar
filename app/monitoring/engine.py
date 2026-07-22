"""Change detection engine orchestrating monitoring and alert pipelines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from loguru import logger

from app.models import Company, Application
from app.monitoring.events import ChangeEvent
from app.monitoring.alerts import Alert, AlertEngine
from app.monitoring.digest import DigestGenerator
from app.monitoring.detectors import (
    JobChangeDetector,
    CompanyChangeDetector,
    RecommendationChangeDetector,
    ApplicationChangeDetector,
)
from app.monitoring.fingerprint import FingerprintEngine

if TYPE_CHECKING:
    from app.services.config import ServiceContainer


class MonitoringEngine:
    """Detects, aggregates, and alerts on database state modifications."""

    def __init__(self, container: ServiceContainer):
        self.container = container
        self.snapshot_dir = container.settings.output_dir / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.companies_snap_path = self.snapshot_dir / "companies_snap.json"
        self.recs_snap_path = self.snapshot_dir / "recs_snap.json"
        self.apps_snap_path = self.snapshot_dir / "apps_snap.json"

    def run_monitoring(self, force: bool = False) -> List[ChangeEvent]:
        """Run the change detection pipeline across all active components."""
        logger.info("monitoring: starting change detection check...")
        events: List[ChangeEvent] = []

        # 1. Load current repositories state
        current_cos_list = self.container.company_repo.load_all()
        current_cos = {c.dedupe_key(): c for c in current_cos_list}
        current_recs = self.container.recommendation_repo.load_recommendations()
        current_apps = self.container.application_repo.load_all()

        # 2. Load previous snapshots
        prev_cos = self._load_companies_snapshot()
        prev_recs = self._load_recs_snapshot()
        prev_apps = self._load_apps_snapshot()

        # If previous snapshots don't exist, this is initial run
        if not prev_cos and not prev_recs and not prev_apps:
            logger.info("monitoring: initial run - creating baseline snapshots.")
            self._save_snapshots(current_cos, current_recs, current_apps)
            return []

        # 3. Detect Job & Company Changes
        for key, curr_co in current_cos.items():
            if key in prev_cos:
                prev_co = prev_cos[key]
                # Compare fingerprints
                old_hash = FingerprintEngine.company(prev_co)
                new_hash = FingerprintEngine.company(curr_co)

                # Run detectors
                company_events = CompanyChangeDetector.detect(prev_co, curr_co)
                job_events = JobChangeDetector.detect(curr_co.name, prev_co.jobs, curr_co.jobs)

                events.extend(company_events)
                events.extend(job_events)

        # 4. Detect Recommendation Changes
        rec_events = RecommendationChangeDetector.detect(prev_recs, current_recs)
        events.extend(rec_events)

        # 5. Detect Application Changes
        app_events = ApplicationChangeDetector.detect(prev_apps, current_apps)
        events.extend(app_events)

        # 6. Aggregate Events
        from app.monitoring.aggregator import EventAggregator
        collapsed_events = EventAggregator.collapse_and_deduplicate(events)

        # 7. Generate alerts
        alerts = AlertEngine.generate_alerts(collapsed_events)

        # 8. Generate Daily Digest
        digest = DigestGenerator.generate(collapsed_events, self.container.ai_gateway)

        # 9. Save Repository data
        self.container.monitoring_repo.save_events(collapsed_events)
        self.container.monitoring_repo.save_alerts(alerts)
        self.container.monitoring_repo.save_digest(digest)

        # 10. Update Snapshots
        self._save_snapshots(current_cos, current_recs, current_apps)
        logger.info(f"monitoring: run complete. Detected {len(collapsed_events)} events and {len(alerts)} alerts.")

        return collapsed_events

    def _load_companies_snapshot(self) -> Dict[str, Company]:
        if not self.companies_snap_path.exists():
            return {}
        try:
            data = self.container.storage.read(self.companies_snap_path) or []
            cos = [Company.model_validate(c) for c in data]
            return {c.dedupe_key(): c for c in cos}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load companies snapshot: {exc}")
            return {}

    def _load_recs_snapshot(self) -> List[dict]:
        if not self.recs_snap_path.exists():
            return []
        try:
            return self.container.storage.read(self.recs_snap_path) or []
        except Exception:  # noqa: BLE001
            return []

    def _load_apps_snapshot(self) -> Dict[str, Application]:
        if not self.apps_snap_path.exists():
            return {}
        try:
            data = self.container.storage.read(self.apps_snap_path) or {}
            return {k: Application.model_validate(v) for k, v in data.items()}
        except Exception:  # noqa: BLE001
            return {}

    def _save_snapshots(
        self,
        companies: Dict[str, Company],
        recs: List[dict],
        apps: Dict[str, Application],
    ) -> None:
        # Save companies snap
        companies_data = [c.model_dump(mode="json") for c in companies.values()]
        self.container.storage.write(self.companies_snap_path, companies_data)

        # Save recs snap
        self.container.storage.write(self.recs_snap_path, recs)

        # Save apps snap
        apps_data = {k: v.model_dump(mode="json") for k, v in apps.items()}
        self.container.storage.write(self.apps_snap_path, apps_data)
