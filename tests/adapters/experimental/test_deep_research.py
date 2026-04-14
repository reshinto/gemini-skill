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

    def test_missing_interaction_id_early_exit(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When the Interactions API returns no id, run() prints an error and returns."""
        from adapters.experimental.deep_research import run

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                return_value={},
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "did not return an interaction id" in capsys.readouterr().out

    def test_interaction_id_non_string_early_exit(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-string interaction id (e.g. integer) is also rejected."""
        from adapters.experimental.deep_research import run

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                return_value={"id": 42},
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "did not return an interaction id" in capsys.readouterr().out

    def test_polling_surfaces_failed_status(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``failed`` poll status prints the failure reason and returns."""
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "failed", "error": "rate-limited"}

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                side_effect=[create_resp, poll_resp],
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        captured = capsys.readouterr().out
        assert "FAILED" in captured
        assert "rate-limited" in captured

    def test_polling_surfaces_cancelled_status(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``cancelled`` poll status prints the cancellation and returns."""
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        poll_resp = {"status": "cancelled"}

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                side_effect=[create_resp, poll_resp],
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch("adapters.experimental.deep_research.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "CANCELLED" in capsys.readouterr().out

    def test_emit_result_with_non_dict_output_warns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Last output in the list is NOT a dict — branch 121→126."""
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        # Last output is a string, not a dict — triggers 121→126
        poll_resp = {"status": "completed", "outputs": ["not-a-dict"]}

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                side_effect=[create_resp, poll_resp],
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch(
                "adapters.experimental.deep_research.time.time",
                side_effect=[0, 0, 0],
            ),
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "No text output" in capsys.readouterr().out

    def test_emit_result_with_non_string_text_warns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Last output is a dict but its ``text`` is not a string — branch 123→126."""
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        # text is an integer — triggers 123→126
        poll_resp = {"status": "completed", "outputs": [{"text": 42}]}

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                side_effect=[create_resp, poll_resp],
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            patch(
                "adapters.experimental.deep_research.time.time",
                side_effect=[0, 0, 0],
            ),
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "No text output" in capsys.readouterr().out

    def test_polling_passes_through_non_terminal_status(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-terminal statuses (in_progress) fall through to ``time.sleep``
        so the loop polls again on the next iteration. Covers branches
        121→126 and 123→126 in adapters/experimental/deep_research.py.
        """
        from adapters.experimental.deep_research import run

        create_resp = {"id": "int-abc"}
        in_progress_resp = {"status": "in_progress"}
        completed_resp = {"status": "completed", "outputs": [{"text": "done"}]}

        with (
            patch(
                "adapters.experimental.deep_research.api_call",
                side_effect=[create_resp, in_progress_resp, completed_resp],
            ),
            patch("adapters.experimental.deep_research.load_config") as mock_cfg,
            patch("adapters.experimental.deep_research.time.sleep"),
            # Three time.time() calls: start, check-1, check-2
            patch(
                "adapters.experimental.deep_research.time.time",
                side_effect=[0, 0, 0, 0],
            ),
        ):
            mock_cfg.return_value = MagicMock(
                deep_research_timeout_seconds=3600, output_dir=None
            )
            run(prompt="research", execute=True)
        assert "Research started" in capsys.readouterr().out
