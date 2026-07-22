import time
from pathlib import Path


class LockManager:
    """Manages file-based exclusive execution locks to prevent concurrent conflicts."""

    def __init__(self, lock_dir: Path) -> None:
        self.lock_dir = lock_dir
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def acquire(self, lock_name: str, timeout: float = 0.0) -> bool:
        """Acquire an exclusive lock by creating a lock file.

        Args:
            lock_name: Unique lock identifier.
            timeout: Maximum seconds to block waiting for the lock.

        Returns:
            True if the lock was acquired successfully, else False.
        """
        lock_file = self.lock_dir / f"{lock_name}.lock"
        start_time = time.time()
        while True:
            try:
                # 'x' mode guarantees atomic exclusive creation
                with lock_file.open("x"):
                    pass
                return True
            except FileExistsError:
                if timeout <= 0 or (time.time() - start_time) > timeout:
                    return False
                time.sleep(0.1)

    def release(self, lock_name: str) -> None:
        """Release the lock by removing the lock file."""
        lock_file = self.lock_dir / f"{lock_name}.lock"
        try:
            lock_file.unlink(missing_ok=True)
        except Exception:
            pass

    def is_locked(self, lock_name: str) -> bool:
        """Check if the lock is currently active."""
        return (self.lock_dir / f"{lock_name}.lock").exists()
