import datetime
import logging
import threading
import time
from typing import Any, Optional

from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource
from app.runtime.execution import Execution
from app.workflows.context import WorkflowContext

logger = logging.getLogger(__name__)


class Worker:
    """Daemon execution worker running jobs in a background thread."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="HiringRadarWorker")
        self._thread.start()
        logger.info("Background worker thread started.")

    def stop(self) -> None:
        """Stop the background worker thread."""
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("Background worker thread stopped.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                # 1. Tick scheduler to check for cron/interval jobs
                due_jobs = self.runtime.scheduler.tick()
                for job in due_jobs:
                    self.runtime.submit(
                        job.workflow_name,
                        trigger=TriggerSource.CRON,
                        **job.kwargs
                    )

                # 2. Dequeue next runnable job
                execution = self.runtime.queue.dequeue()
                if execution:
                    self._execute_job(execution)
                else:
                    time.sleep(1.0)
            except Exception as e:
                logger.error("Error in background worker loop: %s", e)
                time.sleep(1.0)

    def _execute_job(self, execution: Execution) -> None:
        logger.info("Worker executing job %s (%s)", execution.id, execution.workflow_name)
        
        lock_name = f"wf_{execution.workflow_name}"
        if not self.runtime.locks.acquire(lock_name):
            logger.warning("Workflow %s is locked. Re-queueing job %s.", execution.workflow_name, execution.id)
            # Re-enqueue with a short delay (10s)
            delay_until = (datetime.datetime.utcnow() + datetime.timedelta(seconds=10)).isoformat()
            execution.metadata["run_after"] = delay_until
            self.runtime.queue.enqueue(execution, priority=execution.metadata.get("priority", 0))
            return

        try:
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.datetime.utcnow()
            self.runtime.history.record(execution)

            # Create workflow context with matching execution ID for status/cancellation integration
            context = WorkflowContext(
                settings=self.runtime.settings,
                container=self.runtime.container,
                execution_id=execution.id,
            )

            result = self.runtime.workflow_engine.execute(
                execution.workflow_name,
                context=context,
                **execution.metadata
            )

            # Record successful completion
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.datetime.utcnow()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.result = result
            execution.error = None
            self.runtime.history.record(execution)
            logger.info("Job %s completed successfully in %.2fs", execution.id, execution.duration)

        except Exception as e:
            execution.completed_at = datetime.datetime.utcnow()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.error = str(e)
            
            # Check for retries
            if execution.retry_count < execution.max_retries:
                execution.status = ExecutionStatus.RETRYING
                execution.retry_count += 1
                self.runtime.history.record(execution)
                
                # Exponential backoff retry delay: 2^retry_count * 10 seconds
                delay_sec = (2 ** execution.retry_count) * 10
                delay_until = (datetime.datetime.utcnow() + datetime.timedelta(seconds=delay_sec)).isoformat()
                execution.metadata["run_after"] = delay_until
                
                logger.warning(
                    "Job %s failed (%s). Retrying (%d/%d) in %ds...",
                    execution.id, e, execution.retry_count, execution.max_retries, delay_sec
                )
                self.runtime.queue.enqueue(execution, priority=execution.metadata.get("priority", 0))
            else:
                execution.status = ExecutionStatus.FAILED
                self.runtime.history.record(execution)
                logger.error("Job %s failed permanently. Error: %s", execution.id, e)

        finally:
            self.runtime.locks.release(lock_name)
