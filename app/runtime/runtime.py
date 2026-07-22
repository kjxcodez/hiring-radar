from pathlib import Path
from typing import Any, Optional, List
import logging

from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource
from app.runtime.execution import Execution
from app.runtime.queue import JobQueue
from app.runtime.scheduler import Scheduler
from app.runtime.locks import LockManager
from app.runtime.history import ExecutionHistory

logger = logging.getLogger(__name__)


class ExecutionRuntime:
    """The central execution runtime managing job queues, schedules, locking, and worker threads."""

    def __init__(self, container: Any, settings: Any) -> None:
        self.container = container
        self.settings = settings
        
        output_dir = Path(settings.output_dir) if settings else Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.queue = JobQueue(output_dir / "queue.json")
        self.scheduler = Scheduler(output_dir / "schedules.json")
        self.locks = LockManager(output_dir / "locks")
        self.history = ExecutionHistory(output_dir / "executions.json")
        
        from app.runtime.worker import Worker
        self.worker = Worker(self)

    @property
    def workflow_engine(self) -> Any:
        """Expose parent WorkflowEngine driver."""
        return self.container.workflow_engine

    def submit(
        self,
        workflow_name: str,
        trigger: TriggerSource = TriggerSource.MANUAL,
        priority: int = 0,
        **kwargs: Any
    ) -> Execution:
        """Enqueue a workflow for asynchronous background worker processing.

        Args:
            workflow_name: Alias name of the target workflow.
            trigger: The TriggerSource initiator.
            priority: Enqueue priority level (higher numbers execute first).
            **kwargs: Metadatas and inputs passed down to context.

        Returns:
            The queued Execution record.
        """
        execution = Execution(
            workflow_name=workflow_name,
            status=ExecutionStatus.QUEUED,
            trigger=trigger,
            metadata=kwargs,
        )
        self.history.record(execution)
        self.queue.enqueue(execution, priority=priority)
        logger.info("Enqueued workflow '%s' asynchronously (ID: %s)", workflow_name, execution.id)
        return execution

    def execute(
        self,
        workflow_name: str,
        context: Optional[Any] = None,
        trigger: TriggerSource = TriggerSource.MANUAL,
        **kwargs: Any
    ) -> Any:
        """Execute a workflow synchronously, blocking and logging execution history.

        Args:
            workflow_name: Alias name of the target workflow.
            context: Optional custom execution context override.
            trigger: The TriggerSource initiator.
            **kwargs: Metadatas and inputs passed down to context.

        Returns:
            The output result of the executed workflow.
        """
        import uuid
        exec_id = context.execution_id if context else str(uuid.uuid4())
        execution = Execution(
            id=exec_id,
            workflow_name=workflow_name,
            status=ExecutionStatus.RUNNING,
            trigger=trigger,
            metadata=kwargs,
        )
        
        import datetime
        execution.started_at = datetime.datetime.utcnow()
        self.history.record(execution)
        
        lock_name = f"wf_{workflow_name}"
        if not self.locks.acquire(lock_name, timeout=10.0):
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.datetime.utcnow()
            execution.duration = 0.0
            execution.error = f"Lock acquisition timeout for '{workflow_name}'"
            self.history.record(execution)
            raise RuntimeError(f"Workflow '{workflow_name}' is locked by another execution.")

        try:
            # Sync execution ID back to context
            if context:
                execution.id = context.execution_id
            else:
                from app.workflows.context import WorkflowContext
                context = WorkflowContext(
                    settings=self.settings,
                    container=self.container,
                    execution_id=execution.id,
                    metadata=kwargs,
                )
                
            result = self.workflow_engine.execute(
                workflow_name=workflow_name,
                context=context,
                **kwargs
            )
            
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.datetime.utcnow()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.result = result
            execution.error = None
            self.history.record(execution)
            return result
            
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.datetime.utcnow()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.error = str(e)
            self.history.record(execution)
            raise e
        finally:
            self.locks.release(lock_name)

    def cancel(self, execution_id: str) -> bool:
        """Cancel a running or queued execution by ID."""
        import datetime
        
        # 1. Cancel in queue
        if self.queue.cancel(execution_id):
            execution = self.history.find_by_id(execution_id)
            if execution:
                execution.status = ExecutionStatus.CANCELLED
                execution.completed_at = datetime.datetime.utcnow()
                self.history.record(execution)
            logger.info("Cancelled queued execution %s", execution_id)
            return True
            
        # 2. Cancel in engine
        if self.workflow_engine.cancel(execution_id):
            execution = self.history.find_by_id(execution_id)
            if execution:
                execution.status = ExecutionStatus.CANCELLED
                execution.completed_at = datetime.datetime.utcnow()
                self.history.record(execution)
            logger.info("Cancelled active running execution %s", execution_id)
            return True
            
        return False

    def resume(self, execution_id: str) -> Any:
        """Resume execution. Currently unsupported."""
        raise NotImplementedError("Workflow resumption is not supported in this version.")

    def status(self, execution_id: str) -> Optional[Execution]:
        """Find execution record by ID."""
        return self.history.find_by_id(execution_id)

    def list_active(self) -> List[Execution]:
        """Return list of active execution models."""
        active = []
        for exec_id in list(self.workflow_engine.active_contexts.keys()):
            exec_model = self.history.find_by_id(exec_id)
            if exec_model:
                active.append(exec_model)
        return active
