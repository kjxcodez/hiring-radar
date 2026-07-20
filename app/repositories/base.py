"""Repository Protocols for Hiring Radar."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


@runtime_checkable
class SupportsLoad(Protocol[T_co]):
    """Protocol for repositories that support loading data."""

    def load_all(self) -> T_co:
        """Load all records from persistence."""
        ...


@runtime_checkable
class SupportsSave(Protocol[T_contra]):
    """Protocol for repositories that support saving data."""

    def save_all(self, data: T_contra) -> None:
        """Save all records back to persistence."""
        ...


@runtime_checkable
class Repository(Protocol):
    """Marker protocol for all repository classes."""
    pass
