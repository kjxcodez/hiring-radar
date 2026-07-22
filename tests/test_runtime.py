from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.runtime.runtime import ExecutionRuntime
from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


def test_runtime_submit_and_status(temp_dir):
    container = MagicMock()
    settings = MagicMock()
    settings.output_dir = temp_dir

    runtime = ExecutionRuntime(container, settings)

    # Submit job
    execution = runtime.submit("discover", trigger=TriggerSource.MANUAL, priority=5, param1="val1")
    assert execution.id is not None
    assert execution.status == ExecutionStatus.QUEUED
    assert execution.workflow_name == "discover"
    assert execution.metadata["param1"] == "val1"
    assert execution.metadata["priority"] == 5

    # Check status
    fetched = runtime.status(execution.id)
    assert fetched is not None
    assert fetched.id == execution.id
    assert fetched.status == ExecutionStatus.QUEUED


def test_runtime_execute_sync_success(temp_dir):
    container = MagicMock()
    settings = MagicMock()
    settings.output_dir = temp_dir

    # Mock workflow engine execution
    mock_engine = MagicMock()
    mock_engine.execute.return_value = "sync_result"
    container.workflow_engine = mock_engine

    runtime = ExecutionRuntime(container, settings)

    # Run execute synchronously
    res = runtime.execute("discover", trigger=TriggerSource.CLI, custom_arg="x")

    assert res == "sync_result"
    mock_engine.execute.assert_called_once()
    
    # Check history logs
    history = runtime.history.load_all()
    assert len(history) == 1
    logged = list(history.values())[0]
    assert logged.status == ExecutionStatus.COMPLETED
    assert logged.workflow_name == "discover"
    assert logged.result == "sync_result"


def test_runtime_cancel_queued(temp_dir):
    container = MagicMock()
    settings = MagicMock()
    settings.output_dir = temp_dir

    runtime = ExecutionRuntime(container, settings)

    # Submit job to queue
    execution = runtime.submit("discover")
    assert len(runtime.queue.list_queued()) == 1

    # Cancel job
    assert runtime.cancel(execution.id)
    assert len(runtime.queue.list_queued()) == 0

    # Status updated in history
    status_rec = runtime.status(execution.id)
    assert status_rec.status == ExecutionStatus.CANCELLED
