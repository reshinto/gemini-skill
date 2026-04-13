"""Tests for core/transport/base.py — Transport protocol and shared types.

The base module is intentionally tiny but contract-heavy: it defines the
``Transport`` runtime-checkable Protocol that every backend must satisfy,
plus the ``GeminiResponse`` / ``StreamChunk`` / ``FileMetadata`` TypedDicts
that flow through the coordinator. These tests pin the structural contract
so a future PR cannot quietly remove a method or rename a key.

All ``BackendUnavailableError`` assertions live here alongside the Protocol
and TypedDict tests so the base-module contract is tested in one file.
"""

from __future__ import annotations

import pytest


class TestBackendUnavailableError:
    """BackendUnavailableError must inherit from GeminiSkillError so that
    catch-all handlers at the CLI boundary catch it without knowing about
    the transport layer."""

    def test_is_gemini_skill_error_subclass(self):
        from core.infra.errors import GeminiSkillError
        from core.transport.base import BackendUnavailableError

        assert issubclass(BackendUnavailableError, GeminiSkillError)

    def test_carries_message(self):
        from core.transport.base import BackendUnavailableError

        exc = BackendUnavailableError("sdk not importable")
        assert "sdk not importable" in str(exc)

    def test_can_be_caught_as_exception(self):
        from core.transport.base import BackendUnavailableError

        with pytest.raises(Exception):
            raise BackendUnavailableError("boom")


class TestTransportProtocol:
    """Transport is a runtime-checkable Protocol. Any object exposing the
    required methods + name attribute satisfies isinstance(obj, Transport)."""

    def test_protocol_is_runtime_checkable(self):
        from core.transport.base import Transport

        class _Stub:
            name = "stub"

            def api_call(self, endpoint, body, method, api_version, timeout):
                return {}

            def stream_generate_content(self, model, body, api_version, timeout):
                yield {}

            def upload_file(self, file_path, mime_type, display_name, timeout):
                return {}

        assert isinstance(_Stub(), Transport)

    def test_object_missing_method_is_not_transport(self):
        from core.transport.base import Transport

        class _Incomplete:
            name = "incomplete"

            def api_call(self, endpoint, body, method, api_version, timeout):
                return {}

            # missing stream_generate_content and upload_file

        assert not isinstance(_Incomplete(), Transport)

    def test_plain_object_is_not_transport(self):
        from core.transport.base import Transport

        assert not isinstance(object(), Transport)

    def test_raw_http_transport_satisfies_protocol(self):
        """The shipped RawHttpTransport must satisfy the Protocol — this is
        the structural contract that Phase 3's coordinator relies on."""
        from core.transport.base import Transport
        from core.transport.raw_http.transport import RawHttpTransport

        assert isinstance(RawHttpTransport(), Transport)


class TestGeminiResponseTypedDict:
    """GeminiResponse is a TypedDict — at runtime it's just a regular dict.
    Tests pin the recognised keys so accidental renames are caught."""

    def test_can_construct_minimal_envelope(self):
        from core.transport.base import GeminiResponse

        envelope: GeminiResponse = {"candidates": []}
        assert envelope["candidates"] == []

    def test_recognised_keys_are_optional(self):
        """All keys are total=False — an empty envelope is structurally valid."""
        from core.transport.base import GeminiResponse

        envelope: GeminiResponse = {}
        assert envelope == {}

    def test_can_construct_envelope_with_usage_metadata(self):
        from core.transport.base import GeminiResponse

        envelope: GeminiResponse = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}],
            "usageMetadata": {"totalTokenCount": 5},
        }
        assert envelope["usageMetadata"]["totalTokenCount"] == 5


class TestFileMetadataTypedDict:
    """FileMetadata mirrors the Gemini Files API response shape."""

    def test_can_construct_minimal_metadata(self):
        from core.transport.base import FileMetadata

        meta: FileMetadata = {
            "name": "files/abc",
            "displayName": "test.txt",
            "mimeType": "text/plain",
            "sizeBytes": "5",
            "state": "ACTIVE",
            "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc",
        }
        assert meta["name"] == "files/abc"
