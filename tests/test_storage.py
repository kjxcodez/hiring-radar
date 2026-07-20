from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

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
from app.storage.json_storage import JsonStorage


class DummyModel(BaseModel):
    id: int
    name: str


def test_filesystem_operations(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    assert not Filesystem.exists(file_path)

    Filesystem.write_bytes(file_path, b"hello")
    assert Filesystem.exists(file_path)
    assert Filesystem.read_bytes(file_path) == b"hello"

    Filesystem.delete(file_path)
    assert not Filesystem.exists(file_path)


def test_serialization():
    data = {"foo": "bar", "count": 42}
    raw = serialize(data)
    assert isinstance(raw, bytes)
    assert deserialize(raw) == data


def test_model_list_serialization():
    models = [DummyModel(id=1, name="Alice"), DummyModel(id=2, name="Bob")]
    raw = serialize_model_list(models)
    assert isinstance(raw, bytes)

    deserialized = deserialize_model_list(raw, DummyModel)
    assert len(deserialized) == 2
    assert deserialized[0].id == 1
    assert deserialized[0].name == "Alice"
    assert deserialized[1].name == "Bob"


def test_model_dict_serialization():
    models = {
        "alice": DummyModel(id=1, name="Alice"),
        "bob": DummyModel(id=2, name="Bob"),
    }
    raw = serialize_model_dict(models)
    assert isinstance(raw, bytes)

    deserialized = deserialize_model_dict(raw, DummyModel)
    assert len(deserialized) == 2
    assert deserialized["alice"].id == 1
    assert deserialized["alice"].name == "Alice"
    assert deserialized["bob"].name == "Bob"


def test_atomic_write(tmp_path: Path):
    file_path = tmp_path / "atomic.json"
    atomic_write(file_path, b'{"status": "ok"}')

    assert file_path.exists()
    assert file_path.read_bytes() == b'{"status": "ok"}'


def test_atomic_write_backup(tmp_path: Path):
    file_path = tmp_path / "atomic.json"
    backup_path = tmp_path / "atomic.json.backup"

    # Initial write
    atomic_write(file_path, b'{"version": 1}')
    assert not backup_path.exists()

    # Second write with backup enabled
    atomic_write(file_path, b'{"version": 2}', backup=True)
    assert file_path.read_bytes() == b'{"version": 2}'
    assert backup_path.exists()
    assert backup_path.read_bytes() == b'{"version": 1}'


def test_json_storage_orchestration(tmp_path: Path):
    storage = JsonStorage()
    file_path = tmp_path / "data.json"

    assert not storage.exists(file_path)
    assert storage.read(file_path) is None

    data = {"items": [1, 2, 3]}
    storage.write(file_path, data)
    assert storage.exists(file_path)
    assert storage.read(file_path) == data

    storage.delete(file_path)
    assert not storage.exists(file_path)


def test_graceful_recovery_on_corrupt_file(tmp_path: Path):
    storage = JsonStorage()
    file_path = tmp_path / "corrupt.json"

    # Write corrupt data
    file_path.write_bytes(b"invalid-json-data{")

    # Storage read should gracefully return None or fail (handled by caller)
    # Wait, deserialize raises orjson.JSONDecodeError, let's verify if storage.read raises or catches it.
    # In our implementation of JsonStorage.read, it does not catch exceptions, it lets the caller handle them.
    # Let's verify that it propagates the error so the repository can catch it.
    with pytest.raises(Exception):
        storage.read(file_path)
