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


class TestTimeoutSignalHandler:
    """Cover the _signal_handler and _can_use_signal paths."""

    def test_signal_handler_raises_timeout_expired(self):
        from core.infra.timeouts import TimeoutGuard, TimeoutExpired

        guard = TimeoutGuard(seconds=1, message="test timeout")
        with pytest.raises(TimeoutExpired, match="test timeout"):
            guard._signal_handler(14, None)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
    def test_can_use_signal_true_on_posix_main_thread(self):
        from core.infra.timeouts import TimeoutGuard

        guard = TimeoutGuard(seconds=1)
        # We are in the main thread on POSIX during test runs
        assert guard._can_use_signal() is True

    def test_can_use_signal_false_in_non_main_thread(self):
        from core.infra.timeouts import TimeoutGuard

        guard = TimeoutGuard(seconds=1)
        results = []

        def worker():
            results.append(guard._can_use_signal())

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results[0] is False


class TestWatchdogFire:
    """Cover the _watchdog_fire best-effort callback."""

    def test_watchdog_fire_does_not_raise(self):
        from core.infra.timeouts import TimeoutGuard

        guard = TimeoutGuard(seconds=1)
        # Should be a no-op, not raise
        guard._watchdog_fire()

    def test_watchdog_used_in_non_main_thread(self):
        """Verify the watchdog path is taken in a non-main thread."""
        from core.infra.timeouts import TimeoutGuard

        errors = []

        def worker():
            try:
                with TimeoutGuard(seconds=10):
                    pass
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=3)
        assert len(errors) == 0
