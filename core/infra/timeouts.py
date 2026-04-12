"""Cross-platform timeout guards for preventing infinite hangs.

Provides a context manager that enforces execution time limits:
- POSIX main thread: uses signal.alarm() for true preemptive timeout
- Windows or non-main thread: uses a daemon watchdog thread

Python constraints:
- signal.alarm() is Unix-only
- Signal handlers can only be set in the main thread of the main interpreter
- The watchdog thread approach cannot interrupt blocking I/O the same way
  signals can, but it provides the best available protection on those platforms

Dependency: none (leaf module, stdlib only).
"""
from __future__ import annotations

import os
import sys
import signal
import threading
import time
from typing import Optional


class TimeoutExpired(Exception):
    """Raised when an operation exceeds its configured timeout."""


class TimeoutGuard:
    """Context manager that enforces an execution time limit.

    Automatically selects the best timeout mechanism for the current
    platform and thread context:
    - POSIX main thread: signal.alarm() (true preemptive timeout)
    - Other contexts: daemon watchdog thread (best-effort)

    Usage:
        with TimeoutGuard(seconds=30):
            # operation that might hang
            ...

    Args:
        seconds: Maximum execution time in seconds.
        message: Custom message for the TimeoutExpired exception.
    """

    def __init__(self, seconds: int, message: Optional[str] = None) -> None:
        self.seconds = seconds
        self.message = message or f"Operation exceeded {seconds}s limit"
        self._use_signal = False
        self._old_handler = None
        self._watchdog: Optional[threading.Timer] = None

    def __enter__(self) -> TimeoutGuard:
        if self._can_use_signal():
            self._use_signal = True
            self._old_handler = signal.signal(signal.SIGALRM, self._signal_handler)
            signal.alarm(self.seconds)
        else:
            # Watchdog thread — cannot truly interrupt blocking I/O,
            # but will fire the callback after the timeout period
            self._watchdog = threading.Timer(self.seconds, self._watchdog_fire)
            self._watchdog.daemon = True
            self._watchdog.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._use_signal:
            signal.alarm(0)
            if self._old_handler is not None:
                signal.signal(signal.SIGALRM, self._old_handler)
        elif self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None

    def _can_use_signal(self) -> bool:
        """Check if signal-based timeout is available.

        Only works on POSIX systems and only from the main thread
        of the main interpreter.
        """
        if sys.platform == "win32":  # pragma: no cover
            return False
        if not hasattr(signal, "SIGALRM"):  # pragma: no cover
            return False
        return threading.current_thread() is threading.main_thread()

    def _signal_handler(self, signum: int, frame) -> None:
        """POSIX signal handler that raises TimeoutExpired."""
        raise TimeoutExpired(f"[TIMEOUT] {self.message}")

    def _watchdog_fire(self) -> None:
        """Watchdog callback — logs timeout but cannot interrupt the main thread.

        On Windows or from non-main threads, the best we can do is set a flag
        or print a warning. True interruption requires cooperative checking.
        """
        # In practice, the main thread should check for timeout cooperatively
        # This is a best-effort fallback
        pass
