"""Domain-specific exceptions for Hiring Radar.

All domain exceptions inherit from HiringRadarError. Standard exception types
are mixed in where appropriate to maintain backwards-compatibility with existing
test suites and catch-blocks.
"""

from __future__ import annotations


class HiringRadarError(Exception):
    """Base exception class for all errors in Hiring Radar."""
    pass


class CompanyNotFoundError(HiringRadarError, ValueError):
    """Raised when a specific company cannot be found in the repository."""
    pass


class MultipleCompaniesFoundError(HiringRadarError, ValueError):
    """Raised when a query matches multiple companies when a unique one was expected."""
    pass


class DiscoveryError(HiringRadarError):
    """Raised when error conditions are met during discovery."""
    pass


class ScrapingError(HiringRadarError):
    """Raised when scraping or content extraction fails."""
    pass


class ResumeError(HiringRadarError, ValueError):
    """Raised when resume parsing, scoring, or tailoring suggestions fail."""
    pass


class OutreachError(HiringRadarError):
    """Raised when email/Telegram notifications or connections fail."""
    pass


class RecommendationError(HiringRadarError):
    """Raised when recommendation calculations fail."""
    pass
