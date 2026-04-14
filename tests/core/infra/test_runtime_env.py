"""Tests for core/infra/runtime_env.py — launcher env normalization."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _write_settings(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestResolveRuntimeEnv:
    @pytest.mark.usefixtures("monkeypatch")
    def test_process_env_is_used_when_no_files_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()

        monkeypatch.setenv("GEMINI_API_KEY", "process-key")

        resolved_values: dict[str, str] = resolve_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert resolved_values["GEMINI_API_KEY"] == "process-key"

    @pytest.mark.usefixtures("monkeypatch")
    def test_env_file_overrides_process_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()
        (working_directory / ".env").write_text(
            "GEMINI_API_KEY=file-key\nOTHER_KEY=ignored\nGEMINI_LIVE_TESTS=1\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("GEMINI_API_KEY", "process-key")
        monkeypatch.setenv("GEMINI_IS_SDK_PRIORITY", "false")

        resolved_values: dict[str, str] = resolve_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert resolved_values["GEMINI_API_KEY"] == "file-key"
        assert resolved_values["GEMINI_LIVE_TESTS"] == "1"
        assert "OTHER_KEY" not in resolved_values
        assert resolved_values["GEMINI_IS_SDK_PRIORITY"] == "false"

    @pytest.mark.usefixtures("monkeypatch")
    def test_file_precedence_is_applied_per_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()

        _write_settings(
            home_directory / ".claude" / "settings.json",
            {
                "env": {
                    "GEMINI_API_KEY": "global-key",
                    "GEMINI_IS_SDK_PRIORITY": "true",
                    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
                }
            },
        )
        _write_settings(
            working_directory / ".claude" / "settings.json",
            {"env": {"GEMINI_IS_SDK_PRIORITY": "false", "GEMINI_LIVE_TESTS": "1"}},
        )
        _write_settings(
            working_directory / ".claude" / "settings.local.json",
            {"env": {"GEMINI_API_KEY": "local-settings-key"}},
        )
        (working_directory / ".env").write_text("GEMINI_API_KEY=dotenv-key\n", encoding="utf-8")

        monkeypatch.setenv("GEMINI_IS_RAWHTTP_PRIORITY", "process-raw-http")

        resolved_values: dict[str, str] = resolve_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert resolved_values["GEMINI_API_KEY"] == "dotenv-key"
        assert resolved_values["GEMINI_IS_SDK_PRIORITY"] == "false"
        assert resolved_values["GEMINI_LIVE_TESTS"] == "1"
        assert resolved_values["GEMINI_IS_RAWHTTP_PRIORITY"] == "false"

    def test_invalid_settings_json_raises_clear_error(self, tmp_path: Path) -> None:
        from core.infra.errors import EnvironmentResolutionError
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()
        invalid_settings_path: Path = working_directory / ".claude" / "settings.local.json"
        invalid_settings_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_settings_path.write_text("{not-json", encoding="utf-8")

        with pytest.raises(EnvironmentResolutionError, match="settings.local.json"):
            resolve_runtime_env(cwd=working_directory, home_dir=home_directory)

    def test_non_dict_settings_root_is_ignored(self, tmp_path: Path) -> None:
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()

        project_settings_path: Path = working_directory / ".claude" / "settings.json"
        project_settings_path.parent.mkdir(parents=True, exist_ok=True)
        project_settings_path.write_text('["unexpected"]', encoding="utf-8")

        resolved_values: dict[str, str] = resolve_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert resolved_values == {}

    def test_non_dict_env_block_is_ignored(self, tmp_path: Path) -> None:
        from core.infra.runtime_env import resolve_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()

        _write_settings(working_directory / ".claude" / "settings.json", {"env": ["unexpected"]})

        resolved_values: dict[str, str] = resolve_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert resolved_values == {}


class TestRuntimeEnvFileReads:
    def test_read_env_file_missing_returns_empty(self, tmp_path: Path) -> None:
        from core.infra.runtime_env import _read_env_file

        env_path: Path = tmp_path / ".env"
        assert _read_env_file(env_path) == {}

    def test_read_env_file_os_error_is_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.infra.errors import EnvironmentResolutionError
        from core.infra.runtime_env import _read_env_file

        env_path: Path = Path("/tmp/runtime-env-test.env")

        monkeypatch.setattr(Path, "is_file", lambda self: True)

        def failing_read_text(self: Path, encoding: str = "utf-8") -> str:
            raise OSError("env read failed")

        monkeypatch.setattr(Path, "read_text", failing_read_text)

        with pytest.raises(EnvironmentResolutionError, match="env read failed"):
            _read_env_file(env_path)

    def test_read_settings_env_missing_returns_empty(self, tmp_path: Path) -> None:
        from core.infra.runtime_env import _read_settings_env

        settings_path: Path = tmp_path / "settings.json"
        assert _read_settings_env(settings_path) == {}

    def test_read_settings_env_os_error_is_wrapped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.infra.errors import EnvironmentResolutionError
        from core.infra.runtime_env import _read_settings_env

        settings_path: Path = Path("/tmp/runtime-settings-test.json")

        monkeypatch.setattr(Path, "is_file", lambda self: True)

        def failing_read_text(self: Path, encoding: str = "utf-8") -> str:
            raise OSError("settings read failed")

        monkeypatch.setattr(Path, "read_text", failing_read_text)

        with pytest.raises(EnvironmentResolutionError, match="settings read failed"):
            _read_settings_env(settings_path)


class TestBootstrapRuntimeEnv:
    @pytest.mark.usefixtures("monkeypatch")
    def test_bootstrap_runtime_env_updates_os_environ(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.infra.runtime_env import bootstrap_runtime_env

        working_directory: Path = tmp_path / "project"
        home_directory: Path = tmp_path / "home"
        working_directory.mkdir()
        home_directory.mkdir()
        (working_directory / ".env").write_text("GEMINI_API_KEY=bootstrapped-key\n", encoding="utf-8")

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        resolved_values: dict[str, str] = bootstrap_runtime_env(
            cwd=working_directory, home_dir=home_directory
        )

        assert os.environ["GEMINI_API_KEY"] == "bootstrapped-key"
        assert resolved_values["GEMINI_API_KEY"] == "bootstrapped-key"


class TestEnvExampleParity:
    def test_env_example_matches_canonical_defaults(self) -> None:
        from core.infra.runtime_env import CANONICAL_ENV_KEYS, CANONICAL_ENV_DEFAULTS

        repository_root: Path = Path(__file__).resolve().parents[3]
        env_example_path: Path = repository_root / ".env.example"
        raw_lines: list[str] = env_example_path.read_text(encoding="utf-8").splitlines()
        assignment_lines: list[str] = [
            raw_line.strip()
            for raw_line in raw_lines
            if raw_line.strip() and not raw_line.lstrip().startswith("#")
        ]

        expected_lines: list[str] = [
            f"{env_key}={CANONICAL_ENV_DEFAULTS[env_key]}" for env_key in CANONICAL_ENV_KEYS
        ]

        assert assignment_lines == expected_lines
