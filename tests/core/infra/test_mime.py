"""Tests for core/infra/mime.py — MIME type detection helper.

Verifies version-gated MIME detection: guess_file_type() on 3.13+,
guess_type() on 3.9-3.12. Neither inspects file contents.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


class TestGuessMimeForPath:
    """guess_mime_for_path() must return correct MIME types for known extensions."""

    def test_png_file(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "image.png"
        p.touch()
        assert guess_mime_for_path(p) == "image/png"

    def test_pdf_file(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "doc.pdf"
        p.touch()
        assert guess_mime_for_path(p) == "application/pdf"

    def test_mp4_file(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "video.mp4"
        p.touch()
        assert guess_mime_for_path(p) == "video/mp4"

    def test_json_file(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "data.json"
        p.touch()
        assert guess_mime_for_path(p) == "application/json"

    def test_unknown_extension_returns_fallback(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "file.xyzabc"
        p.touch()
        result = guess_mime_for_path(p)
        assert result == "application/octet-stream"

    def test_accepts_string_path(self, tmp_path):
        from core.infra.mime import guess_mime_for_path
        p = tmp_path / "test.txt"
        p.touch()
        result = guess_mime_for_path(str(p))
        assert result == "text/plain"

    def test_no_cgi_module_used(self):
        """Verify the mime module does not import cgi (removed in 3.13)."""
        import importlib
        mod = importlib.import_module("core.infra.mime")
        source = Path(mod.__file__).read_text()
        assert "import cgi" not in source
        assert "from cgi" not in source
