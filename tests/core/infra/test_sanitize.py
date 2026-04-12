"""Tests for core/infra/sanitize.py — API key scrubbing and output safety.

Verifies that API key patterns are redacted from all output, that the
global exception hook scrubs tracebacks, and that safe_print sanitizes
before outputting.
"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


class TestSanitizeOutput:
    """sanitize() must scrub API key patterns from text."""

    def test_redacts_gemini_api_key_pattern(self):
        from core.infra.sanitize import sanitize
        key = "AIzaSyA1234567890abcdefghijklmnopqrstuv"
        text = f"Error calling API with key {key}"
        result = sanitize(text)
        assert key not in result
        assert "[REDACTED]" in result

    def test_leaves_normal_text_unchanged(self):
        from core.infra.sanitize import sanitize
        text = "This is a normal response with no secrets"
        assert sanitize(text) == text

    def test_redacts_multiple_keys(self):
        from core.infra.sanitize import sanitize
        key1 = "AIzaSyA1234567890abcdefghijklmnopqrstuv"
        key2 = "AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-x"
        text = f"key1={key1} key2={key2}"
        result = sanitize(text)
        assert key1 not in result
        assert key2 not in result

    def test_redacts_key_in_url(self):
        from core.infra.sanitize import sanitize
        key = "AIzaSyA1234567890abcdefghijklmnopqrstuv"
        url = f"https://api.example.com?key={key}"
        result = sanitize(url)
        assert key not in result


class TestSafePrint:
    """safe_print() must sanitize before printing."""

    def test_safe_print_redacts_key(self, capsys):
        from core.infra.sanitize import safe_print
        key = "AIzaSyA1234567890abcdefghijklmnopqrstuv"
        safe_print(f"Response with {key}")
        captured = capsys.readouterr()
        assert key not in captured.out
        assert "[REDACTED]" in captured.out

    def test_safe_print_normal_text(self, capsys):
        from core.infra.sanitize import safe_print
        safe_print("Hello world")
        captured = capsys.readouterr()
        assert "Hello world" in captured.out


class TestExceptionHook:
    """install_exception_hook() must scrub keys from tracebacks."""

    def test_hook_is_installable(self):
        from core.infra.sanitize import install_exception_hook
        original = sys.excepthook
        try:
            install_exception_hook()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original

    def test_hook_scrubs_key_from_traceback(self, capsys):
        """Verify the installed hook actually scrubs keys from traceback output."""
        from core.infra.sanitize import install_exception_hook
        import io

        original = sys.excepthook
        original_stderr = sys.stderr
        captured_stderr = io.StringIO()
        try:
            install_exception_hook()
            hook = sys.excepthook

            # Create an exception with an API key in the message
            key = "AIzaSyA1234567890abcdefghijklmnopqrstuv"
            try:
                raise ValueError(f"failed with key {key}")
            except ValueError:
                exc_info = sys.exc_info()

            # Call the hook directly, capturing stderr
            sys.stderr = captured_stderr
            hook(*exc_info)
            sys.stderr = original_stderr

            output = captured_stderr.getvalue()
            assert key not in output
            assert "[REDACTED]" in output
            assert "ValueError" in output
        finally:
            sys.excepthook = original
            sys.stderr = original_stderr
