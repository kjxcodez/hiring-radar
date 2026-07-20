"""Storage abstraction package for Hiring Radar.

Decouples persistence layers from specific database, filesystem, or
serialization technologies.
"""

from __future__ import annotations

from app.storage.json_storage import JsonStorage
from app.storage.filesystem import Filesystem
from app.storage.atomic import atomic_write
from app.storage.serializer import (
    serialize,
    deserialize,
    serialize_model_list,
    deserialize_model_list,
    serialize_model_dict,
    deserialize_model_dict,
)

__all__ = [
    "JsonStorage",
    "Filesystem",
    "atomic_write",
    "serialize",
    "deserialize",
    "serialize_model_list",
    "deserialize_model_list",
    "serialize_model_dict",
    "deserialize_model_dict",
]
