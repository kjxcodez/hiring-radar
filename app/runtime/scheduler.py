from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from app.storage.json_storage import JsonStorage


class ScheduledJob(BaseModel):
    """Represents a scheduled periodic or cron workflow trigger."""
    id: str
    workflow_name: str
    cron_or_interval: str  # Format: "interval:3600" or "cron:0 8 * * *"
    kwargs: dict = Field(default_factory=dict)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


class Scheduler:
    """Manages recurring execution schedules and periodic ticks for workflows."""

    def __init__(self, schedule_file: Path, storage: Optional[JsonStorage] = None) -> None:
        self.schedule_file = schedule_file
        self.storage = storage or JsonStorage()

    def add_schedule(self, job_id: str, workflow_name: str, cron_or_interval: str, **kwargs: Any) -> None:
        """Create or update a workflow schedule definition."""
        schedules = self.load_schedules()
        job = ScheduledJob(
            id=job_id,
            workflow_name=workflow_name,
            cron_or_interval=cron_or_interval,
            kwargs=kwargs,
        )
        self.calculate_next_run(job)
        schedules[job_id] = job
        self.save_schedules(schedules)

    def calculate_next_run(self, job: ScheduledJob) -> None:
        """Compute the next UTC execution time for a scheduled job."""
        now = datetime.utcnow()
        if job.cron_or_interval.startswith("interval:"):
            try:
                seconds = int(job.cron_or_interval.split(":")[1])
                base = job.last_run or now
                job.next_run = base + timedelta(seconds=seconds)
            except Exception:
                job.next_run = now + timedelta(hours=1)
        elif job.cron_or_interval.startswith("cron:"):
            # Simplified cron parser supporting: minutes hours * * *
            parts = job.cron_or_interval.split(":")[1].split()
            if len(parts) == 5:
                try:
                    minute = int(parts[0]) if parts[0].isdigit() else 0
                    hour = int(parts[1]) if parts[1].isdigit() else 8
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target <= now:
                        target += timedelta(days=1)
                    job.next_run = target
                except Exception:
                    job.next_run = now + timedelta(days=1)
            else:
                job.next_run = now + timedelta(days=1)
        else:
            job.next_run = now + timedelta(days=1)

    def tick(self) -> List[ScheduledJob]:
        """Evaluate schedules. Returns due jobs and updates their states."""
        schedules = self.load_schedules()
        now = datetime.utcnow()
        due_jobs = []
        changed = False
        
        for job in list(schedules.values()):
            if job.next_run and now >= job.next_run:
                due_jobs.append(job)
                job.last_run = now
                self.calculate_next_run(job)
                changed = True
                
        if changed:
            self.save_schedules(schedules)
            
        return due_jobs

    def load_schedules(self) -> dict[str, ScheduledJob]:
        """Load schedule definitions from storage."""
        try:
            data = self.storage.read(self.schedule_file)
            if not isinstance(data, dict):
                return {}
            return {k: ScheduledJob(**v) for k, v in data.items()}
        except Exception:
            return {}

    def save_schedules(self, schedules: dict[str, ScheduledJob]) -> None:
        """Atomically persist schedule definitions to storage."""
        data = {k: v.model_dump(mode="json") for k, v in schedules.items()}
        self.storage.write(self.schedule_file, data)
