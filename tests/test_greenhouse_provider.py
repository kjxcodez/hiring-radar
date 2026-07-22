"""Tests for GreenhouseProvider — mocked HTTP, error handling."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.discovery.providers.greenhouse import GreenhouseProvider
from app.models import Company, JobPosting


def _make_company(name: str) -> Company:
    return Company(
        name=name,
        ats_platform="greenhouse",
        ats_slug=name.lower(),
        jobs=[
            JobPosting(
                job_title="Software Engineer",
                job_url=f"https://boards.greenhouse.io/{name.lower()}/jobs/1",
                source="greenhouse",
            )
        ],
        discovered_at=datetime.now(),
        last_updated=datetime.now(),
    )


class TestGreenhouseProvider:

    def setup_method(self):
        self.provider = GreenhouseProvider()

    def test_name(self):
        assert self.provider.name == "greenhouse"

    def test_is_not_feed_based(self):
        assert self.provider.is_feed_based() is False

    def test_discover_empty_slugs_returns_empty(self):
        result = asyncio.run(self.provider.discover(slugs=[], limit=50))
        assert result == []

    def test_discover_calls_sync_discover(self):
        mock_cos = [_make_company("stripe")]
        with patch("app.discover.greenhouse.discover", return_value=mock_cos) as mock_fn:
            result = asyncio.run(self.provider.discover(slugs=["stripe"], limit=50))
            mock_fn.assert_called_once_with(["stripe"])
            assert len(result) == 1
            assert result[0].name == "stripe"

    def test_discover_handles_sync_exception_gracefully(self):
        with patch("app.discover.greenhouse.discover", side_effect=RuntimeError("boom")):
            result = asyncio.run(self.provider.discover(slugs=["bad"], limit=50))
            assert result == []

    def test_discover_returns_all_from_sync(self):
        mock_cos = [_make_company("co1"), _make_company("co2")]
        with patch("app.discover.greenhouse.discover", return_value=mock_cos):
            result = asyncio.run(self.provider.discover(slugs=["co1", "co2"], limit=50))
            assert len(result) == 2
