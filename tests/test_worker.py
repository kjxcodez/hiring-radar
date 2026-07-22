from __future__ import annotations

import datetime
import time
from unittest.mock import MagicMock, patch
import pytest

from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource
from app.runtime.execution import Execution
from app.runtime.worker import Worker


class MockRuntime:
    def __init__(self):
        self.container = MagicMock()
        self.settings = MagicMock()
        self.settings.output_dir = "mock_output"
        self.queue = MagicMock()
        self.scheduler = MagicMock()
        self.locks = MagicMock()
        self.history = MagicMock()
        self.workflow_engine = MagicMock()


@patch("app.runtime.worker.logger")
def test_worker_job_execution_success(mock_logger):
    runtime = MockRuntime()
    worker = Worker(runtime)

    # 1. Mock scheduler and queue
    runtime.scheduler.tick.return_value = []
    
    execution = Execution(workflow_name="discover")
    runtime.queue.dequeue.side_effect = [execution, None]
    
    # 2. Mock locks
    runtime.locks.acquire.return_value = True

    # 3. Mock engine run
    runtime.workflow_engine.execute.return_value = "success_val"

    # Start worker and run one iteration manually
    worker._run_loop = MagicMock() # bypass loop
    
    # Invoke one job execution loop manually
    worker._execute_job(execution)

    # Verify locks acquired and released
    runtime.locks.acquire.assert_called_once_with("wf_discover")
    runtime.locks.release.assert_called_once_with("wf_discover")

    # Verify execution finished successfully
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.result == "success_val"
    assert execution.error is None
    assert runtime.history.record.call_count == 2 # 1 for running, 1 for completed


@patch("app.runtime.worker.logger")
def test_worker_job_execution_failure_retry(mock_logger):
    runtime = MockRuntime()
    worker = Worker(runtime)

    runtime.scheduler.tick.return_value = []
    execution = Execution(workflow_name="discover", retry_count=0, max_retries=3)
    runtime.queue.dequeue.side_effect = [execution, None]
    runtime.locks.acquire.return_value = True

    # Mock engine execution error
    runtime.workflow_engine.execute.side_effect = ValueError("Engine fail")

    # Execute job
    worker._execute_job(execution)

    # Verify it transitions to RETRYING and enqueues back to queue
    assert execution.status == ExecutionStatus.RETRYING
    assert execution.retry_count == 1
    assert "run_after" in execution.metadata
    runtime.queue.enqueue.assert_called_once_with(execution, priority=0)
    runtime.locks.release.assert_called_once_with("wf_discover")


@patch("app.runtime.worker.logger")
def test_worker_job_execution_permanent_failure(mock_logger):
    runtime = MockRuntime()
    worker = Worker(runtime)

    runtime.scheduler.tick.return_value = []
    # Max retries reached
    execution = Execution(workflow_name="discover", retry_count=3, max_retries=3)
    runtime.queue.dequeue.side_effect = [execution, None]
    runtime.locks.acquire.return_value = True
    runtime.workflow_engine.execute.side_effect = ValueError("Final fail")

    worker._execute_job(execution)

    # Verify transition to FAILED and no re-queueing
    assert execution.status == ExecutionStatus.FAILED
    runtime.queue.enqueue.assert_not_called()
