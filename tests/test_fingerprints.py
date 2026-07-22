"""Unit tests for the FingerprintEngine creating deterministic hashes."""

from __future__ import annotations

from datetime import datetime
from app.models import Company, JobPosting, Application
from app.monitoring.fingerprint import FingerprintEngine


def test_fingerprints_determinism():
    co1 = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())
    co2 = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    # Fingerprints should be equal for identical values (ignoring auto timestamps if configured)
    assert FingerprintEngine.company(co1) == FingerprintEngine.company(co2)

    job1 = JobPosting(job_title="Engineer", job_url="http://co.com/1", source="greenhouse")
    job2 = JobPosting(job_title="Engineer", job_url="http://co.com/1", source="greenhouse")
    assert FingerprintEngine.job(job1) == FingerprintEngine.job(job2)


def test_fingerprints_change():
    job1 = JobPosting(job_title="Engineer", job_url="http://co.com/1", source="greenhouse")
    job2 = JobPosting(job_title="Senior Engineer", job_url="http://co.com/1", source="greenhouse")
    assert FingerprintEngine.job(job1) != FingerprintEngine.job(job2)
