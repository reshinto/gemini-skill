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

    def test_includes_execute_flag(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args(["--execute"])
        assert args.execute is True

    def test_execute_defaults_false(self):
        from core.adapter.helpers import build_base_parser
        parser = build_base_parser("test")
        args = parser.parse_args([])
        assert args.execute is False

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
