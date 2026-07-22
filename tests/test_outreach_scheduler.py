"""Unit tests for the CRM FollowUpScheduler creating offset schedule templates."""

from __future__ import annotations

from app.outreach.scheduler import FollowUpScheduler


def test_followup_scheduler():
    schedule = FollowUpScheduler.create_schedule()
    assert len(schedule) == 4
    assert schedule[0].day == 0
    assert schedule[1].day == 5
    assert schedule[2].day == 12
    assert schedule[3].day == 21

    # Status defaults to pending
    assert all(item.status == "pending" for item in schedule)
