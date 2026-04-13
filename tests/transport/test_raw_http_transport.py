"""Tests for core/transport/raw_http/transport.py — RawHttpTransport.

RawHttpTransport is a thin Protocol-shaped wrapper over the existing
``core/transport/raw_http/client.py`` functions. The behavior under test
here is delegation only: each method must forward all arguments to the
right client function and pass the result through unchanged. The deeper
behavior (retries, SSE parsing, multipart upload) is covered by
``tests/core/infra/test_client.py`` against the moved module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestRawHttpTransportName:
    """The Protocol contract requires a ``name`` Literal."""

    def test_name_is_raw_http(self):
        from core.transport.raw_http.transport import RawHttpTransport

        assert RawHttpTransport().name == "raw_http"

    def test_name_is_class_attribute_for_protocol_check(self):
        """``isinstance(obj, Transport)`` reads ``name`` as an attribute,
        which means it must exist BEFORE __init__ runs (class-level)."""
        from core.transport.raw_http.transport import RawHttpTransport

        assert hasattr(RawHttpTransport, "name")
        assert RawHttpTransport.name == "raw_http"


class TestRawHttpTransportSupports:
    """RawHttpTransport claims every capability — urllib can issue any REST
    call, so the deterministic-fallback contract requires a True for all
    capability names (including unknown ones the dispatch table will catch
    later)."""

    @pytest.mark.parametrize(
        "capability",
        [
            "text",
            "structured",
            "multimodal",
            "streaming",
            "embed",
            "token_count",
            "function_calling",
            "code_exec",
            "search",
            "image_gen",
            "video_gen",
            "files",
            "cache",
            "batch",
            # Capabilities the SDK does NOT support — raw HTTP must say yes
            # so the coordinator can route them here.
            "maps",
            "music_gen",
            "computer_use",
            "file_search",
            "deep_research",
            # Unknown name — still True (dispatch layer's problem, not ours).
            "totally-made-up",
            "",
        ],
    )
    def test_supports_returns_true_for_every_capability(self, capability: str) -> None:
        from core.transport.raw_http.transport import RawHttpTransport

        assert RawHttpTransport().supports(capability) is True


class TestApiCallDelegation:
    """api_call must forward every argument to the underlying client function."""

    def test_forwards_all_kwargs(self):
        from core.transport.raw_http.transport import RawHttpTransport

        with patch("core.transport.raw_http.transport._client_api_call") as mock:
            mock.return_value = {"candidates": []}
            transport = RawHttpTransport()
            result = transport.api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        assert result == {"candidates": []}
        mock.assert_called_once_with(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

    def test_propagates_client_exception(self):
        from core.infra.errors import APIError
        from core.transport.raw_http.transport import RawHttpTransport

        with patch("core.transport.raw_http.transport._client_api_call") as mock:
            mock.side_effect = APIError("boom", status_code=500)
            with pytest.raises(APIError, match="boom"):
                RawHttpTransport().api_call(
                    endpoint="models",
                    body=None,
                    method="GET",
                    api_version="v1beta",
                    timeout=30,
                )


class TestStreamDelegation:
    """stream_generate_content must forward and yield from the underlying generator."""

    def test_yields_each_chunk(self):
        from core.transport.raw_http.transport import RawHttpTransport

        def fake_stream(model, body, api_version, timeout):
            yield {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
            yield {"candidates": [{"content": {"parts": [{"text": " world"}]}}]}

        with patch(
            "core.transport.raw_http.transport._client_stream_generate_content",
            side_effect=fake_stream,
        ):
            chunks = list(
                RawHttpTransport().stream_generate_content(
                    model="gemini-2.5-flash",
                    body={"contents": []},
                    api_version="v1beta",
                    timeout=30,
                )
            )

        assert len(chunks) == 2
        assert chunks[0]["candidates"][0]["content"]["parts"][0]["text"] == "hello"

    def test_forwards_kwargs(self):
        from core.transport.raw_http.transport import RawHttpTransport

        captured: dict[str, object] = {}

        def fake_stream(model, body, api_version, timeout):
            captured.update(
                {"model": model, "body": body, "api_version": api_version, "timeout": timeout}
            )
            yield from ()

        with patch(
            "core.transport.raw_http.transport._client_stream_generate_content",
            side_effect=fake_stream,
        ):
            list(
                RawHttpTransport().stream_generate_content(
                    model="gemini-2.5-flash",
                    body={"contents": [{"parts": [{"text": "hi"}]}]},
                    api_version="v1beta",
                    timeout=45,
                )
            )

        assert captured == {
            "model": "gemini-2.5-flash",
            "body": {"contents": [{"parts": [{"text": "hi"}]}]},
            "api_version": "v1beta",
            "timeout": 45,
        }


class TestUploadDelegation:
    """upload_file must forward kwargs and return the FileMetadata dict."""

    def test_forwards_all_kwargs(self, tmp_path):
        from core.transport.raw_http.transport import RawHttpTransport

        f = tmp_path / "tiny.txt"
        f.write_text("hi")

        with patch("core.transport.raw_http.transport._client_upload_file") as mock:
            mock.return_value = {
                "name": "files/abc",
                "displayName": "tiny.txt",
                "mimeType": "text/plain",
                "sizeBytes": "2",
                "state": "ACTIVE",
                "uri": "https://example.invalid/v1beta/files/abc",
            }
            result = RawHttpTransport().upload_file(
                file_path=f,
                mime_type="text/plain",
                display_name="tiny.txt",
                timeout=120,
            )

        assert result["name"] == "files/abc"
        mock.assert_called_once_with(
            file_path=f,
            mime_type="text/plain",
            display_name="tiny.txt",
            timeout=120,
        )

    def test_accepts_string_path(self, tmp_path):
        from core.transport.raw_http.transport import RawHttpTransport

        f = tmp_path / "tiny.txt"
        f.write_text("hi")

        with patch("core.transport.raw_http.transport._client_upload_file") as mock:
            mock.return_value = {"name": "files/x"}
            RawHttpTransport().upload_file(
                file_path=str(f),
                mime_type="text/plain",
                display_name=None,
                timeout=60,
            )

        mock.assert_called_once_with(
            file_path=str(f),
            mime_type="text/plain",
            display_name=None,
            timeout=60,
        )
