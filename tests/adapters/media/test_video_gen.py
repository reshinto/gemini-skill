"""Tests for adapters/media/video_gen.py — video generation adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestVideoGenGetParser:
    def test_has_prompt(self):
        from adapters.media.video_gen import get_parser

        args = get_parser().parse_args(["a sunset"])
        assert args.prompt == "a sunset"

    def test_has_poll_interval(self):
        from adapters.media.video_gen import get_parser

        args = get_parser().parse_args(["sunset", "--poll-interval", "30"])
        assert args.poll_interval == 30


class TestVideoGenRun:
    def test_dry_run_skips(self, capsys):
        from adapters.media.video_gen import run

        run(prompt="sunset", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_submits_long_running_operation(self, tmp_path, capsys):
        from adapters.media.video_gen import run

        op_response = {"name": "operations/veo-1"}
        done_response = {
            "done": True,
            "response": {
                "generatedVideos": [{"video": {"uri": "https://storage.example.com/video.mp4"}}],
            },
        }
        with (
            patch("adapters.media.video_gen.api_call", side_effect=[op_response, done_response]),
            patch("adapters.media.video_gen._download", return_value=b"video-data"),
            patch("adapters.media.video_gen.load_config") as mock_cfg,
            patch("adapters.media.video_gen.time.sleep"),
            patch("adapters.media.video_gen.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="sunset", execute=True)
        output = capsys.readouterr().out
        assert '"mime_type": "video/mp4"' in output
        assert '"size_bytes"' in output

    def test_poll_timeout(self, capsys):
        from adapters.media.video_gen import run

        op_response = {"name": "operations/veo-1"}
        not_done = {"done": False}
        with (
            patch("adapters.media.video_gen.api_call", side_effect=[op_response, not_done]),
            patch("adapters.media.video_gen.load_config") as mock_cfg,
            patch("adapters.media.video_gen.time.sleep"),
            patch("adapters.media.video_gen.time.time", side_effect=[0, 0, 2000]),
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="sunset", execute=True, max_wait=1)
        assert "[POLL TIMEOUT]" in capsys.readouterr().out

    def test_no_video_uri_in_response(self, capsys):
        from adapters.media.video_gen import run

        op_response = {"name": "ops/1"}
        done_response = {"done": True, "response": {}}
        with (
            patch("adapters.media.video_gen.api_call", side_effect=[op_response, done_response]),
            patch("adapters.media.video_gen.load_config") as mock_cfg,
            patch("adapters.media.video_gen.time.sleep"),
            patch("adapters.media.video_gen.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="sunset", execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestDownload:
    def test_downloads_content(self):
        from adapters.media.video_gen import _download
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"video-bytes"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("adapters.media.video_gen.urlopen", return_value=mock_resp):
            data = _download("https://example.com/v.mp4")
        assert data == b"video-bytes"


class TestVideoGenOutputDir:
    def test_output_dir_used_for_download_path(self, tmp_path, capsys):
        """Ensure videos are saved to the requested output_dir via the shared helper."""
        from adapters.media.video_gen import run

        op = {"name": "operations/veo-x"}
        done = {
            "done": True,
            "response": {"generatedVideos": [{"video": {"uri": "https://ex/v.mp4"}}]},
        }
        with (
            patch("adapters.media.video_gen.api_call", side_effect=[op, done]),
            patch("adapters.media.video_gen._download", return_value=b"bytes"),
            patch("adapters.media.video_gen.load_config") as mock_cfg,
            patch("adapters.media.video_gen.time.sleep"),
            patch("adapters.media.video_gen.time.time", side_effect=[0, 0, 0]),
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="sunset", execute=True, output_dir=str(tmp_path))
        assert str(tmp_path) in capsys.readouterr().out


class TestExtractVideoUri:
    def test_extracts_uri(self):
        from adapters.media.video_gen import _extract_video_uri

        status = {
            "response": {
                "generatedVideos": [{"video": {"uri": "https://example.com/v.mp4"}}],
            },
        }
        assert _extract_video_uri(status) == "https://example.com/v.mp4"

    def test_returns_none_on_missing(self):
        from adapters.media.video_gen import _extract_video_uri

        assert _extract_video_uri({}) is None
        assert _extract_video_uri({"response": {}}) is None
        assert _extract_video_uri({"response": {"generatedVideos": []}}) is None

    def test_returns_none_on_malformed(self):
        from adapters.media.video_gen import _extract_video_uri

        # Trigger the except branch with bad data types
        assert _extract_video_uri({"response": {"generatedVideos": "not-a-list"}}) is None

    def test_returns_none_when_response_not_dict(self) -> None:
        """Branch: ``status.get('response')`` is not a dict."""
        from adapters.media.video_gen import _extract_video_uri

        assert _extract_video_uri({"response": "string-not-dict"}) is None
        assert _extract_video_uri({"response": 42}) is None

    def test_returns_none_when_first_video_not_dict(self) -> None:
        """Branch: the first generatedVideos entry is not a dict."""
        from adapters.media.video_gen import _extract_video_uri

        status: dict[str, object] = {
            "response": {"generatedVideos": ["not-a-dict"]},
        }
        assert _extract_video_uri(status) is None

    def test_returns_none_when_video_subdict_missing(self) -> None:
        """Branch: entry lacks a ``video`` dict key."""
        from adapters.media.video_gen import _extract_video_uri

        status: dict[str, object] = {
            "response": {"generatedVideos": [{"other": "value"}]},
        }
        assert _extract_video_uri(status) is None

    def test_returns_none_when_video_subdict_not_dict(self) -> None:
        """Branch: ``video`` value is a non-dict type."""
        from adapters.media.video_gen import _extract_video_uri

        status: dict[str, object] = {
            "response": {"generatedVideos": [{"video": "string-not-dict"}]},
        }
        assert _extract_video_uri(status) is None

    def test_returns_none_when_uri_not_string(self) -> None:
        """Branch: ``uri`` present but not a string."""
        from adapters.media.video_gen import _extract_video_uri

        status: dict[str, object] = {
            "response": {"generatedVideos": [{"video": {"uri": 42}}]},
        }
        assert _extract_video_uri(status) is None


class TestVideoGenRunErrorPaths:
    """Coverage for error branches in ``run`` (lines 87-89)."""

    def test_missing_operation_name_early_exit(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When predictLongRunning does NOT return an operation name,
        run() prints the error, emits the raw op JSON, and returns early."""
        from unittest.mock import MagicMock, patch

        from adapters.media.video_gen import run

        with (
            patch("adapters.media.video_gen.api_call", return_value={}),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.media.video_gen.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "veo-3"
            mock_cfg.return_value = MagicMock(
                prefer_preview_models=False, output_dir=None
            )
            run(prompt="sunset", execute=True, output_dir=str(tmp_path))

        captured = capsys.readouterr().out
        assert "did not return an operation name" in captured

    def test_missing_video_uri_after_poll(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When polling completes but the response lacks a usable URI,
        run() emits the error and returns without writing any file."""
        from unittest.mock import MagicMock, patch

        from adapters.media.video_gen import run

        done_status: dict[str, object] = {"done": True, "response": {}}

        def fake_api_call(endpoint: str, **kwargs: object) -> dict[str, object]:
            if "predictLongRunning" in endpoint:
                return {"name": "operations/xyz"}
            return done_status

        with (
            patch("adapters.media.video_gen.api_call", side_effect=fake_api_call),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.media.video_gen.load_config") as mock_cfg,
            patch("adapters.media.video_gen.time.time", side_effect=[0, 1, 2]),
            patch("adapters.media.video_gen.time.sleep"),
        ):
            mock_router_cls.return_value.select_model.return_value = "veo-3"
            mock_cfg.return_value = MagicMock(
                prefer_preview_models=False, output_dir=None
            )
            run(prompt="sunset", execute=True, output_dir=str(tmp_path))

        captured = capsys.readouterr().out
        assert "No video URI" in captured
