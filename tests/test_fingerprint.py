"""Unit tests for the Fingerprinting Engine."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint


def test_company_fingerprint_is_deterministic():
    co1 = Company(
        name="Test Corp",
        domain="testcorp.com",
        website="https://testcorp.com",
        career_page_url="https://testcorp.com/careers",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    co2 = Company(
        name="Test Corp",
        domain="testcorp.com",
        website="https://testcorp.com",
        career_page_url="https://testcorp.com/careers",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    # Different timestamps, but same identity properties
    assert generate_company_fingerprint(co1) == generate_company_fingerprint(co2)


def test_company_fingerprint_changes_on_field_update():
    co = Company(
        name="Test Corp",
        domain="testcorp.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    fp_before = generate_company_fingerprint(co)

    co.domain = "updated.com"
    fp_after = generate_company_fingerprint(co)
    assert fp_before != fp_after


def test_job_fingerprint_is_deterministic():
    job1 = JobPosting(
        job_title="Software Engineer",
        job_url="https://testcorp.com/job1",
        location="Remote",
        remote_type="remote",
        source="greenhouse",
    )
    job2 = JobPosting(
        job_title="Software Engineer",
        job_url="https://testcorp.com/job1",
        location="Remote",
        remote_type="remote",
        source="greenhouse",
    )
    assert generate_job_fingerprint(job1) == generate_job_fingerprint(job2)


def test_job_fingerprint_changes_on_field_update():
    job = JobPosting(
        job_title="Software Engineer",
        job_url="https://testcorp.com/job1",
        location="Remote",
        remote_type="remote",
        source="greenhouse",
    )
    fp_before = generate_job_fingerprint(job)

    job.location = "New York"
    fp_after = generate_job_fingerprint(job)
    assert fp_before != fp_after
