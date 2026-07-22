"""Unit tests for the Snapshot model."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.sync.snapshot import Snapshot


def test_snapshot_checksum_calculation():
    co = Company(
        name="Stripe",
        domain="stripe.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Engineer",
                job_url="https://stripe.com/jobs/1",
                source="greenhouse",
            )
        ],
    )
    snap = Snapshot(provider="greenhouse", companies=[co])
    checksum1 = snap.calculate_checksum()
    assert len(checksum1) == 64  # SHA-256 length in hex

    snap.checksum = checksum1
    assert snap.checksum == snap.calculate_checksum()


def test_snapshot_checksum_order_independence():
    co1 = Company(
        name="Alpha",
        domain="alpha.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    co2 = Company(
        name="Beta",
        domain="beta.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    snap1 = Snapshot(provider="test", companies=[co1, co2])
    snap2 = Snapshot(provider="test", companies=[co2, co1])

    assert snap1.calculate_checksum() == snap2.calculate_checksum()


def test_snapshot_checksum_changes_on_data_mutation():
    co = Company(
        name="Stripe",
        domain="stripe.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Engineer",
                job_url="https://stripe.com/jobs/1",
                source="greenhouse",
            )
        ],
    )
    snap = Snapshot(provider="greenhouse", companies=[co])
    hash_before = snap.calculate_checksum()

    # Mutate a job title
    co.jobs[0].job_title = "Senior Engineer"
    hash_after = snap.calculate_checksum()

    assert hash_before != hash_after
