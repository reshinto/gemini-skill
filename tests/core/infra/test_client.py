"""Tests for core/infra/client.py — REST client with retry logic.

Verifies API call construction, header auth, retry classification,
exponential backoff, streaming SSE, and error handling.
All tests mock urllib to avoid network calls.
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
        from core.infra.client import api_call

        response_data = {"models": [{"name": "gemini-2.5-flash"}]}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            result = api_call("models", method="GET")

        assert result == response_data
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "fake-key"
        assert req.get_method() == "GET"

    def test_post_request_sends_json_body(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"candidates": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        body = {"contents": [{"parts": [{"text": "hello"}]}]}
        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            result = api_call("models/gemini-2.5-flash:generateContent", body=body)

        req = mock_urlopen.call_args[0][0]
        assert json.loads(req.data) == body
        assert req.get_header("Content-type") == "application/json"

    def test_uses_v1beta_by_default(self):
        from core.infra.client import api_call, BASE_URL

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert "/v1beta/" in req.full_url

    def test_respects_custom_api_version(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            api_call("models", method="GET", api_version="v1")

        req = mock_urlopen.call_args[0][0]
        assert "/v1/" in req.full_url

    def test_uses_provided_timeout(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            api_call("models", method="GET", timeout=60)

        _, kwargs = mock_urlopen.call_args
        assert kwargs["timeout"] == 60

    def test_never_puts_key_in_url(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="AIzaSyTestKey1234567890123456789012345"):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert "AIza" not in req.full_url
        assert "key=" not in req.full_url


class TestApiCallErrors:
    """api_call() must handle HTTP errors with correct retry behavior."""

    def test_400_raises_api_error_no_retry(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 400, "Bad Request", {}, io.BytesIO(b'{"error": {"message": "bad"}}'))
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            with pytest.raises(APIError, match="400") as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 400

    def test_401_raises_api_error_no_retry(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 401

    def test_429_retries_then_raises(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError) as exc_info:
                api_call("models", method="GET")
            assert exc_info.value.status_code == 429

    def test_429_retries_up_to_max(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            # 1 initial + 3 retries = 4 total calls
            assert mock_urlopen.call_count == 4

    def test_503_retries_then_raises(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 503, "Service Unavailable", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_504_retries_once_for_get(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 504, "Gateway Timeout", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError):
                api_call("models", method="GET")
            # 1 initial + 1 timeout retry = 2
            assert mock_urlopen.call_count == 2

    def test_504_no_retry_for_post(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 504, "Gateway Timeout", {}, io.BytesIO(b'{}'))
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError):
                api_call("models/x:generateContent", body={"x": 1}, method="POST")
            assert mock_urlopen.call_count == 1

    def test_retry_succeeds_on_second_attempt(self):
        from core.infra.client import api_call
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b'{}'))
        mock_success = MagicMock()
        mock_success.read.return_value = b'{"ok": true}'
        mock_success.__enter__ = MagicMock(return_value=mock_success)
        mock_success.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", side_effect=[err, mock_success]), \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            result = api_call("models", method="GET")
        assert result == {"ok": True}

    def test_connection_error_retries(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import URLError

        err = URLError("Connection refused")
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError, match="Connection"):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_timeout_error_retries(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        import socket

        err = socket.timeout("timed out")
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError, match="timed out"):
                api_call("models", method="GET")
            assert mock_urlopen.call_count == 4

    def test_backoff_sleep_intervals(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "Too Many Requests", {}, io.BytesIO(b'{}'))
        sleep_calls = []
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(APIError):
                api_call("models", method="GET")
        # Exponential backoff: 1, 2, 4
        assert sleep_calls == [1, 2, 4]

    def test_http_error_extracts_api_message(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        body = json.dumps({"error": {"message": "Model not found"}}).encode()
        err = HTTPError("http://x", 404, "Not Found", {}, io.BytesIO(body))
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            with pytest.raises(APIError, match="Model not found"):
                api_call("models/nonexistent", method="GET")

    def test_http_error_with_non_json_body(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        from urllib.error import HTTPError

        err = HTTPError("http://x", 500, "Internal Server Error", {}, io.BytesIO(b'not json'))
        with patch("core.infra.client.urlopen", side_effect=err) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"), \
             patch("time.sleep"):
            with pytest.raises(APIError, match="500"):
                api_call("models", method="GET")


class TestStreamGenerateContent:
    """stream_generate_content() must yield SSE chunks correctly."""

    def test_yields_parsed_json_chunks(self):
        from core.infra.client import stream_generate_content

        chunk1 = json.dumps({"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]})
        chunk2 = json.dumps({"candidates": [{"content": {"parts": [{"text": " world"}]}}]})
        sse_data = f"data: {chunk1}\n\ndata: {chunk2}\n\n".encode()

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            chunks = list(stream_generate_content("gemini-2.5-flash", {"contents": []}))

        assert len(chunks) == 2
        assert chunks[0]["candidates"][0]["content"]["parts"][0]["text"] == "Hello"

    def test_uses_alt_sse_in_url(self):
        from core.infra.client import stream_generate_content

        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            list(stream_generate_content("gemini-2.5-flash", {}))

        req = mock_urlopen.call_args[0][0]
        assert "alt=sse" in req.full_url
        assert "streamGenerateContent" in req.full_url

    def test_skips_non_data_lines(self):
        from core.infra.client import stream_generate_content

        chunk = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
        sse_data = f": comment\nevent: message\ndata: {chunk}\n\n".encode()

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            chunks = list(stream_generate_content("gemini-2.5-flash", {}))

        assert len(chunks) == 1

    def test_skips_malformed_json_lines(self):
        from core.infra.client import stream_generate_content

        sse_data = b"data: not-json\n\ndata: {\"ok\": true}\n\n"

        mock_response = MagicMock()
        mock_response.read.return_value = sse_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            chunks = list(stream_generate_content("gemini-2.5-flash", {}))

        assert len(chunks) == 1
        assert chunks[0] == {"ok": True}

    def test_respects_api_version(self):
        from core.infra.client import stream_generate_content

        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            list(stream_generate_content("gemini-2.5-flash", {}, api_version="v1"))

        req = mock_urlopen.call_args[0][0]
        assert "/v1/" in req.full_url


class TestUploadFile:
    """upload_file() must construct multipart upload requests correctly."""

    def test_upload_sends_file_content(self, tmp_path):
        from core.infra.client import upload_file

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content here")

        response_data = {"file": {"name": "files/abc123", "uri": "gs://bucket/abc123"}}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            result = upload_file(test_file, mime_type="application/pdf")

        assert result == response_data

    def test_upload_uses_correct_endpoint(self, tmp_path):
        from core.infra.client import upload_file, BASE_URL

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"file": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            upload_file(test_file, mime_type="text/plain")

        req = mock_urlopen.call_args[0][0]
        assert "upload/v1beta/files" in req.full_url

    def test_upload_sets_display_name(self, tmp_path):
        from core.infra.client import upload_file

        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"data")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"file": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            upload_file(test_file, mime_type="application/pdf", display_name="My Report")

        req = mock_urlopen.call_args[0][0]
        # Request body should contain metadata with display name
        body = req.data
        assert b"My Report" in body


class TestApiCallWithKey:
    """Verify api_call passes the API key via resolve_key."""

    def test_uses_resolve_key_result(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen, \
             patch("core.infra.client.resolve_key", return_value="test-api-key-value"):
            api_call("models", method="GET")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "test-api-key-value"

    def test_accepts_explicit_api_key(self):
        from core.infra.client import api_call

        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.infra.client.urlopen", return_value=mock_response) as mock_urlopen:
            api_call("models", method="GET", api_key="explicit-key")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-goog-api-key") == "explicit-key"


class TestSslErrorHandling:
    """Cover the macOS SSL certificate error path."""

    def test_ssl_error_includes_fix_message(self):
        from core.infra.client import api_call
        from core.infra.errors import APIError
        import ssl

        err = ssl.SSLCertVerificationError("certificate verify failed")
        with patch("core.infra.client.urlopen", side_effect=err), \
             patch("core.infra.client.resolve_key", return_value="fake-key"):
            with pytest.raises(APIError, match="certificate"):
                api_call("models", method="GET")


class TestMimeTypeValidation:
    """upload_file() must reject unsafe MIME types."""

    def test_rejects_crlf_in_mime_type(self, tmp_path):
        from core.infra.client import upload_file

        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsafe MIME type"):
            upload_file(f, mime_type="text/plain\r\nEvil-Header: injected")

    def test_rejects_empty_mime_type(self, tmp_path):
        from core.infra.client import upload_file

        f = tmp_path / "test.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsafe MIME type"):
            upload_file(f, mime_type="")
