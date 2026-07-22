"""Tests for RemoteOKProvider — feed-based, limit routing."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from app.discovery.providers.remoteok import RemoteOKProvider
from app.models import Company, JobPosting


def _make_company(name: str) -> Company:
    return Company(
        name=name,
        jobs=[
            JobPosting(
                job_title="Remote Dev",
                job_url=f"https://remoteok.com/{name.lower()}",
                remote_type="remote",
                source="remoteok",
            )
        ],
        discovered_at=datetime.now(),
        last_updated=datetime.now(),
    )


class TestRemoteOKProvider:

    def setup_method(self):
        self.provider = RemoteOKProvider()

    def test_name(self):
        assert self.provider.name == "remoteok"

    def test_is_feed_based(self):
        assert self.provider.is_feed_based() is True

    def test_discover_passes_limit_to_sync(self):
        mock_cos = [_make_company("acme"), _make_company("beta")]
        with patch("app.discover.remoteok.discover", return_value=mock_cos) as mock_fn:
            result = asyncio.run(self.provider.discover(slugs=[], limit=25))
            mock_fn.assert_called_once_with(limit=25)
            assert len(result) == 2

    def test_discover_ignores_slugs(self):
        """Feed-based: slugs argument is irrelevant and should be ignored."""
        with patch("app.discover.remoteok.discover", return_value=[]) as mock_fn:
            asyncio.run(self.provider.discover(slugs=["ignored1", "ignored2"], limit=10))
            mock_fn.assert_called_once_with(limit=10)

    def test_discover_handles_exception_gracefully(self):
        with patch("app.discover.remoteok.discover", side_effect=RuntimeError("boom")):
            result = asyncio.run(self.provider.discover(slugs=[], limit=10))
            assert result == []

    def test_low_concurrency_default(self):
        assert self.provider.default_concurrency == 1
        assert self.provider.default_rate_limit_rps <= 1.0
