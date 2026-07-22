"""Follow-up schedule generator creating action reminder timelines."""

from __future__ import annotations

from typing import List
from app.outreach.profile import FollowUp


class FollowUpScheduler:
    """Generates standard follow-up schedules for submitted applications."""

    @staticmethod
    def create_schedule() -> List[FollowUp]:
        """Return a list of standard recommended follow-up events."""
        return [
            FollowUp(day=0, action="Submit application on career portal", template_name="portal_apply"),
            FollowUp(day=5, action="Send first recruiter follow-up email", template_name="recruiter_followup"),
            FollowUp(day=12, action="Send second LinkedIn connection note", template_name="linkedin_reminder"),
            FollowUp(day=21, action="Archive application or check alternative contacts", template_name="archive_check"),
        ]
