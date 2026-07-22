from __future__ import annotations

import time
import pytest
from app.runtime.locks import LockManager


@pytest.fixture
def temp_lock_dir(tmp_path):
    return tmp_path / "locks"


def test_lock_acquire_and_release(temp_lock_dir):
    lock_mgr = LockManager(temp_lock_dir)
    lock_name = "test_lock"

    # Verify initial state
    assert not lock_mgr.is_locked(lock_name)

    # First acquire succeeds
    assert lock_mgr.acquire(lock_name)
    assert lock_mgr.is_locked(lock_name)

    # Secondary acquire fails immediately
    assert not lock_mgr.acquire(lock_name)

    # Release and verify it is unlocked
    lock_mgr.release(lock_name)
    assert not lock_mgr.is_locked(lock_name)


def test_lock_acquire_timeout(temp_lock_dir):
    lock_mgr = LockManager(temp_lock_dir)
    lock_name = "timeout_lock"

    # Lock it
    assert lock_mgr.acquire(lock_name)

    # Acquire with timeout should block and fail after timeout expires
    start = time.time()
    acquired = lock_mgr.acquire(lock_name, timeout=0.3)
    duration = time.time() - start

    assert not acquired
    assert duration >= 0.3
