"""Tests for adapters/experimental/deep_research.py — Interactions API."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestDeepResearchGetParser:
    def test_has_prompt(self):
        from adapters.experimental.deep_research import get_parser

        args = get_parser().parse_args(["research quantum computing"])
        assert args.prompt == "research quantum computing"

    def test_accepts_execute_flag(self):
        from adapters.experimental.deep_research import get_parser

        args = get_parser().parse_args(["research quantum computing", "--execute"])
        assert args.execute is True

    def test_has_resume_flag(self):
        from adapters.experimental.deep_research import get_parser

        args = get_parser().parse_args(["test", "--resume", "int-123"])
        assert args.resume == "int-123"

    def test_has_max_wait_flag(self):
        from adapters.experimental.deep_research import get_parser

        args = get_parser().parse_args(["test", "--max-wait", "600"])
        assert args.max_wait == 600


class TestDeepResearchRun:
    def test_dry_run_shows_warning(self, capsys):
        from adapters.experimental.deep_research import run

        run(prompt="research", execute=False)
        output = capsys.readouterr().out
        assert "[DRY RUN]" in output
        assert "WARNING" in output

    def test_creates_interaction_and_polls(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {
            "status": "completed",
            "outputs": [{"text": "Research findings here."}],
        }

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="research topic", execute=True)
        output = capsys.readouterr().out
        assert "Research findings" in output

    def test_resume_skips_creation(self, capsys):
        from adapters.experimental.deep_research import run

        poll_resp = {
            "status": "completed",
            "outputs": [{"text": "Resumed result."}],
        }

        with (
            patch("adapters.experimental.deep_research.api_call", return_value=poll_resp),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="ignored", resume="int-existing", execute=True)
        assert "Resumed result" in capsys.readouterr().out

    def test_resume_dry_run_skips(self, capsys):
        from adapters.experimental.deep_research import run

        with (
            patch("adapters.experimental.deep_research.api_call") as mock_api,
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="ignored", resume="int-existing", execute=False)
        mock_api.assert_not_called()
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_poll_timeout(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "running"}

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 9999]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=1, output_dir=None)
            run(prompt="research", execute=True)
        output = capsys.readouterr().out
        assert "[POLL TIMEOUT]" in output
        assert "int-abc" in output

    def test_failed_interaction(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "failed", "error": "quota exceeded"}

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="research", execute=True)
        output = capsys.readouterr().out
        assert "FAILED" in output

    def test_cancelled_interaction(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "cancelled"}

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="research", execute=True)
        assert "CANCELLED" in capsys.readouterr().out

    def test_completed_with_no_text(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "completed", "outputs": []}

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="research", execute=True)
        assert "WARNING" in capsys.readouterr().out

    def test_storage_notice_printed(self, capsys):
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "completed", "outputs": [{"text": "done"}]}

        with (
            patch(
                "adapters.experimental.deep_research.api_call", side_effect=[create_resp, poll_resp]
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(deep_research_timeout_seconds=3600, output_dir=None)
            run(prompt="research", execute=True)
        assert "55d paid" in capsys.readouterr().out
