"""Tests for LeverProvider — mocked HTTP, error handling."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from app.discovery.providers.lever import LeverProvider
from app.models import Company, JobPosting


def _make_company(name: str) -> Company:
    return Company(
        name=name,
        ats_platform="lever",
        ats_slug=name.lower(),
        jobs=[
            JobPosting(
                job_title="Product Manager",
                job_url=f"https://jobs.lever.co/{name.lower()}/123",
                source="lever",
            )
        ],
        discovered_at=datetime.now(),
        last_updated=datetime.now(),
    )


class TestLeverProvider:

    def setup_method(self):
        self.provider = LeverProvider()

    def test_name(self):
        assert self.provider.name == "lever"

    def test_is_not_feed_based(self):
        assert self.provider.is_feed_based() is False

    def test_discover_empty_slugs_returns_empty(self):
        result = asyncio.run(self.provider.discover(slugs=[], limit=50))
        assert result == []

    def test_discover_delegates_to_sync_module(self):
        mock_cos = [_make_company("notion")]
        with patch("app.discover.lever.discover", return_value=mock_cos) as mock_fn:
            result = asyncio.run(self.provider.discover(slugs=["notion"], limit=50))
            mock_fn.assert_called_once_with(["notion"])
            assert result[0].name == "notion"

    def test_discover_handles_exception_gracefully(self):
        with patch("app.discover.lever.discover", side_effect=ConnectionError("net fail")):
            result = asyncio.run(self.provider.discover(slugs=["x"], limit=10))
            assert result == []

    def test_concurrency_higher_than_greenhouse(self):
        assert self.provider.default_concurrency == 8
