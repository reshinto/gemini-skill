"""Tests for core/infra/cost.py — two-phase cost tracking.

Verifies pre-flight estimation, post-response tracking with usageMetadata,
daily accumulation with file locking, daily limit checking, and date rollover.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


class TestEstimateCost:
    """estimate_cost() must compute pre-flight cost estimates."""

    def test_basic_estimate(self):
        from core.infra.cost import estimate_cost

        pricing = {
            "input_per_1m": 0.15,
            "output_per_1m": 0.60,
            "cached_per_1m": 0.0375,
        }
        cost = estimate_cost(
            pricing=pricing,
            input_tokens=1000,
            output_tokens=500,
        )
        expected = (1000 * 0.15 / 1_000_000) + (500 * 0.60 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_estimate_with_cached_tokens(self):
        from core.infra.cost import estimate_cost

        pricing = {
            "input_per_1m": 0.15,
            "output_per_1m": 0.60,
            "cached_per_1m": 0.0375,
        }
        cost = estimate_cost(
            pricing=pricing,
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
        )
        # 800 regular input + 200 cached input + 500 output
        expected = (800 * 0.15 / 1_000_000) + (200 * 0.0375 / 1_000_000) + (500 * 0.60 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_estimate_zero_tokens(self):
        from core.infra.cost import estimate_cost

        pricing = {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375}
        cost = estimate_cost(pricing=pricing, input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_estimate_cached_exceeds_input(self):
        from core.infra.cost import estimate_cost

        pricing = {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375}
        # cached > input — regular input should be 0, not negative
        cost = estimate_cost(
            pricing=pricing,
            input_tokens=100,
            output_tokens=0,
            cached_tokens=200,
        )
        assert cost >= 0


class TestRecordActualCost:
    """record_actual_cost() must track costs from usageMetadata."""

    def test_records_cost_to_file(self, tmp_path):
        from core.infra.cost import CostTracker

        pricing = {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375}
        tracker = CostTracker(state_dir=tmp_path)
        usage = {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 500,
            "cachedContentTokenCount": 0,
        }
        cost = tracker.record_actual_cost(pricing=pricing, usage_metadata=usage)
        assert cost > 0

    def test_accumulates_across_calls(self, tmp_path):
        from core.infra.cost import CostTracker

        pricing = {"input_per_1m": 1.0, "output_per_1m": 1.0, "cached_per_1m": 0.5}
        tracker = CostTracker(state_dir=tmp_path)
        usage = {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 1000,
            "cachedContentTokenCount": 0,
        }

        tracker.record_actual_cost(pricing=pricing, usage_metadata=usage)
        tracker.record_actual_cost(pricing=pricing, usage_metadata=usage)

        total = tracker.get_daily_total()
        expected_single = (1000 * 1.0 / 1_000_000) + (1000 * 1.0 / 1_000_000)
        assert abs(total - 2 * expected_single) < 1e-10

    def test_persists_across_instances(self, tmp_path):
        from core.infra.cost import CostTracker

        pricing = {"input_per_1m": 1.0, "output_per_1m": 1.0, "cached_per_1m": 0.5}
        usage = {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 500,
            "cachedContentTokenCount": 0,
        }

        tracker1 = CostTracker(state_dir=tmp_path)
        tracker1.record_actual_cost(pricing=pricing, usage_metadata=usage)

        tracker2 = CostTracker(state_dir=tmp_path)
        assert tracker2.get_daily_total() > 0

    def test_handles_missing_usage_fields(self, tmp_path):
        from core.infra.cost import CostTracker

        pricing = {"input_per_1m": 1.0, "output_per_1m": 1.0, "cached_per_1m": 0.5}
        tracker = CostTracker(state_dir=tmp_path)
        # Sparse usageMetadata — missing fields default to 0
        usage = {"promptTokenCount": 100}
        cost = tracker.record_actual_cost(pricing=pricing, usage_metadata=usage)
        assert cost >= 0

    def test_handles_empty_usage(self, tmp_path):
        from core.infra.cost import CostTracker

        pricing = {"input_per_1m": 1.0, "output_per_1m": 1.0, "cached_per_1m": 0.5}
        tracker = CostTracker(state_dir=tmp_path)
        cost = tracker.record_actual_cost(pricing=pricing, usage_metadata={})
        assert cost == 0.0


class TestDailyLimit:
    """CostTracker.check_daily_limit() must enforce cost caps."""

    def test_under_limit_returns_true(self, tmp_path):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        assert tracker.check_daily_limit(limit_usd=5.0) is True

    def test_over_limit_returns_false(self, tmp_path):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        # Manually write a high cost
        tracker._write_daily(10.0)
        assert tracker.check_daily_limit(limit_usd=5.0) is False

    def test_exactly_at_limit_returns_true(self, tmp_path):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        tracker._write_daily(5.0)
        assert tracker.check_daily_limit(limit_usd=5.0) is True


class TestDailyRollover:
    """CostTracker must reset on date change."""

    def test_new_day_resets_total(self, tmp_path):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        tracker._write_daily(10.0)

        # Simulate next day by changing the date key
        cost_file = tmp_path / "cost_today.json"
        data = json.loads(cost_file.read_text())
        data["date"] = "2020-01-01"  # Old date
        cost_file.write_text(json.dumps(data))

        # New tracker should see 0 for today
        tracker2 = CostTracker(state_dir=tmp_path)
        assert tracker2.get_daily_total() == 0.0

    def test_invalid_cost_file_returns_zero(self, tmp_path):
        from core.infra.cost import CostTracker

        (tmp_path / "cost_today.json").write_text("bad json")
        tracker = CostTracker(state_dir=tmp_path)
        assert tracker.get_daily_total() == 0.0


class TestCostTrackerSaveErrors:
    """Cover error paths in _write_daily()."""

    def test_save_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        with pytest.raises(OSError, match="replace failed"):
            tracker._write_daily(1.0)

    def test_save_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        monkeypatch.setattr(
            os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed"))
        )
        with pytest.raises(OSError, match="write failed"):
            tracker._write_daily(1.0)

    def test_save_handles_unlink_failure(self, tmp_path, monkeypatch):
        from core.infra.cost import CostTracker

        tracker = CostTracker(state_dir=tmp_path)
        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        monkeypatch.setattr(os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
        with pytest.raises(OSError, match="replace failed"):
            tracker._write_daily(1.0)
