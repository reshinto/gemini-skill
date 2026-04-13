"""Cross-platform file locking for concurrent access protection.

Provides a context-manager-based file lock that prevents data loss when
multiple Claude Code tool calls run in parallel. Uses fcntl.flock on POSIX
and msvcrt.locking on Windows.

Non-blocking with configurable timeout — avoids infinite hangs if a process
crashes while holding the lock. The lock is always released on context exit,
even if an exception occurs inside the with block.

Dependency: core/infra/errors.py (for LockTimeout, though we define it here
to keep the filelock self-contained).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


class LockTimeout(Exception):
    """Raised when the file lock cannot be acquired within the timeout period."""


class FileLock:
    """Cross-platform file lock using a context manager.

    Usage:
        with FileLock(Path("data.lock")):
            # read-modify-write data safely
            ...

    Args:
        path: Path to the lock file. Created if it does not exist.
        timeout: Maximum seconds to wait for the lock. 0 = fail immediately.
            None or negative = wait indefinitely (not recommended).
    """

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> FileLock:
        self._acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._release()

    def _acquire(self) -> None:
        """Acquire the lock with non-blocking retries until timeout."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o600)

        deadline = time.monotonic() + self.timeout if self.timeout >= 0 else float("inf")
        sleep_interval = 0.05

        while True:
            try:
                self._try_lock()
                return
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise LockTimeout(
                        f"Could not acquire lock on {self.path} within {self.timeout}s"
                    )
                time.sleep(min(sleep_interval, max(0, deadline - time.monotonic())))
                sleep_interval = min(sleep_interval * 2, 0.5)

    def _try_lock(self) -> None:
        """Attempt a non-blocking lock. Raises OSError if unavailable."""
        fd = self._fd
        if fd is None:
            raise RuntimeError("File descriptor not initialized before locking")
        if sys.platform == "win32":  # pragma: no cover
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(self) -> None:
        """Release the lock and close the file descriptor."""
        if self._fd is not None:
            try:
                if sys.platform == "win32":  # pragma: no cover
                    import msvcrt
                    try:
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
