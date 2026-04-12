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


class TestConfigDefaultDir:
    """Cover the default config_dir=None path (uses ~/.config/gemini-skill/)."""

    def test_load_with_none_dir_uses_home(self, monkeypatch, tmp_path):
        from core.infra.config import load_config
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg = load_config(config_dir=None)
        assert cfg.default_model == "gemini-2.5-flash"

    def test_save_with_none_dir_uses_home(self, monkeypatch, tmp_path):
        from core.infra.config import load_config, save_config
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg = load_config(config_dir=tmp_path)
        cfg.cost_limit_daily_usd = 99.0
        save_config(cfg, config_dir=None)
        config_file = tmp_path / ".config" / "gemini-skill" / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["cost_limit_daily_usd"] == 99.0


class TestConfigSaveErrorHandling:
    """Cover the error cleanup paths in save_config."""

    def test_save_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)

        original_replace = os.replace
        def failing_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(OSError, match="disk full"):
            save_config(cfg, config_dir=tmp_path)

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
    def test_save_dir_gets_0700_permissions(self, tmp_path):
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)
        save_config(cfg, config_dir=tmp_path)
        dir_mode = stat.S_IMODE(tmp_path.stat().st_mode)
        assert dir_mode == 0o700

    def test_save_handles_chmod_dir_failure(self, tmp_path, monkeypatch):
        """Cover the OSError catch on directory chmod."""
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)

        original_chmod = os.chmod
        call_count = [0]
        def failing_chmod(path, mode):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("permission denied on dir")
            return original_chmod(path, mode)

        monkeypatch.setattr(os, "chmod", failing_chmod)
        # Should not raise — chmod failure on dir is best-effort
        save_config(cfg, config_dir=tmp_path)
        assert (tmp_path / "config.json").exists()

    def test_save_handles_chmod_file_failure(self, tmp_path, monkeypatch):
        """Cover the OSError catch on file chmod."""
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)

        original_chmod = os.chmod
        call_count = [0]
        def failing_chmod(path, mode):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("permission denied on file")
            return original_chmod(path, mode)

        monkeypatch.setattr(os, "chmod", failing_chmod)
        save_config(cfg, config_dir=tmp_path)
        assert (tmp_path / "config.json").exists()

    def test_save_cleans_up_temp_file_on_failure(self, tmp_path, monkeypatch):
        """Cover the cleanup branch: fd already closed, unlink temp file."""
        from core.infra.config import load_config, save_config
        import tempfile as tmp_mod

        cfg = load_config(config_dir=tmp_path)

        original_mkstemp = tmp_mod.mkstemp
        created_temps = []

        def tracking_mkstemp(**kwargs):
            fd, path = original_mkstemp(**kwargs)
            created_temps.append(path)
            return fd, path

        monkeypatch.setattr(tmp_mod, "mkstemp", tracking_mkstemp)

        # Make os.replace fail so we hit the cleanup branch
        monkeypatch.setattr(os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed")))

        with pytest.raises(OSError, match="replace failed"):
            save_config(cfg, config_dir=tmp_path)

        # Temp file should have been cleaned up
        for tp in created_temps:
            assert not os.path.exists(tp), f"Temp file was not cleaned up: {tp}"

    def test_save_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        """Cover the branch where fd is still open when exception fires."""
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)

        # Make os.write fail so fd is still >= 0 in the except block
        monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed")))

        with pytest.raises(OSError, match="write failed"):
            save_config(cfg, config_dir=tmp_path)

    def test_save_handles_unlink_failure(self, tmp_path, monkeypatch):
        """Cover the OSError catch on temp file unlink."""
        from core.infra.config import load_config, save_config
        cfg = load_config(config_dir=tmp_path)

        original_replace = os.replace
        original_unlink = os.unlink

        def failing_replace(src, dst):
            raise OSError("replace failed")

        def failing_unlink(path):
            raise OSError("unlink failed")

        monkeypatch.setattr(os, "replace", failing_replace)
        monkeypatch.setattr(os, "unlink", failing_unlink)

        with pytest.raises(OSError, match="replace failed"):
            save_config(cfg, config_dir=tmp_path)
