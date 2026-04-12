"""Tests for core/infra/config.py — JSON configuration management.

Verifies loading, defaults, saving with secure permissions, and
config field access.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest


class TestConfigDefaults:
    """Config must provide sensible defaults when no file exists."""

    def test_load_returns_config_object(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg is not None

    def test_default_model(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.default_model == "gemini-2.5-flash"

    def test_default_prefer_preview_false(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.prefer_preview_models is False

    def test_default_cost_limit(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.cost_limit_daily_usd == 5.00

    def test_default_dry_run_true(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.dry_run_default is True

    def test_default_deep_research_timeout(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.deep_research_timeout_seconds == 3600

    def test_default_output_dir_is_none(self, tmp_path):
        from core.infra.config import load_config
        cfg = load_config(config_dir=tmp_path)
        assert cfg.output_dir is None


class TestConfigLoading:
    """Config must load from an existing JSON file and merge with defaults."""

    def test_loads_custom_model(self, tmp_path):
        from core.infra.config import load_config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"default_model": "gemini-2.5-pro"}))
        cfg = load_config(config_dir=tmp_path)
        assert cfg.default_model == "gemini-2.5-pro"

    def test_unknown_fields_ignored(self, tmp_path):
        from core.infra.config import load_config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"unknown_field": "value", "default_model": "gemini-2.5-flash"}))
        cfg = load_config(config_dir=tmp_path)
        assert cfg.default_model == "gemini-2.5-flash"

    def test_partial_config_merges_with_defaults(self, tmp_path):
        from core.infra.config import load_config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cost_limit_daily_usd": 10.0}))
        cfg = load_config(config_dir=tmp_path)
        assert cfg.cost_limit_daily_usd == 10.0
        assert cfg.default_model == "gemini-2.5-flash"  # default preserved

    def test_invalid_json_returns_defaults(self, tmp_path):
        from core.infra.config import load_config
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{")
        cfg = load_config(config_dir=tmp_path)
        assert cfg.default_model == "gemini-2.5-flash"


class TestConfigSaving:
    """save_config() must write JSON with secure permissions."""

    def test_save_creates_file(self, tmp_path):
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)
        save_config(cfg, config_dir=tmp_path)
        assert (tmp_path / "config.json").exists()

    def test_save_round_trips(self, tmp_path):
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)
        cfg.cost_limit_daily_usd = 20.0
        save_config(cfg, config_dir=tmp_path)

        cfg2 = load_config(config_dir=tmp_path)
        assert cfg2.cost_limit_daily_usd == 20.0

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions not available on Windows")
    def test_save_sets_secure_permissions(self, tmp_path):
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)
        save_config(cfg, config_dir=tmp_path)

        config_file = tmp_path / "config.json"
        file_mode = stat.S_IMODE(config_file.stat().st_mode)
        assert file_mode == 0o600

    def test_deep_research_timeout_capped_at_3600(self, tmp_path):
        from core.infra.config import load_config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"deep_research_timeout_seconds": 9999}))
        cfg = load_config(config_dir=tmp_path)
        assert cfg.deep_research_timeout_seconds == 3600
