"""Tests for WorkableProvider — mocked HTTP, remote_type mapping."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from app.discovery.providers.workable import WorkableProvider
from app.models import Company, JobPosting


def _make_company(name: str, remote_type: str = "remote") -> Company:
    return Company(
        name=name,
        ats_platform="workable",
        ats_slug=name.lower(),
        jobs=[
            JobPosting(
                job_title="Backend Engineer",
                job_url=f"https://apply.workable.com/{name.lower()}/j/1",
                remote_type=remote_type,
                source="workable",
            )
        ],
        discovered_at=datetime.now(),
        last_updated=datetime.now(),
    )


class TestWorkableProvider:

    def setup_method(self):
        self.provider = WorkableProvider()

    def test_name(self):
        assert self.provider.name == "workable"

    def test_is_not_feed_based(self):
        assert self.provider.is_feed_based() is False

    def test_discover_empty_slugs_returns_empty(self):
        result = asyncio.run(self.provider.discover(slugs=[], limit=50))
        assert result == []

    def test_discover_delegates_to_sync_module(self):
        mock_cos = [_make_company("buffer")]
        with patch("app.discover.workable.discover", return_value=mock_cos) as mock_fn:
            result = asyncio.run(self.provider.discover(slugs=["buffer"], limit=50))
            mock_fn.assert_called_once_with(["buffer"])
            assert len(result) == 1

    def test_discover_handles_exception_gracefully(self):
        with patch("app.discover.workable.discover", side_effect=ValueError("bad")):
            result = asyncio.run(self.provider.discover(slugs=["x"], limit=10))
            assert result == []

    def test_remote_type_preserved(self):
        """Company with remote_type=remote should be preserved as-is."""
        mock_cos = [_make_company("remote-co", remote_type="remote")]
        with patch("app.discover.workable.discover", return_value=mock_cos):
            result = asyncio.run(self.provider.discover(slugs=["remote-co"], limit=10))
            assert result[0].jobs[0].remote_type == "remote"
