"""Tests for core/adapter/helpers.py — shared adapter lifecycle helpers.

Verifies argument parsing, dry-run enforcement, cost tracking integration,
and output emission helpers.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBuildBaseParser:
    """build_base_parser() must return a parser with common flags."""

    def test_includes_model_flag(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args(["--model", "gemini-2.5-pro"])
        assert args.model == "gemini-2.5-pro"

    def test_model_is_optional(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args([])
        assert args.model is None

    def test_execute_defaults_false(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args([])
        assert args.execute is False

    def test_base_parser_rejects_execute_flag(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        with pytest.raises(SystemExit):
            parser.parse_args(["--execute"])

    def test_includes_session_flags(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args(["--session", "review-1"])
        assert args.session == "review-1"

    def test_includes_continue_flag(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args(["--continue"])
        assert args.continue_session is True

    def test_description_set(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("Text generation")
        assert "Text generation" in parser.description


class TestAddExecuteFlag:
    def test_includes_execute_flag(self):
        from core.adapter.helpers import add_execute_flag, build_base_parser

        parser = build_base_parser("test")
        add_execute_flag(parser)
        args = parser.parse_args(["--execute"])
        assert args.execute is True

    def test_execute_defaults_false(self):
        from core.adapter.helpers import add_execute_flag, build_base_parser

        parser = build_base_parser("test")
        add_execute_flag(parser)
        args = parser.parse_args([])
        assert args.execute is False


class TestCheckDryRun:
    """check_dry_run() must enforce dry-run policy for mutating ops."""

    def test_returns_true_when_dry_run(self, capsys):
        from core.adapter.helpers import check_dry_run
        result = check_dry_run(execute=False, operation="upload file")
        assert result is True
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "upload file" in captured.out

    def test_returns_false_when_execute(self):
        from core.adapter.helpers import check_dry_run
        result = check_dry_run(execute=True, operation="upload file")
        assert result is False


class TestEmitOutput:
    """emit_output() must print or save based on size."""

    def test_short_output_prints(self, capsys):
        from core.adapter.helpers import emit_output
        emit_output("Hello world")
        captured = capsys.readouterr()
        assert "Hello world" in captured.out

    def test_large_output_saves_to_file(self, tmp_path, capsys):
        from core.adapter.helpers import emit_output
        large_text = "x" * 60_000
        emit_output(large_text, output_dir=str(tmp_path))
        captured = capsys.readouterr()
        assert "saved to" in captured.out.lower() or "Response saved" in captured.out
        # Check the file was created
        files = list(tmp_path.glob("gemini-skill-*.txt"))
        assert len(files) == 1
        assert files[0].read_text() == large_text

    def test_large_output_uses_tempdir_by_default(self, capsys):
        from core.adapter.helpers import emit_output
        import tempfile
        large_text = "x" * 60_000
        emit_output(large_text)
        captured = capsys.readouterr()
        assert "saved to" in captured.out.lower() or "Response saved" in captured.out

    def test_threshold_boundary(self, capsys):
        from core.adapter.helpers import emit_output
        # Exactly at threshold should print normally
        text = "x" * 50_000
        emit_output(text)
        captured = capsys.readouterr()
        assert text in captured.out


class TestEmitJson:
    """emit_json() must output structured JSON."""

    def test_emits_json(self, capsys):
        from core.adapter.helpers import emit_json
        emit_json({"path": "/tmp/out.png", "size": 1234})
        captured = capsys.readouterr()
        import json
        data = json.loads(captured.out)
        assert data["path"] == "/tmp/out.png"


class TestExtractText:
    """extract_text() must return text or raise on safety blocks."""

    def test_returns_text_from_valid_response(self):
        from core.adapter.helpers import extract_text
        response = {
            "candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]
        }
        assert extract_text(response) == "Hello world"

    def test_skips_non_text_parts(self):
        from core.adapter.helpers import extract_text
        response = {
            "candidates": [{
                "content": {"parts": [
                    {"inlineData": {"data": "x"}},
                    {"text": "after"},
                ]}
            }]
        }
        assert extract_text(response) == "after"

    def test_raises_on_no_candidates(self):
        from core.adapter.helpers import extract_text
        import pytest
        with pytest.raises(ValueError, match="no candidates"):
            extract_text({"candidates": []})

    def test_raises_with_block_reason(self):
        from core.adapter.helpers import extract_text
        import pytest
        with pytest.raises(ValueError, match="SAFETY"):
            extract_text({"promptFeedback": {"blockReason": "SAFETY"}})

    def test_raises_on_unknown_block(self):
        from core.adapter.helpers import extract_text
        import pytest
        with pytest.raises(ValueError, match="unknown"):
            extract_text({})

    def test_returns_empty_string_if_no_text_part(self):
        from core.adapter.helpers import extract_text
        response = {"candidates": [{"content": {"parts": [{"inlineData": {}}]}}]}
        assert extract_text(response) == ""


class TestExtractParts:
    """extract_parts() must return parts list or raise."""

    def test_returns_parts(self):
        from core.adapter.helpers import extract_parts
        parts = [{"text": "hi"}, {"functionCall": {"name": "f"}}]
        response = {"candidates": [{"content": {"parts": parts}}]}
        assert extract_parts(response) == parts

    def test_raises_on_no_candidates(self):
        from core.adapter.helpers import extract_parts
        import pytest
        with pytest.raises(ValueError, match="no candidates"):
            extract_parts({"promptFeedback": {"blockReason": "OTHER"}})

    def test_returns_empty_when_no_parts(self):
        from core.adapter.helpers import extract_parts
        response = {"candidates": [{"content": {}}]}
        assert extract_parts(response) == []


class TestCreateMediaOutputFile:
    """create_media_output_file() must return a unique writable path."""

    def test_creates_file_in_dir(self, tmp_path):
        from core.adapter.helpers import create_media_output_file
        import os
        path = create_media_output_file(".png", str(tmp_path))
        assert path.endswith(".png")
        assert os.path.exists(path)
        assert str(tmp_path) in path

    def test_creates_file_in_tempdir_by_default(self):
        from core.adapter.helpers import create_media_output_file
        import os
        path = create_media_output_file(".wav")
        assert os.path.exists(path)
        os.unlink(path)

    def test_unique_paths(self, tmp_path):
        from core.adapter.helpers import create_media_output_file
        p1 = create_media_output_file(".png", str(tmp_path))
        p2 = create_media_output_file(".png", str(tmp_path))
        assert p1 != p2


class TestMimeToExt:
    """mime_to_ext() must map MIME types to extensions with a default."""

    def test_known_mime(self):
        from core.adapter.helpers import mime_to_ext
        mapping = {"image/png": ".png", "image/jpeg": ".jpg"}
        assert mime_to_ext("image/png", mapping, ".bin") == ".png"

    def test_unknown_uses_default(self):
        from core.adapter.helpers import mime_to_ext
        mapping = {"image/png": ".png"}
        assert mime_to_ext("image/gif", mapping, ".bin") == ".bin"
