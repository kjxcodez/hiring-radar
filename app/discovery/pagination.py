"""Pagination state management for multi-page provider fetches.

Providers that support pagination (e.g. future Workable, Greenhouse Boards)
use ``PaginationState`` to track cursor/offset position and signal when all
pages have been consumed.

Current providers (Greenhouse, Lever, Ashby, Workable, BambooHR, RemoteOK,
WWR) are all single-request — they set ``has_more=False`` immediately after
their first fetch.  ``PaginationState`` is included here so future providers
can adopt it without changes to the coordinator.

Usage::

    state = PaginationState()

    while state.has_more:
        data, state = await provider.fetch_page(state)
        process(data)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaginationState:
    """Mutable cursor for paginated provider fetches.

    Providers advance this object as they consume pages.  When no more data
    is available they set ``has_more = False``.

    Attributes:
        page:       Current page number (1-indexed for page-number APIs).
        offset:     Current byte/item offset (for offset-based APIs).
        cursor:     Opaque cursor token returned by the upstream API.
        next_url:   Full URL of the next page (for link-header APIs).
        has_more:   ``True`` while more pages remain, ``False`` when done.
        extra:      Provider-specific auxiliary state (e.g. total_count).
    """

    page: int = 1
    offset: int = 0
    cursor: str | None = None
    next_url: str | None = None
    has_more: bool = False          # Conservative default — single-page providers
    extra: dict[str, Any] = field(default_factory=dict)

    def advance_page(self) -> "PaginationState":
        """Return a new state with page incremented by 1."""
        return PaginationState(
            page=self.page + 1,
            offset=self.offset,
            cursor=self.cursor,
            next_url=self.next_url,
            has_more=self.has_more,
            extra=self.extra.copy(),
        )

    def advance_offset(self, step: int) -> "PaginationState":
        """Return a new state with offset advanced by *step* items."""
        return PaginationState(
            page=self.page,
            offset=self.offset + step,
            cursor=self.cursor,
            next_url=self.next_url,
            has_more=self.has_more,
            extra=self.extra.copy(),
        )

    def with_cursor(self, cursor: str | None, has_more: bool = True) -> "PaginationState":
        """Return a new state with an updated cursor token."""
        return PaginationState(
            page=self.page,
            offset=self.offset,
            cursor=cursor,
            next_url=self.next_url,
            has_more=has_more,
            extra=self.extra.copy(),
        )

    def with_next_url(self, url: str | None) -> "PaginationState":
        """Return a new state with a link-header next URL."""
        return PaginationState(
            page=self.page,
            offset=self.offset,
            cursor=self.cursor,
            next_url=url,
            has_more=url is not None,
            extra=self.extra.copy(),
        )

    def done(self) -> "PaginationState":
        """Return a terminal state signalling no more pages."""
        return PaginationState(
            page=self.page,
            offset=self.offset,
            cursor=self.cursor,
            next_url=None,
            has_more=False,
            extra=self.extra.copy(),
        )
