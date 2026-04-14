"""Tests for the clone-free bootstrap installer CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


class TestMaterializePayload:
    def test_copies_install_payload_from_source_checkout(self, tmp_path: Path) -> None:
        from gemini_skill_install.cli import materialize_payload

        payload_root = materialize_payload(tmp_path / "payload")

        assert (payload_root / "SKILL.md").exists()
        assert (payload_root / "VERSION").exists()
        assert (payload_root / "core" / "__init__.py").exists()
        assert (payload_root / "adapters" / "__init__.py").exists()
        assert (payload_root / "reference" / "index.md").exists()
        assert (payload_root / "registry" / "models.json").exists()
        assert (payload_root / "scripts" / "gemini_run.py").exists()
        assert (payload_root / "setup" / "update.py").exists()
        assert (payload_root / "setup" / "requirements.txt").exists()


class TestBootstrapInstallerCli:
    def test_main_installs_using_materialized_payload(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from gemini_skill_install.cli import main

        home_dir = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home_dir))
        (home_dir / ".claude").mkdir(parents=True)
        install_dir = tmp_path / "install"

        with (
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch(
                "core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"
            ),
            patch("core.cli.install_main._is_interactive_stdin", return_value=False),
        ):
            main(["--yes"], install_dir=install_dir)

        assert (install_dir / "SKILL.md").exists()
        assert (install_dir / "setup" / "update.py").exists()
        assert (install_dir / "setup" / "requirements.txt").exists()

        settings_path = home_dir / ".claude" / "settings.json"
        settings_data = json.loads(settings_path.read_text())
        assert settings_data["env"]["GEMINI_IS_SDK_PRIORITY"] == "true"
        assert settings_data["env"]["GEMINI_IS_RAWHTTP_PRIORITY"] == "false"
