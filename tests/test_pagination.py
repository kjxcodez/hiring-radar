"""Tests for PaginationState."""

from __future__ import annotations

import pytest

from app.discovery.pagination import PaginationState


class TestPaginationState:

    def test_default_has_more_false(self):
        """Default state is terminal — single-page providers don't paginate."""
        state = PaginationState()
        assert state.has_more is False

    def test_advance_page(self):
        state = PaginationState(page=1, has_more=True)
        next_state = state.advance_page()
        assert next_state.page == 2
        assert next_state.has_more is True
        # Original unchanged
        assert state.page == 1

    def test_advance_offset(self):
        state = PaginationState(offset=0)
        next_state = state.advance_offset(50)
        assert next_state.offset == 50
        assert state.offset == 0

    def test_with_cursor(self):
        state = PaginationState()
        next_state = state.with_cursor("tok_abc123", has_more=True)
        assert next_state.cursor == "tok_abc123"
        assert next_state.has_more is True

    def test_with_cursor_none_stops_iteration(self):
        state = PaginationState(has_more=True)
        next_state = state.with_cursor(None, has_more=False)
        assert next_state.cursor is None
        assert next_state.has_more is False

    def test_with_next_url(self):
        state = PaginationState()
        next_state = state.with_next_url("https://api.example.com/jobs?page=2")
        assert next_state.next_url == "https://api.example.com/jobs?page=2"
        assert next_state.has_more is True

    def test_with_next_url_none_sets_has_more_false(self):
        state = PaginationState(has_more=True)
        next_state = state.with_next_url(None)
        assert next_state.has_more is False

    def test_done(self):
        state = PaginationState(page=5, cursor="tok", has_more=True)
        terminal = state.done()
        assert terminal.has_more is False
        assert terminal.next_url is None
        # Extra state preserved
        assert terminal.page == 5

    def test_extra_preserved_through_transitions(self):
        state = PaginationState(extra={"total": 200})
        next_state = state.advance_page()
        assert next_state.extra["total"] == 200

    def test_immutability_of_transitions(self):
        """Each transition returns a new object, original is unchanged."""
        original = PaginationState(page=1, cursor="old", has_more=True)
        _ = original.with_cursor("new")
        assert original.cursor == "old"
