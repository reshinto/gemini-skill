"""Two-phase cost tracking with file-locked daily accumulation.

Phase 1 (pre-flight): estimate_cost() computes expected cost from
    registry pricing before making the API call.
Phase 2 (post-response): CostTracker.record_actual_cost() tracks
    actual cost from usageMetadata returned by the API.

Cost numbers are estimates based on local pricing tables and provider
metadata. Not guaranteed to be exact.

Daily totals are stored in cost_today.json with UTC date keys.
File locking prevents data loss from concurrent tool calls.

Dependencies: core/infra/filelock.py
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.infra.filelock import FileLock

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
    Automatically resets when the date changes.

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

    def _read_daily(self) -> float:
        """Read today's cost total from disk. Returns 0.0 on any error."""
        if not self._cost_file.is_file():
            return 0.0
        try:
            data = json.loads(self._cost_file.read_text(encoding="utf-8"))
            if data.get("date") != self._today_key():
                return 0.0
            return float(data.get("total", 0.0))
        except (json.JSONDecodeError, OSError, ValueError):
            return 0.0

    def _write_daily(self, total: float) -> None:
        """Atomically write today's cost total to disk."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with FileLock(self._lock_path):
            data = json.dumps({
                "date": self._today_key(),
                "total": total,
                "updated_at": time.time(),
            })
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._state_dir), prefix=".cost-", suffix=".tmp"
            )
            try:
                os.write(fd, data.encode("utf-8"))
                os.close(fd)
                fd = -1
                os.replace(tmp_path, str(self._cost_file))
            except Exception:
                if fd >= 0:
                    os.close(fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def get_daily_total(self) -> float:
        """Get today's accumulated cost in USD."""
        return self._read_daily()

    def record_actual_cost(
        self,
        pricing: dict[str, float],
        usage_metadata: dict[str, Any],
    ) -> float:
        """Record actual cost from API response usageMetadata.

        Extracts token counts from usageMetadata, computes cost,
        and adds to the daily total.

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

        current = self._read_daily()
        self._write_daily(current + cost)

        return cost

    def check_daily_limit(self, limit_usd: float) -> bool:
        """Check if the daily cost is within the configured limit.

        Args:
            limit_usd: The daily cost limit in USD.

        Returns:
            True if current total is at or below the limit.
        """
        return self._read_daily() <= limit_usd
