"""Pre-persistence filtering for the discovery engine.

Delegates to the existing ``app.filters.apply_filters`` function so that
filter logic remains in a single canonical location.  This module simply
provides a cleaner object-oriented entry point for the coordinator.

Usage::

    from app.discovery.filters import DiscoveryFilter

    f = DiscoveryFilter()
    filtered = f.apply(companies, remote=True, country="india")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.models import Company

if TYPE_CHECKING:
    from app.profiles import SearchProfile


class DiscoveryFilter:
    """Thin wrapper around ``app.filters.apply_filters`` for use in the coordinator.

    Applying filters before persistence avoids writing companies to disk that
    don't match the user's search criteria.  The coordinator calls this after
    all providers have completed but before the results reach the repository.
    """

    def apply(
        self,
        companies: list[Company],
        *,
        remote: Optional[bool] = None,
        country: Optional[str] = None,
        keyword: Optional[str] = None,
        exclude: Optional[str] = None,
        days: Optional[int] = None,
        profile: Optional["SearchProfile"] = None,
    ) -> list[Company]:
        """Filter *companies* using the canonical filter engine.

        Args:
            companies: Discovered companies to filter.
            remote:    ``True`` to keep only remote jobs; ``False`` for
                       non-remote; ``None`` to skip the check.
            country:   Required substring in job location (case-insensitive).
            keyword:   Required substring in job title (case-insensitive).
            exclude:   Term to exclude from job titles (case-insensitive).
            days:      Drop jobs posted more than *days* days ago.
            profile:   Search profile with compound filter criteria.

        Returns:
            A filtered list of :class:`~app.models.Company` objects.
            Companies with zero matching jobs after filtering are omitted.
        """
        # No filters active — return as-is (fast path)
        if (
            remote is None
            and not country
            and not keyword
            and not exclude
            and days is None
            and profile is None
        ):
            return companies

        from app.filters import apply_filters
        return apply_filters(
            companies,
            profile=profile,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
        )
