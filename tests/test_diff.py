"""Unit tests for the Diff Engine."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.sync.diff import DiffEngine
from app.sync.snapshot import Snapshot


def _make_company(name: str, domain: str, jobs: list[JobPosting] = None) -> Company:
    return Company(
        name=name,
        domain=domain,
        jobs=jobs or [],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )


def _make_job(title: str, url: str) -> JobPosting:
    return JobPosting(
        job_title=title,
        job_url=url,
        source="test",
    )


def test_diff_empty_previous():
    curr_co = _make_company("Google", "google.com", [_make_job("PM", "https://google.com/1")])
    current = Snapshot(provider="test", companies=[curr_co])

    diff = DiffEngine.diff(None, current)
    assert len(diff.added_companies) == 1
    assert diff.added_companies[0].name == "Google"
    assert len(diff.added_jobs) == 1
    assert diff.added_jobs[0].job_title == "PM"


def test_diff_detects_additions_and_removals():
    prev_co = _make_company("Stripe", "stripe.com")
    curr_co = _make_company("Adyen", "adyen.com")

    previous = Snapshot(provider="test", companies=[prev_co])
    current = Snapshot(provider="test", companies=[curr_co])

    diff = DiffEngine.diff(previous, current)
    assert len(diff.added_companies) == 1
    assert diff.added_companies[0].name == "Adyen"
    assert len(diff.removed_companies) == 1
    assert diff.removed_companies[0].name == "Stripe"


def test_diff_detects_updates():
    prev_co = _make_company("Google", "google.com", [_make_job("PM", "https://google.com/1")])
    curr_co = _make_company("Google", "google.com", [
        _make_job("PM", "https://google.com/1"),
        _make_job("Engineer", "https://google.com/2")
    ])

    previous = Snapshot(provider="test", companies=[prev_co])
    current = Snapshot(provider="test", companies=[curr_co])

    diff = DiffEngine.diff(previous, current)
    assert len(diff.added_companies) == 0
    assert len(diff.updated_companies) == 1
    assert len(diff.added_jobs) == 1
    assert diff.added_jobs[0].job_title == "Engineer"


def test_diff_detects_job_updates():
    # If a job's field changes (like location), it is updated
    job_prev = JobPosting(job_title="PM", job_url="https://google.com/1", location="London", source="test")
    job_curr = JobPosting(job_title="PM", job_url="https://google.com/1", location="Paris", source="test")

    prev_co = _make_company("Google", "google.com", [job_prev])
    curr_co = _make_company("Google", "google.com", [job_curr])

    previous = Snapshot(provider="test", companies=[prev_co])
    current = Snapshot(provider="test", companies=[curr_co])

    diff = DiffEngine.diff(previous, current)
    assert len(diff.updated_companies) == 1
    assert len(diff.updated_jobs) == 1
    assert diff.updated_jobs[0].location == "Paris"
