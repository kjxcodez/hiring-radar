"""Unit tests for the property-level CRMDiffEngine."""

from __future__ import annotations

from app.outreach.profile import Recruiter
from app.monitoring.diff import CRMDiffEngine


def test_diff_dicts():
    old = {"salary_min": 100000, "location": "SF"}
    new = {"salary_min": 120000, "location": "SF"}

    diffs = CRMDiffEngine.diff_dicts(old, new, ["salary_min", "location"])
    assert len(diffs) == 1
    assert diffs[0].field_name == "salary_min"
    assert diffs[0].previous_value == 100000
    assert diffs[0].current_value == 120000


def test_diff_pydantic():
    old = Recruiter(name="Alice", email="alice@co.com")
    new = Recruiter(name="Alice", email="alice_new@co.com")

    diffs = CRMDiffEngine.diff_pydantic(old, new, ["name", "email"])
    assert len(diffs) == 1
    assert diffs[0].field_name == "email"
    assert diffs[0].previous_value == "alice@co.com"
    assert diffs[0].current_value == "alice_new@co.com"
