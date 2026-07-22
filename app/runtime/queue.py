import datetime
from pathlib import Path
from typing import Optional, List
from app.runtime.execution import Execution
from app.storage.json_storage import JsonStorage
from app.runtime.state import ExecutionStatus


class JobQueue:
    """Manages a persistent FIFO execution queue with priority and delay support."""

    def __init__(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def enqueue(self, execution: Execution, priority: int = 0) -> None:
        """Add a job to the queue."""
        execution.metadata["priority"] = priority
        execution.status = ExecutionStatus.QUEUED
        
        queue_data = self._load()
        # Remove if already exists (e.g. re-enqueuing / retrying)
        queue_data = [item for item in queue_data if item.get("id") != execution.id]
        queue_data.append(execution.model_dump(mode="json"))
        self._save(queue_data)

    def dequeue(self) -> Optional[Execution]:
        """Retrieve and remove the highest priority runnable job from the queue."""
        queue_data = self._load()
        if not queue_data:
            return None
        
        now = datetime.datetime.utcnow()
        selectable = []
        
        for idx, item in enumerate(queue_data):
            exec_model = Execution(**item)
            run_after_str = exec_model.metadata.get("run_after")
            if run_after_str:
                try:
                    run_after = datetime.datetime.fromisoformat(run_after_str)
                    if now < run_after:
                        continue  # Skip delayed / backing off jobs
                except ValueError:
                    pass
            
            priority = exec_model.metadata.get("priority", 0)
            selectable.append((idx, priority, exec_model.submitted_at, exec_model))
            
        if not selectable:
            return None
            
        # Sort priority (descending, i.e. higher priority first), then submitted_at (ascending, FIFO)
        selectable.sort(key=lambda x: (-x[1], x[2]))
        best_idx, _, _, best_exec = selectable[0]
        
        # Remove chosen job from the persistent queue
        queue_data.pop(best_idx)
        self._save(queue_data)
        
        return best_exec

    def cancel(self, execution_id: str) -> bool:
        """Cancel and remove a queued job by ID."""
        queue_data = self._load()
        original_len = len(queue_data)
        queue_data = [item for item in queue_data if item.get("id") != execution_id]
        if len(queue_data) < original_len:
            self._save(queue_data)
            return True
        return False

    def list_queued(self) -> List[Execution]:
        """Return a copy list of all queued jobs."""
        return [Execution(**item) for item in self._load()]

    def _load(self) -> list:
        data = self.storage.read(self.filepath)
        return data if isinstance(data, list) else []

    def _save(self, data: list) -> None:
        self.storage.write(self.filepath, data)
