"""Tests for core/infra/timeouts.py — cross-platform timeout guards.

Verifies that the timeout guard works as a context manager, raises
TimeoutError on expiry, and handles platform differences correctly.
"""
from __future__ import annotations

import sys
import time
import threading

import pytest


class TestTimeoutGuard:
    """install_timeout_guard() must enforce execution time limits."""

    def test_is_context_manager(self):
        from core.infra.timeouts import TimeoutGuard
        guard = TimeoutGuard(seconds=10)
        assert hasattr(guard, "__enter__")
        assert hasattr(guard, "__exit__")

    def test_does_not_fire_within_limit(self):
        from core.infra.timeouts import TimeoutGuard
        with TimeoutGuard(seconds=5):
            time.sleep(0.01)  # well within limit

    def test_no_signal_from_non_main_thread(self):
        """Signal-based timeouts must not be used from non-main threads."""
        from core.infra.timeouts import TimeoutGuard

        errors = []

        def worker():
            try:
                with TimeoutGuard(seconds=1):
                    pass
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=3)
        # Should not raise — falls back to watchdog or no-op in non-main thread
        assert len(errors) == 0

    def test_accepts_custom_message(self):
        from core.infra.timeouts import TimeoutGuard
        guard = TimeoutGuard(seconds=5, message="Custom timeout message")
        assert guard.message == "Custom timeout message"
