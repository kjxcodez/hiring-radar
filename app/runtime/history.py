from pathlib import Path
from typing import Optional
from app.runtime.execution import Execution
from app.storage.json_storage import JsonStorage


class ExecutionHistory:
    """Handles persistent serialization and logging of job execution history."""

    def __init__(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def record(self, execution: Execution) -> None:
        """Add or update an execution entry in history."""
        executions = self.load_all()
        executions[execution.id] = execution
        self.save_all(executions)

    def find_by_id(self, execution_id: str) -> Optional[Execution]:
        """Find an execution by its UUID."""
        return self.load_all().get(execution_id)

    def load_all(self) -> dict[str, Execution]:
        """Load and deserialize all historical executions from JSON file."""
        try:
            data = self.storage.read(self.filepath)
            if not isinstance(data, dict):
                return {}
            return {k: Execution(**v) for k, v in data.items()}
        except Exception:
            return {}

    def save_all(self, executions: dict[str, Execution]) -> None:
        """Serialize and atomically save executions list to JSON file."""
        data = {k: v.model_dump(mode="json") for k, v in executions.items()}
        self.storage.write(self.filepath, data)
