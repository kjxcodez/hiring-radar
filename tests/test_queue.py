from __future__ import annotations

import datetime
import pytest
from app.runtime.execution import Execution
from app.runtime.queue import JobQueue
from app.storage.json_storage import JsonStorage


@pytest.fixture
def temp_queue_file(tmp_path):
    return tmp_path / "queue.json"


def test_queue_fifo_ordering(temp_queue_file):
    storage = JsonStorage()
    queue = JobQueue(temp_queue_file, storage=storage)

    exec1 = Execution(workflow_name="discover")
    exec2 = Execution(workflow_name="enrich")

    # Enqueue in order
    queue.enqueue(exec1, priority=0)
    queue.enqueue(exec2, priority=0)

    # Dequeue is FIFO
    dq1 = queue.dequeue()
    dq2 = queue.dequeue()

    assert dq1 is not None
    assert dq2 is not None
    assert dq1.id == exec1.id
    assert dq2.id == exec2.id
    assert queue.dequeue() is None


def test_queue_priority_ordering(temp_queue_file):
    storage = JsonStorage()
    queue = JobQueue(temp_queue_file, storage=storage)

    exec_low = Execution(workflow_name="discover")
    exec_high = Execution(workflow_name="enrich")

    # Enqueue low priority first
    queue.enqueue(exec_low, priority=0)
    queue.enqueue(exec_high, priority=10)

    # Dequeue retrieves high priority first
    dq1 = queue.dequeue()
    dq2 = queue.dequeue()

    assert dq1.id == exec_high.id
    assert dq2.id == exec_low.id


def test_queue_delayed_jobs(temp_queue_file):
    storage = JsonStorage()
    queue = JobQueue(temp_queue_file, storage=storage)

    exec_delayed = Execution(workflow_name="discover")
    # Set run_after in future
    future_time = (datetime.datetime.utcnow() + datetime.timedelta(seconds=60)).isoformat()
    exec_delayed.metadata["run_after"] = future_time

    exec_now = Execution(workflow_name="enrich")

    queue.enqueue(exec_delayed, priority=10) # Higher priority but delayed
    queue.enqueue(exec_now, priority=0)

    # Delayed job is skipped, exec_now dequeued first
    dq1 = queue.dequeue()
    assert dq1.id == exec_now.id
    assert queue.dequeue() is None


def test_queue_cancellation(temp_queue_file):
    storage = JsonStorage()
    queue = JobQueue(temp_queue_file, storage=storage)

    exec1 = Execution(workflow_name="discover")
    queue.enqueue(exec1)

    assert queue.cancel(exec1.id)
    assert len(queue.list_queued()) == 0
    assert not queue.cancel("nonexistent-id")
