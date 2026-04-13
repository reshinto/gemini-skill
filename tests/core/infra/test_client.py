"""Tests for core/transport/raw_http/client.py — REST client with retry logic.

Verifies API call construction, header auth, retry classification,
exponential backoff, streaming SSE, and error handling.
All tests mock urllib to avoid network calls.

Test imports were retargeted from ``core.infra.client`` (the legacy shim)
to ``core.transport.raw_http.client`` (the canonical location) when the
Phase 3 dual-backend refactor turned the shim into a forwarder over the
TransportCoordinator. The raw HTTP client mechanics are still exactly
the same — these tests pin the urllib-side behavior and would route
through the SDK transport (not the urlopen mock) if they imported via
the shim.
"""

from __future__ import annotations

import io
import json
import time
from unittest.mock import MagicMock, patch, call

import pytest


class TestApiCall:
    """api_call() must build correct requests and handle responses."""

    def test_get_request_returns_parsed_json(self):
        from core.transport.raw_http.client import api_call

        response_data = {"models": [{"name": "gemini-2.5-flash"}]}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            result = api_call("models", method="GET")

        assert result == response_data
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "fake-key"
        assert req.get_method() == "GET"

    def test_post_request_sends_json_body(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"candidates": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        body = {"contents": [{"parts": [{"text": "hello"}]}]}
        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            result = api_call("models/gemini-2.5-flash:generateContent", body=body)

        req = mock_urlopen.call_args[0][0]
        assert json.loads(req.data) == body
        assert req.get_header("Content-type") == "application/json"

    def test_uses_v1beta_by_default(self):
        from core.transport.raw_http.client import api_call, BASE_URL

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert "/v1beta/" in req.full_url

    def test_respects_custom_api_version(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            api_call("models", method="GET", api_version="v1")

        req = mock_urlopen.call_args[0][0]
        assert "/v1/" in req.full_url

    def test_uses_provided_timeout(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            api_call("models", method="GET", timeout=60)

        _, kwargs = mock_urlopen.call_args
        assert kwargs["timeout"] == 60

    def test_never_puts_key_in_url(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch(
                "core.transport.raw_http.client.resolve_key",
                return_value="AIzaSyTestKey1234567890123456789012345",
            ),
        ):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert "AIza" not in req.full_url
        assert "key=" not in req.full_url

    def test_explicit_api_key_never_appears_in_url(self):
        """When a caller bypasses resolve_key() and passes api_key directly,
        the key must still travel via the x-goog-api-key header — never via
        the URL query string. This pins the explicit-key path of api_call."""
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "core.transport.raw_http.client.urlopen", return_value=mock_response
        ) as mock_urlopen:
            api_call(
                "models",
                method="GET",
                api_key="AIzaSyExplicitKey1234567890123456789012",
            )

        req = mock_urlopen.call_args[0][0]
        assert "AIza" not in req.full_url
        assert "key=" not in req.full_url
        assert req.get_header("X-goog-api-key") == "AIzaSyExplicitKey1234567890123456789012"


class TestApiCallErrors:
    """api_call() must handle HTTP errors with correct retry behavior."""

    def test_400_raises_api_error_no_retry(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError(
            "http://x", 400, "Bad Request", {}, io.BytesIO(b'{"error": {"message": "bad"}}')
        )
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError, match="400") as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 400

    def test_401_raises_api_error_no_retry(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 401

    def test_429_retries_then_raises(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 429

    def test_429_retries_up_to_max(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            # 1 initial + 3 retries = 4 total calls
            assert mock_urlopen.call_count == 4

    def test_503_retries_then_raises(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 503, "Service Unavailable", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_504_retries_once_for_get(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 504, "Gateway Timeout", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            # 1 initial + 1 timeout retry = 2
            assert mock_urlopen.call_count == 2

    def test_504_no_retry_for_post(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 504, "Gateway Timeout", {}, io.BytesIO(b"{}"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError):
                api_call("models/x:generateContent", body={"x": 1}, method="POST")
            assert mock_urlopen.call_count == 1

    def test_retry_succeeds_on_second_attempt(self):
        from core.transport.raw_http.client import api_call
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        mock_success = MagicMock()
        mock_success.read.return_value = b'{"ok": true}'
        mock_success.__enter__ = MagicMock(return_value=mock_success)
        mock_success.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=[err, mock_success]),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            result = api_call("models", method="GET")
        assert result == {"ok": True}

    def test_connection_error_retries(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import URLError

        err = URLError("Connection refused")
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError, match="Connection"):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_timeout_error_retries(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        import socket

        err = socket.timeout("timed out")
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError, match="timed out"):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_backoff_sleep_intervals(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        sleep_calls = []
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)),
        ):
            with pytest.raises(APIError):
                api_call("models", method="GET")
        # Exponential backoff: 1, 2, 4
        assert sleep_calls == [1, 2, 4]

    def test_http_error_extracts_api_message(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        body = json.dumps({"error": {"message": "Model not found"}}).encode()
        err = HTTPError("http://x", 404, "Not Found", {}, io.BytesIO(body))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError, match="Model not found"):
                api_call("models/nonexistent", method="GET")

    def test_http_error_with_non_json_body(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 500, "Internal Server Error", {}, io.BytesIO(b"not json"))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),
        ):
            with pytest.raises(APIError, match="500"):
                api_call("models", method="GET")


class TestStreamGenerateContent:
    """stream_generate_content() must yield SSE chunks correctly."""

    def test_yields_parsed_json_chunks(self):
        from core.transport.raw_http.client import stream_generate_content

        chunk1 = json.dumps({"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]})
        chunk2 = json.dumps({"candidates": [{"content": {"parts": [{"text": " world"}]}}]})
        sse_data = f"data: {chunk1}\n\ndata: {chunk2}\n\n".encode()

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            chunks = list(stream_generate_content("gemini-2.5-flash", {"contents": []}))

        assert len(chunks) == 2
        assert chunks[0]["candidates"][0]["content"]["parts"][0]["text"] == "Hello"

    def test_uses_alt_sse_in_url(self):
        from core.transport.raw_http.client import stream_generate_content

        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            list(stream_generate_content("gemini-2.5-flash", {}))

        req = mock_urlopen.call_args[0][0]
        assert "alt=sse" in req.full_url
        assert "streamGenerateContent" in req.full_url

    def test_skips_non_data_lines(self):
        from core.transport.raw_http.client import stream_generate_content

        chunk = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
        sse_data = f": comment\nevent: message\ndata: {chunk}\n\n".encode()

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            chunks = list(stream_generate_content("gemini-2.5-flash", {}))

        assert len(chunks) == 1

    def test_skips_malformed_json_lines(self):
        from core.transport.raw_http.client import stream_generate_content

        sse_data = b'data: not-json\n\ndata: {"ok": true}\n\n'

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            chunks = list(stream_generate_content("gemini-2.5-flash", {}))

        assert len(chunks) == 1
        assert chunks[0] == {"ok": True}

    def test_respects_api_version(self):
        from core.transport.raw_http.client import stream_generate_content

        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            list(stream_generate_content("gemini-2.5-flash", {}, api_version="v1"))

        req = mock_urlopen.call_args[0][0]
        assert "/v1/" in req.full_url


class TestUploadFile:
    """upload_file() must construct multipart upload requests correctly."""

    def test_upload_sends_file_content(self, tmp_path):
        from core.transport.raw_http.client import upload_file

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content here")

        response_data = {"file": {"name": "files/abc123", "uri": "gs://bucket/abc123"}}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            result = upload_file(test_file, mime_type="application/pdf")

        assert result == response_data

    def test_upload_uses_correct_endpoint(self, tmp_path):
        from core.transport.raw_http.client import upload_file, BASE_URL

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"file": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            upload_file(test_file, mime_type="text/plain")

        req = mock_urlopen.call_args[0][0]
        assert "upload/v1beta/files" in req.full_url

    def test_upload_sets_display_name(self, tmp_path):
        from core.transport.raw_http.client import upload_file

        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"data")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"file": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            upload_file(test_file, mime_type="application/pdf", display_name="My Report")

        req = mock_urlopen.call_args[0][0]
        # Request body should contain metadata with display name
        body = req.data
        assert b"My Report" in body


class TestApiCallWithKey:
    """Verify api_call passes the API key via resolve_key."""

    def test_uses_resolve_key_result(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen", return_value=mock_response
            ) as mock_urlopen,
            patch("core.transport.raw_http.client.resolve_key", return_value="test-api-key-value"),
        ):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "test-api-key-value"

    def test_api_call_invokes_resolve_key_with_no_arguments(self):
        """The installed skill reads GEMINI_API_KEY from the process environment
        (Claude Code injects it from ~/.claude/settings.json). The raw HTTP
        client must therefore call resolve_key() with NO arguments — the old
        ``env_dir=_SKILL_ROOT`` path was deleted in the dual-backend refactor.
        """
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="key") as mock_resolve,
        ):
            api_call("models", method="GET")

        mock_resolve.assert_called_once_with()

    def test_stream_generate_content_invokes_resolve_key_with_no_arguments(self):
        """stream_generate_content must follow the same no-arg auth contract."""
        from core.transport.raw_http.client import stream_generate_content

        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="key") as mock_resolve,
        ):
            list(stream_generate_content("gemini-2.5-flash", {"contents": []}))

        mock_resolve.assert_called_once_with()

    def test_upload_file_invokes_resolve_key_with_no_arguments(self, tmp_path):
        """upload_file must follow the same no-arg auth contract."""
        from core.transport.raw_http.client import upload_file

        f = tmp_path / "tiny.txt"
        f.write_text("hi")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"name": "files/abc"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("core.transport.raw_http.client.urlopen", return_value=mock_response),
            patch("core.transport.raw_http.client.resolve_key", return_value="key") as mock_resolve,
        ):
            upload_file(str(f), "text/plain")

        mock_resolve.assert_called_once_with()

    def test_accepts_explicit_api_key(self):
        from core.transport.raw_http.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "core.transport.raw_http.client.urlopen", return_value=mock_response
        ) as mock_urlopen:
            api_call("models", method="GET", api_key="explicit-key")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "explicit-key"


class TestSslErrorHandling:
    """Cover the macOS SSL certificate error path."""

    def test_ssl_error_includes_fix_message(self):
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError
        import ssl

        err = ssl.SSLCertVerificationError("certificate verify failed")
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError, match="certificate"):
                api_call("models", method="GET")


class TestErrorMessageSanitization:
    """Every code path that surfaces an upstream error string must pass the
    string through ``sanitize()`` so an echoed-back API key is redacted
    before it lands in an APIError, log line, or traceback. These tests pin
    that the sanitize() call actually fires on each path — without them, a
    future refactor could silently delete the call and only a live test
    against a misbehaving upstream would catch the regression.
    """

    _FAKE_KEY = "AIzaSyTestKey12345678901234567890123456"  # AIza + 35 chars = 39 total

    def test_4xx_error_body_with_embedded_key_is_redacted(self):
        """A 400 response whose JSON error message echoes back the API key
        must be sanitized before APIError carries it. Pins the sanitize()
        call inside _extract_error_message's structured-JSON branch."""
        import io
        from urllib.error import HTTPError
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError

        body = (
            b'{"error": {"message": "Invalid request from key ' + self._FAKE_KEY.encode() + b'"}}'
        )
        err = HTTPError("http://x", 400, "Bad Request", {}, io.BytesIO(body))
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")

        rendered = str(exc_info.value)
        assert self._FAKE_KEY not in rendered
        assert "[REDACTED]" in rendered

    def test_4xx_error_fallback_path_with_embedded_key_is_redacted(self):
        """A 400 whose body is malformed JSON falls through to the second
        return path of _extract_error_message (HTTP {code} {reason}). Pins
        the sanitize() call on that fallback path. We embed the key in the
        ``reason`` string so the fallback branch has something to redact."""
        import io
        from urllib.error import HTTPError
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError

        err = HTTPError(
            "http://x",
            400,
            f"Bad Request {self._FAKE_KEY}",
            {},
            io.BytesIO(b"not valid json"),
        )
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")

        rendered = str(exc_info.value)
        assert self._FAKE_KEY not in rendered
        assert "[REDACTED]" in rendered

    def test_ssl_error_with_embedded_key_is_redacted(self):
        """SSLCertVerificationError.__str__ may embed certificate fields
        that an attacker controls. Pins the sanitize() call on the SSL
        branch in _execute_with_retry."""
        import ssl
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError

        err = ssl.SSLCertVerificationError(
            f"cert verify failed: subject contained {self._FAKE_KEY}"
        )
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")

        rendered = str(exc_info.value)
        assert self._FAKE_KEY not in rendered
        assert "[REDACTED]" in rendered

    def test_network_error_with_embedded_key_is_redacted(self):
        """A ConnectionError whose ``str()`` representation contains a key
        (e.g. from a custom transport wrapper) must be sanitized. Pins the
        sanitize() call on the network-error branch."""
        from core.transport.raw_http.client import api_call
        from core.infra.errors import APIError

        err = ConnectionError(f"connection reset, attempted url with {self._FAKE_KEY}")
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="fake-key"),
            patch("time.sleep"),  # skip the backoff delays
        ):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")

        rendered = str(exc_info.value)
        assert self._FAKE_KEY not in rendered
        assert "[REDACTED]" in rendered


class TestMimeTypeValidation:
    """upload_file() must reject unsafe MIME types."""

    def test_rejects_crlf_in_mime_type(self, tmp_path):
        from core.transport.raw_http.client import upload_file

        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsafe MIME type"):
            upload_file(f, mime_type="text/plain\r\nEvil-Header: injected")

    def test_rejects_empty_mime_type(self, tmp_path):
        from core.transport.raw_http.client import upload_file

        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsafe MIME type"):
            upload_file(f, mime_type="")


class TestDownloadFileBytes:
    """Phase 7: download a file's raw bytes via ``GET <files/{name}>?alt=media``.

    The response is binary, not JSON, so the helper bypasses the
    ``api_call`` json.loads path entirely and reads the raw bytes via
    ``urlopen(...).read()``.
    """

    def test_returns_raw_bytes(self):
        from core.transport.raw_http.client import download_file_bytes

        mock_response = MagicMock()
        mock_response.read.return_value = b"\x89PNG raw data"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen",
                return_value=mock_response,
            ),
            patch("core.transport.raw_http.client.resolve_key", return_value="k"),
        ):
            result = download_file_bytes("files/abc")
        assert result == b"\x89PNG raw data"

    def test_uses_correct_url_and_header(self):
        from core.transport.raw_http.client import download_file_bytes

        mock_response = MagicMock()
        mock_response.read.return_value = b"x"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen",
                return_value=mock_response,
            ) as mock_urlopen,
            patch(
                "core.transport.raw_http.client.resolve_key",
                return_value="test-key",
            ),
        ):
            download_file_bytes("files/abc")
        req = mock_urlopen.call_args.args[0]
        assert req.full_url.endswith("/v1beta/files/abc?alt=media")
        assert req.headers["X-goog-api-key"] == "test-key"
        assert req.get_method() == "GET"

    def test_http_error_becomes_apierror(self):
        from urllib.error import HTTPError

        from core.infra.errors import APIError
        from core.transport.raw_http.client import download_file_bytes

        err = HTTPError(
            "http://x", 404, "Not Found", {}, io.BytesIO(b'{"error":{"message":"missing"}}')
        )
        with (
            patch("core.transport.raw_http.client.urlopen", side_effect=err),
            patch("core.transport.raw_http.client.resolve_key", return_value="k"),
        ):
            with pytest.raises(APIError) as excinfo:
                download_file_bytes("files/abc")
        assert excinfo.value.status_code == 404

    def test_network_error_becomes_apierror(self):
        import socket

        from core.infra.errors import APIError
        from core.transport.raw_http.client import download_file_bytes

        with (
            patch(
                "core.transport.raw_http.client.urlopen",
                side_effect=socket.timeout("timed out"),
            ),
            patch("core.transport.raw_http.client.resolve_key", return_value="k"),
        ):
            with pytest.raises(APIError, match="network error"):
                download_file_bytes("files/abc")

    def test_handles_non_bytes_read_result(self):
        """Some mock urlopen implementations return bytearray or memoryview;
        the helper must coerce to bytes for a consistent return type."""
        from core.transport.raw_http.client import download_file_bytes

        mock_response = MagicMock()
        mock_response.read.return_value = bytearray(b"raw")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "core.transport.raw_http.client.urlopen",
                return_value=mock_response,
            ),
            patch("core.transport.raw_http.client.resolve_key", return_value="k"),
        ):
            result = download_file_bytes("files/abc")
        assert isinstance(result, bytes)
        assert result == b"raw"
