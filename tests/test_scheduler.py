from __future__ import annotations

import datetime
import pytest
from app.runtime.scheduler import Scheduler, ScheduledJob
from app.storage.json_storage import JsonStorage


@pytest.fixture
def temp_schedule_file(tmp_path):
    return tmp_path / "schedules.json"


def test_scheduler_interval_calculation(temp_schedule_file):
    storage = JsonStorage()
    scheduler = Scheduler(temp_schedule_file, storage=storage)

    job = ScheduledJob(
        id="test_interval",
        workflow_name="discover",
        cron_or_interval="interval:3600"
    )

    scheduler.calculate_next_run(job)
    assert job.next_run is not None
    # Next run should be roughly 1 hour from now
    diff = job.next_run - datetime.datetime.utcnow()
    assert 3500 < diff.total_seconds() < 3700


def test_scheduler_cron_calculation(temp_schedule_file):
    storage = JsonStorage()
    scheduler = Scheduler(temp_schedule_file, storage=storage)

    job = ScheduledJob(
        id="test_cron",
        workflow_name="recommend",
        cron_or_interval="cron:0 8 * * *"
    )

    scheduler.calculate_next_run(job)
    assert job.next_run is not None
    assert job.next_run.hour == 8
    assert job.next_run.minute == 0


def test_scheduler_ticking(temp_schedule_file):
    storage = JsonStorage()
    scheduler = Scheduler(temp_schedule_file, storage=storage)

    # Add schedule that is due (next run in past)
    scheduler.add_schedule("due_job", "discover", "interval:10")
    schedules = scheduler.load_schedules()
    # Force next run to be in the past
    schedules["due_job"].next_run = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    scheduler.save_schedules(schedules)

    # Tick and verify it triggers the job
    due = scheduler.tick()
    assert len(due) == 1
    assert due[0].id == "due_job"

    # Next run is updated to future, ticking again returns empty
    assert len(scheduler.tick()) == 0
