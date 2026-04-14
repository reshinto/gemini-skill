"""Tests for core/auth/auth.py — API key resolution and .env parsing.

Verifies env var precedence (GEMINI_API_KEY env > GEMINI_API_KEY in .env),
.env file parsing (split on first =, strip matching quotes, skip comments),
and key validation via the models endpoint. The skill deliberately does NOT
honor GOOGLE_API_KEY; tests assert that setting it alone yields AuthError.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestParseEnvContent:
    """parse_env_content() must follow the documented parser rules."""

    def test_basic_key_value(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("MY_KEY=my_value")
        assert result["MY_KEY"] == "my_value"

    def test_split_on_first_equals_only(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("KEY=value=with=equals")
        assert result["KEY"] == "value=with=equals"

    def test_strips_matching_double_quotes(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content('KEY="quoted_value"')
        assert result["KEY"] == "quoted_value"

    def test_strips_matching_single_quotes(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("KEY='single_quoted'")
        assert result["KEY"] == "single_quoted"

    def test_mismatched_quotes_not_stripped(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("KEY=\"mismatched'")
        assert result["KEY"] == "\"mismatched'"

    def test_trims_whitespace(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("  KEY  =  value  ")
        assert result["KEY"] == "value"

    def test_skips_blank_lines(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("\n\nKEY=value\n\n")
        assert result == {"KEY": "value"}

    def test_skips_comment_lines(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("# comment\nKEY=value\n# another")
        assert result == {"KEY": "value"}

    def test_hash_in_value_is_literal(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("KEY=value#with#hash")
        assert result["KEY"] == "value#with#hash"

    def test_empty_value(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("KEY=")
        assert result["KEY"] == ""

    def test_line_without_equals_skipped(self):
        from core.auth.auth import parse_env_content

        result = parse_env_content("NOEQUALS\nKEY=val")
        assert result == {"KEY": "val"}


class TestResolveKey:
    """resolve_key() must follow the documented precedence order."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True)
    def test_gemini_api_key_resolved_from_process_env(self):
        from core.auth.auth import resolve_key

        assert resolve_key() == "gemini_key"

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True)
    def test_google_api_key_alone_yields_auth_error(self):
        """The skill deliberately does NOT honor GOOGLE_API_KEY.

        Setting only GOOGLE_API_KEY (no GEMINI_API_KEY) must raise AuthError,
        proving the legacy precedence has been removed.
        """
        from core.auth.auth import resolve_key
        from core.infra.errors import AuthError

        with pytest.raises(AuthError):
            resolve_key()

    @patch.dict(
        os.environ, {"GOOGLE_API_KEY": "google_key", "GEMINI_API_KEY": "gemini_key"}, clear=True
    )
    def test_google_api_key_ignored_when_gemini_api_key_set(self):
        """Even when both are set, only GEMINI_API_KEY is used."""
        from core.auth.auth import resolve_key

        assert resolve_key() == "gemini_key"

    @patch.dict(os.environ, {}, clear=True)
    def test_reads_from_env_file(self, tmp_path):
        from core.auth.auth import resolve_key

        env_file = tmp_path / ".env"
        env_file.write_text("GEMINI_API_KEY=file_key\n")
        assert resolve_key(env_dir=tmp_path) == "file_key"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "shell_key"}, clear=True)
    def test_shell_env_overrides_env_file(self, tmp_path):
        from core.auth.auth import resolve_key

        env_file = tmp_path / ".env"
        env_file.write_text("GEMINI_API_KEY=file_key\n")
        assert resolve_key(env_dir=tmp_path) == "shell_key"

    @patch.dict(os.environ, {}, clear=True)
    def test_env_file_with_only_google_api_key_yields_auth_error(self, tmp_path):
        """A .env file containing only GOOGLE_API_KEY must NOT satisfy the resolver."""
        from core.auth.auth import resolve_key
        from core.infra.errors import AuthError

        env_file = tmp_path / ".env"
        env_file.write_text("GOOGLE_API_KEY=file_key\n")
        with pytest.raises(AuthError):
            resolve_key(env_dir=tmp_path)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_raises_auth_error(self):
        from core.auth.auth import resolve_key
        from core.infra.errors import AuthError

        with pytest.raises(AuthError):
            resolve_key()


class TestValidateKey:
    """validate_key() must call the models endpoint with the correct header."""

    @patch("core.auth.auth.urlopen")
    def test_success_returns_true(self, mock_urlopen):
        from core.auth.auth import validate_key

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        assert validate_key("test_key") is True

        # Verify header-based auth, not query string
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("X-goog-api-key") == "test_key"
        assert "?key=" not in request.full_url

    @patch("core.auth.auth.urlopen")
    def test_401_raises_auth_error(self, mock_urlopen):
        from core.auth.auth import validate_key
        from core.infra.errors import AuthError
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError("url", 401, "Unauthorized", {}, None)

        with pytest.raises(AuthError):
            validate_key("bad_key")

    @patch("core.auth.auth.urlopen")
    def test_non_401_http_error_raises_auth_error(self, mock_urlopen):
        from core.auth.auth import validate_key
        from core.infra.errors import AuthError
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError("url", 500, "Server Error", {}, None)

        with pytest.raises(AuthError, match="HTTP 500"):
            validate_key("some_key")

    @patch("core.auth.auth.urlopen")
    def test_generic_exception_raises_auth_error(self, mock_urlopen):
        from core.auth.auth import validate_key
        from core.infra.errors import AuthError

        mock_urlopen.side_effect = ConnectionError("network down")

        with pytest.raises(AuthError, match="network down"):
            validate_key("some_key")


class TestLoadEnvFileMissing:
    """_load_env_file must handle missing .env gracefully."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_env_file_no_error(self, tmp_path):
        from core.auth.auth import resolve_key
        from core.infra.errors import AuthError

        # No .env file in tmp_path, no env vars → should raise AuthError
        with pytest.raises(AuthError):
            resolve_key(env_dir=tmp_path)
