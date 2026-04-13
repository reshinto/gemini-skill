"""Tests for core/transport/normalize.py — SDK → REST envelope translation.

The normalize layer is the contract bridge between the google-genai SDK
(which emits pydantic models with snake_case field names) and the existing
adapter helpers (which read camelCase REST envelope dicts).

Architectural decision (per the dual-backend refactor plan): we do NOT
trust ``model_dump(by_alias=True)`` to emit the right shape because alias
coverage is inconsistent across nested SDK types. Instead, we walk the
dict produced by ``model_dump(exclude_none=True)`` (snake_case) and
recursively translate keys via an explicit snake→camel mapping table.

This file covers the translation function with focused fixture-style
inputs that exercise every supported field, plus the validator that
catches structural drift in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestSnakeToCamelMapping:
    """The explicit mapping table is the canonical source of truth for
    field-name translation. Tests pin every entry so a future PR cannot
    silently drop one."""

    def test_table_includes_usage_metadata_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["usage_metadata"] == "usageMetadata"
        assert _SNAKE_TO_CAMEL["prompt_token_count"] == "promptTokenCount"
        assert _SNAKE_TO_CAMEL["candidates_token_count"] == "candidatesTokenCount"
        assert _SNAKE_TO_CAMEL["total_token_count"] == "totalTokenCount"
        assert _SNAKE_TO_CAMEL["cached_content_token_count"] == "cachedContentTokenCount"

    def test_table_includes_candidate_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["finish_reason"] == "finishReason"
        assert _SNAKE_TO_CAMEL["safety_ratings"] == "safetyRatings"
        assert _SNAKE_TO_CAMEL["grounding_metadata"] == "groundingMetadata"

    def test_table_includes_part_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["function_call"] == "functionCall"
        assert _SNAKE_TO_CAMEL["function_response"] == "functionResponse"
        assert _SNAKE_TO_CAMEL["executable_code"] == "executableCode"
        assert _SNAKE_TO_CAMEL["code_execution_result"] == "codeExecutionResult"
        assert _SNAKE_TO_CAMEL["inline_data"] == "inlineData"
        assert _SNAKE_TO_CAMEL["mime_type"] == "mimeType"

    def test_table_includes_file_metadata_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["display_name"] == "displayName"
        assert _SNAKE_TO_CAMEL["size_bytes"] == "sizeBytes"
        assert _SNAKE_TO_CAMEL["create_time"] == "createTime"
        assert _SNAKE_TO_CAMEL["update_time"] == "updateTime"
        assert _SNAKE_TO_CAMEL["expiration_time"] == "expirationTime"
        assert _SNAKE_TO_CAMEL["sha256_hash"] == "sha256Hash"

    def test_table_includes_grounding_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["web_search_queries"] == "webSearchQueries"
        assert _SNAKE_TO_CAMEL["grounding_chunks"] == "groundingChunks"
        assert _SNAKE_TO_CAMEL["search_entry_point"] == "searchEntryPoint"
        assert _SNAKE_TO_CAMEL["rendered_content"] == "renderedContent"
        assert _SNAKE_TO_CAMEL["retrieved_context"] == "retrievedContext"

    def test_table_includes_prompt_feedback_keys(self):
        from core.transport.normalize import _SNAKE_TO_CAMEL

        assert _SNAKE_TO_CAMEL["prompt_feedback"] == "promptFeedback"
        assert _SNAKE_TO_CAMEL["block_reason"] == "blockReason"


class TestTranslateKeysShallow:
    """_translate_keys must rename top-level snake_case keys to camelCase."""

    def test_renames_known_keys(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys({"usage_metadata": {"total_token_count": 5}})
        assert "usageMetadata" in out
        assert "totalTokenCount" in out["usageMetadata"]

    def test_passes_through_unknown_keys_untouched(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys({"already_camel": 1, "candidates": []})
        # 'already_camel' is not in the table so it survives as-is.
        # The validator (separate concern) is what catches unexpected keys.
        assert out["already_camel"] == 1
        assert out["candidates"] == []

    def test_passes_through_camel_keys_untouched(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys({"candidates": [{"finishReason": "STOP"}]})
        assert out["candidates"][0]["finishReason"] == "STOP"

    def test_recurses_into_nested_dicts(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys(
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "hi"}]},
                        "finish_reason": "STOP",
                        "safety_ratings": [{"category": "HARM", "probability": "LOW"}],
                    }
                ]
            }
        )
        cand = out["candidates"][0]
        assert "finishReason" in cand
        assert "safetyRatings" in cand
        assert cand["content"]["parts"][0]["text"] == "hi"

    def test_recurses_into_lists_of_dicts(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys(
            {
                "grounding_chunks": [
                    {"web": {"uri": "https://example.invalid", "title": "Example"}},
                    {"web": {"uri": "https://other.invalid", "title": "Other"}},
                ]
            }
        )
        assert "groundingChunks" in out
        assert len(out["groundingChunks"]) == 2

    def test_handles_part_with_inline_data(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"inline_data": {"mime_type": "image/png", "data": "b64..."}}]
                        }
                    }
                ]
            }
        )
        part = out["candidates"][0]["content"]["parts"][0]
        assert "inlineData" in part
        assert part["inlineData"]["mimeType"] == "image/png"

    def test_handles_function_call(self):
        from core.transport.normalize import _translate_keys

        out = _translate_keys(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"function_call": {"name": "lookup", "args": {"query": "weather"}}}
                            ]
                        }
                    }
                ]
            }
        )
        part = out["candidates"][0]["content"]["parts"][0]
        assert "functionCall" in part
        assert part["functionCall"]["name"] == "lookup"

    def test_returns_non_dict_values_unchanged(self):
        """_translate_keys is dict-only; primitives passed in (via recursion
        into list elements) come back identical."""
        from core.transport.normalize import _translate_keys

        out = _translate_keys({"items": [1, 2, "three", None, True]})
        assert out["items"] == [1, 2, "three", None, True]


class TestSdkResponseToRestEnvelope:
    """The public entrypoint must accept a pydantic-like SDK response (anything
    with model_dump) and return a translated GeminiResponse dict."""

    def test_calls_model_dump_with_exclude_none(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {"candidates": []}
        sdk_response_to_rest_envelope(sdk_obj)

        sdk_obj.model_dump.assert_called_once_with(exclude_none=True)

    def test_returns_translated_envelope_for_text_response(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "hello"}]},
                    "finish_reason": "STOP",
                }
            ],
            "usage_metadata": {
                "prompt_token_count": 3,
                "candidates_token_count": 2,
                "total_token_count": 5,
            },
        }

        envelope = sdk_response_to_rest_envelope(sdk_obj)

        assert envelope["candidates"][0]["finishReason"] == "STOP"
        assert envelope["candidates"][0]["content"]["parts"][0]["text"] == "hello"
        assert envelope["usageMetadata"]["totalTokenCount"] == 5
        assert envelope["usageMetadata"]["promptTokenCount"] == 3

    def test_returns_translated_envelope_for_inline_image_response(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"inline_data": {"mime_type": "image/png", "data": "b64data"}}],
                    },
                    "finish_reason": "STOP",
                }
            ]
        }

        envelope = sdk_response_to_rest_envelope(sdk_obj)
        part = envelope["candidates"][0]["content"]["parts"][0]
        assert part["inlineData"]["mimeType"] == "image/png"
        assert part["inlineData"]["data"] == "b64data"

    def test_returns_translated_envelope_for_grounded_response(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "grounded answer"}]},
                    "grounding_metadata": {
                        "web_search_queries": ["weather today"],
                        "grounding_chunks": [{"web": {"uri": "https://example.invalid"}}],
                        "search_entry_point": {"rendered_content": "<html>...</html>"},
                    },
                }
            ]
        }

        envelope = sdk_response_to_rest_envelope(sdk_obj)
        gm = envelope["candidates"][0]["groundingMetadata"]
        assert gm["webSearchQueries"] == ["weather today"]
        assert gm["groundingChunks"][0]["web"]["uri"] == "https://example.invalid"
        assert gm["searchEntryPoint"]["renderedContent"] == "<html>...</html>"

    def test_returns_translated_envelope_for_prompt_feedback(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {
            "prompt_feedback": {"block_reason": "SAFETY"},
            "candidates": [],
        }

        envelope = sdk_response_to_rest_envelope(sdk_obj)
        assert envelope["promptFeedback"]["blockReason"] == "SAFETY"

    def test_raises_typeerror_on_unrecognised_object(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        with pytest.raises(TypeError, match="Cannot normalize"):
            sdk_response_to_rest_envelope("not an SDK response")

    def test_raises_typeerror_on_object_without_model_dump(self):
        from core.transport.normalize import sdk_response_to_rest_envelope

        class NotPydantic:
            pass

        with pytest.raises(TypeError, match="Cannot normalize"):
            sdk_response_to_rest_envelope(NotPydantic())


class TestSdkStreamChunkToEnvelope:
    """Streaming chunks share the same shape as full responses, so the
    translator is a thin alias — tests pin that contract."""

    def test_translates_chunk_like_full_response(self):
        from core.transport.normalize import sdk_stream_chunk_to_envelope

        sdk_obj = MagicMock()
        sdk_obj.model_dump.return_value = {
            "candidates": [{"content": {"parts": [{"text": "partial"}]}}]
        }

        chunk = sdk_stream_chunk_to_envelope(sdk_obj)
        assert chunk["candidates"][0]["content"]["parts"][0]["text"] == "partial"


class TestSdkFileToMetadata:
    """File upload responses use snake_case in the SDK; translator emits
    the FileMetadata camelCase shape."""

    def test_translates_file_object(self):
        from core.transport.normalize import sdk_file_to_metadata

        sdk_file = MagicMock()
        sdk_file.model_dump.return_value = {
            "name": "files/abc",
            "display_name": "tiny.txt",
            "mime_type": "text/plain",
            "size_bytes": "5",
            "state": "ACTIVE",
            "uri": "https://generativelanguage.googleapis.com/v1beta/files/abc",
            "create_time": "2026-01-01T00:00:00Z",
            "update_time": "2026-01-02T00:00:00Z",
            "expiration_time": "2026-01-03T00:00:00Z",
            "sha256_hash": "deadbeef",
        }

        meta = sdk_file_to_metadata(sdk_file)
        assert meta["name"] == "files/abc"
        assert meta["displayName"] == "tiny.txt"
        assert meta["mimeType"] == "text/plain"
        assert meta["sizeBytes"] == "5"
        assert meta["state"] == "ACTIVE"
        assert meta["createTime"] == "2026-01-01T00:00:00Z"
        assert meta["updateTime"] == "2026-01-02T00:00:00Z"
        assert meta["expirationTime"] == "2026-01-03T00:00:00Z"
        assert meta["sha256Hash"] == "deadbeef"

    def test_raises_typeerror_on_object_without_model_dump(self):
        from core.transport.normalize import sdk_file_to_metadata

        with pytest.raises(TypeError, match="Cannot normalize"):
            sdk_file_to_metadata("not a file object")


class TestValidateEnvelope:
    """The runtime validator is opt-in via the GEMINI_DEBUG_VALIDATE_ENVELOPE
    env var; it accepts anything dict-shaped and raises on obviously-wrong
    structures (used in CI to catch SDK shape drift)."""

    def test_accepts_minimal_envelope(self):
        from core.transport.normalize import _validate_envelope

        envelope = {"candidates": []}
        # Should not raise.
        _validate_envelope(envelope)

    def test_accepts_full_envelope(self):
        from core.transport.normalize import _validate_envelope

        envelope = {
            "candidates": [{"content": {"parts": [{"text": "hi"}]}}],
            "usageMetadata": {"totalTokenCount": 5},
            "promptFeedback": {"blockReason": ""},
        }
        _validate_envelope(envelope)

    def test_rejects_non_dict(self):
        from core.transport.normalize import _validate_envelope

        with pytest.raises(TypeError, match="dict"):
            _validate_envelope([1, 2, 3])  # type: ignore[arg-type]

    def test_rejects_non_list_candidates(self):
        from core.transport.normalize import _validate_envelope

        with pytest.raises(TypeError, match="candidates"):
            _validate_envelope({"candidates": "not-a-list"})  # type: ignore[arg-type]
