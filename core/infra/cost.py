"""Two-phase cost tracking with file-locked daily accumulation.

Phase 1 (pre-flight): estimate_cost() computes expected cost from
    registry pricing before making the API call.
Phase 2 (post-response): CostTracker.record_actual_cost() tracks
    actual cost from usageMetadata returned by the API.

Cost numbers are estimates based on local pricing tables and provider
metadata. Not guaranteed to be exact.

Daily totals are stored in cost_today.json with UTC date keys.
File locking prevents data loss from concurrent tool calls.
The entire read-modify-write cycle runs under a single lock
to prevent TOCTOU races.

Dependencies: core/infra/filelock.py, core/infra/atomic_write.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from core.infra.atomic_write import atomic_write_json
from core.infra.filelock import FileLock
from core.transport.base import UsageMetadata

_COST_FILENAME = "cost_today.json"
_LOCK_FILENAME = "cost.lock"


def estimate_cost(
    pricing: dict[str, float],
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Compute a pre-flight cost estimate from registry pricing.

    Args:
        pricing: Dict with keys input_per_1m, output_per_1m, cached_per_1m.
        input_tokens: Total input tokens (including cached).
        output_tokens: Expected output tokens.
        cached_tokens: Number of tokens served from cache.

    Returns:
        Estimated cost in USD.
    """
    regular_input = max(0, input_tokens - cached_tokens)
    input_cost = regular_input * pricing["input_per_1m"] / 1_000_000
    cached_cost = cached_tokens * pricing["cached_per_1m"] / 1_000_000
    output_cost = output_tokens * pricing["output_per_1m"] / 1_000_000
    return input_cost + cached_cost + output_cost


class CostTracker:
    """Tracks daily API cost with file-locked atomic writes.

    Stores the daily total in a JSON file with a UTC date key.
    Automatically resets when the date changes. The full
    read-modify-write cycle is protected by a file lock.

    Args:
        state_dir: Directory for cost state and lock files.
    """

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._cost_file = self._state_dir / _COST_FILENAME
        self._lock_path = self._state_dir / _LOCK_FILENAME

    def _today_key(self) -> str:
        """Get today's UTC date as a string key."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _read_daily_unlocked(self) -> float:
        """Read today's cost total from disk without locking.

        Must only be called from within a lock context or when
        an approximate read is acceptable.
        """
        if not self._cost_file.is_file():
            return 0.0
        try:
            data = json.loads(self._cost_file.read_text(encoding="utf-8"))
            if data.get("date") != self._today_key():
                return 0.0
            return float(data.get("total", 0.0))
        except (json.JSONDecodeError, OSError, ValueError):
            return 0.0

    def _add_to_daily(self, delta: float) -> None:
        """Atomically add to today's cost total under a single lock.

        The entire read-modify-write runs under one lock acquisition
        to prevent TOCTOU races from concurrent tool calls.
        """
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with FileLock(self._lock_path):
            current = self._read_daily_unlocked()
            total = current + delta
            data = json.dumps({
                "date": self._today_key(),
                "total": total,
                "updated_at": time.time(),
            })
            atomic_write_json(self._cost_file, data)

    def _write_daily(self, total: float) -> None:
        """Write a specific daily total (used for testing/direct set)."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with FileLock(self._lock_path):
            data = json.dumps({
                "date": self._today_key(),
                "total": total,
                "updated_at": time.time(),
            })
            atomic_write_json(self._cost_file, data)

    def get_daily_total(self) -> float:
        """Get today's accumulated cost in USD."""
        return self._read_daily_unlocked()

    def record_actual_cost(
        self,
        pricing: dict[str, float],
        usage_metadata: UsageMetadata,
    ) -> float:
        """Record actual cost from API response usageMetadata.

        Extracts token counts from usageMetadata, computes cost,
        and atomically adds to the daily total under a file lock.

        Args:
            pricing: Dict with keys input_per_1m, output_per_1m, cached_per_1m.
            usage_metadata: The usageMetadata dict from the API response.

        Returns:
            The cost of this individual request in USD.
        """
        input_tokens = usage_metadata.get("promptTokenCount", 0)
        output_tokens = usage_metadata.get("candidatesTokenCount", 0)
        cached_tokens = usage_metadata.get("cachedContentTokenCount", 0)

        cost = estimate_cost(
            pricing=pricing,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )

        self._add_to_daily(cost)
        return cost

    def check_daily_limit(self, limit_usd: float) -> bool:
        """Check if the daily cost is within the configured limit.

        Args:
            limit_usd: The daily cost limit in USD.

        Returns:
            True if current total is at or below the limit.
        """
        return self._read_daily_unlocked() <= limit_usd
