"""Serialization and deserialization logic for Pydantic models."""

from __future__ import annotations

from typing import Any, TypeVar
import orjson
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def serialize(data: Any) -> bytes:
    """Serialize arbitrary Python data to JSON bytes using orjson."""
    return orjson.dumps(data, option=orjson.OPT_INDENT_2)


def deserialize(raw: bytes) -> Any:
    """Deserialize raw JSON bytes into a Python object using orjson."""
    if not raw:
        return None
    return orjson.loads(raw)


def serialize_model_list(models: list[BaseModel]) -> bytes:
    """Serialize a list of Pydantic models to JSON bytes."""
    serialized = [m.model_dump(mode="json") for m in models]
    return serialize(serialized)


def deserialize_model_list(raw: bytes, model_type: type[T]) -> list[T]:
    """Deserialize JSON bytes into a list of Pydantic models of model_type."""
    data = deserialize(raw)
    if not data or not isinstance(data, list):
        return []
    return [model_type.model_validate(item) for item in data]


def serialize_model_dict(models: dict[str, BaseModel]) -> bytes:
    """Serialize a mapping of string keys to Pydantic models to JSON bytes."""
    serialized = {k: m.model_dump(mode="json") for k, m in models.items()}
    return serialize(serialized)


def deserialize_model_dict(raw: bytes, model_type: type[T]) -> dict[str, T]:
    """Deserialize JSON bytes into a mapping of string keys to Pydantic models."""
    data = deserialize(raw)
    if not data or not isinstance(data, dict):
        return {}
    return {k: model_type.model_validate(v) for k, v in data.items()}
