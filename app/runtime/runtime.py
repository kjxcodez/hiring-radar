from pathlib import Path
from typing import Any, Optional, List
import logging, uuid, datetime

from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource
from app.runtime.execution import Execution
from app.runtime.queue import JobQueue
from app.runtime.scheduler import Scheduler
from app.runtime.locks import LockManager
from app.runtime.history import ExecutionHistory
from app.runtime.task import TaskGraph
from app.runtime.recovery import RecoveryEngine
from app.runtime.worker import Worker

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
        
        # Crash recovery engine initialization
        self.recovery = RecoveryEngine(output_dir)
        self.active_graphs = {}
        
        # Auto-resume recovered state if enabled
        recovered = self.recovery.load_state()
        if recovered and getattr(settings, "auto_resume", True):
            for gid, graph in recovered.items():
                self.active_graphs[gid] = graph
                logger.info("Recovered active task graph execution: %s", gid)

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
        exec_id = context.execution_id if context else str(uuid.uuid4())
        execution = Execution(
            id=exec_id,
            workflow_name=workflow_name,
            status=ExecutionStatus.RUNNING,
            trigger=trigger,
            metadata=kwargs,
        )
        
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

    def submit_graph(self, graph: TaskGraph, priority: int = 0) -> Execution:
        """Enqueue a TaskGraph execution."""
        from app.runtime.execution import Execution
        from app.runtime.state import ExecutionStatus
        execution = Execution(
            workflow_name=f"graph_{graph.graph_id}",
            status=ExecutionStatus.QUEUED,
            task_graph=graph
        )
        self.history.record(execution)
        self.queue.enqueue(execution, priority=priority)
        
        self.active_graphs[graph.graph_id] = graph
        self.recovery.save_state(self.active_graphs)
        return execution

    def pause(self, execution_id: str) -> bool:
        """Pause a running or queued task graph execution."""
        from app.runtime.task import TaskStatus
        execution = self.queue.get_execution(execution_id)
        if not execution:
            execution = self.history.find_by_id(execution_id)
        if not execution:
            return False
            
        execution.status = ExecutionStatus.PAUSED
        self.history.record(execution)
        
        self.queue.enqueue(execution, priority=execution.metadata.get("priority", 0))
        if execution.task_graph:
            self.active_graphs[execution.task_graph.graph_id] = execution.task_graph
            for task in execution.task_graph.tasks.values():
                if task.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING):
                    task.status = TaskStatus.PAUSED
            self.recovery.save_state(self.active_graphs)
        return True

    def resume(self, execution_id: str) -> bool:
        """Resume a paused execution graph."""
        from app.runtime.task import TaskStatus
        execution = self.queue.get_execution(execution_id)
        if not execution:
            execution = self.history.find_by_id(execution_id)
        if not execution:
            return False
            
        execution.status = ExecutionStatus.QUEUED
        self.history.record(execution)
        
        self.queue.enqueue(execution, priority=execution.metadata.get("priority", 0))
        if execution.task_graph:
            self.active_graphs[execution.task_graph.graph_id] = execution.task_graph
            for task in execution.task_graph.tasks.values():
                if task.status == TaskStatus.PAUSED:
                    task.status = TaskStatus.PENDING
            self.recovery.save_state(self.active_graphs)
        return True

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
