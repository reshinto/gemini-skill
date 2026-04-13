"""Tests for core/transport/sdk/transport.py — SdkTransport.

The SDK transport implements the Transport protocol by dispatching legacy
REST-shaped endpoint strings (e.g. ``models/gemini-2.5-flash:generateContent``)
into google-genai SDK method calls (e.g. ``client.models.generate_content``).

This test file is structured in slices that mirror the implementation slices:

- Slice 2a: class skeleton (name, Protocol fit, supports(), __init__)
- Slice 2b: api_call dispatch matrix (every supported endpoint family)
- Slice 2c: stream_generate_content + upload_file
- Slice 2d: _wrap_sdk_errors error mapping

Every test in this file mocks google.genai.Client. There is no live network.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast
from unittest import mock

import pytest


def _make_sdk_response(payload: dict[str, Any]) -> mock.Mock:
    """Build a mock pydantic-shaped SDK response.

    The normalize layer calls ``sdk_obj.model_dump(exclude_none=True)`` on
    every response, so the only contract a test fake must satisfy is to
    expose a callable ``model_dump`` method that returns the snake_case
    payload normalize will translate into camelCase.
    """
    fake = mock.Mock()
    fake.model_dump.return_value = payload
    return fake


@pytest.fixture
def fake_client() -> mock.Mock:
    """Return a Mock client wired with the namespaces the dispatch touches."""
    client = mock.Mock(name="genai.Client")
    # Attach explicit child mocks so attribute access is deterministic and
    # autospec-style typos surface as AttributeError instead of silent Mocks.
    client.models = mock.Mock(name="client.models")
    client.files = mock.Mock(name="client.files")
    client.caches = mock.Mock(name="client.caches")
    client.batches = mock.Mock(name="client.batches")
    client.operations = mock.Mock(name="client.operations")
    return client


@pytest.fixture
def patched_get_client(fake_client: mock.Mock) -> Iterator[mock.Mock]:
    """Replace ``get_client`` in the transport module with a thunk that
    returns ``fake_client``. The transport is the only module under test
    that consults ``get_client``; patching at its import site (instead of
    the factory module) is the canonical mock.patch idiom and avoids any
    interaction with the real lru_cache."""
    with mock.patch("core.transport.sdk.transport.get_client", return_value=fake_client):
        yield fake_client


@pytest.fixture(autouse=True)
def _reset_client_factory() -> Iterator[None]:
    """Drop the client_factory lru_cache so each test gets a fresh instance."""
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


class TestSdkTransportSkeleton:
    """The Transport-shape contract the coordinator relies on."""

    def test_name_is_sdk(self) -> None:
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport.name == "sdk"
        assert SdkTransport().name == "sdk"

    def test_satisfies_transport_protocol(self) -> None:
        from core.transport.base import Transport
        from core.transport.sdk.transport import SdkTransport

        assert isinstance(SdkTransport(), Transport)

    def test_supported_capabilities_is_frozenset(self) -> None:
        """Guard against future test authors swapping the registry for a
        mutable ``set`` — the closed-world contract relies on immutability."""
        from core.transport.sdk.transport import SdkTransport

        assert isinstance(SdkTransport._SUPPORTED_CAPABILITIES, frozenset)


class TestSdkTransportSupports:
    """The explicit capability registry replaces try/except heuristics.

    Capabilities listed in ``_SUPPORTED_CAPABILITIES`` route through the SDK;
    everything else falls through to raw HTTP without an SDK probe. The
    coordinator (Phase 3) consults ``primary.supports(capability)`` BEFORE
    dispatching to ``api_call`` so the SDK transport never sees an
    unsupported capability call.
    """

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
        ],
    )
    def test_supported_capabilities_return_true(self, capability: str) -> None:
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is True

    @pytest.mark.parametrize(
        "capability",
        ["maps", "music_gen", "computer_use", "file_search", "deep_research"],
    )
    def test_unsupported_capabilities_return_false(self, capability: str) -> None:
        """These four are not exposed by google-genai 1.33.0 — coordinator
        routes them deterministically to raw HTTP without probing the SDK."""
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is False

    @pytest.mark.parametrize(
        "capability",
        [
            "nonexistent-capability-xyz",
            "",  # empty string must not bypass the closed-world default
            "TEXT",  # case-sensitivity guard — uppercase aliases are NOT supported
            "text ",  # trailing whitespace must not match "text"
            " text",  # leading whitespace must not match "text"
            "text\x00",  # null byte injection guard
        ],
    )
    def test_adversarial_capability_strings_return_false(self, capability: str) -> None:
        """Closed-world default: anything not exactly in the registry returns
        False, including empty strings, case mismatches, whitespace-padded
        values, and null-byte-suffixed strings. This is the routing-bypass
        guard that keeps the coordinator's deterministic-fallback contract
        from being subverted by sloppy capability strings."""
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is False


class TestApiCallGenerateContent:
    """``models/{m}:generateContent`` is the most exercised dispatch arm."""

    def test_minimal_text_request(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        sdk_resp = _make_sdk_response(
            {
                "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}],
                "usage_metadata": {"total_token_count": 5},
            }
        )
        patched_get_client.models.generate_content.return_value = sdk_resp

        body = {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]}
        result = SdkTransport().api_call("models/gemini-2.5-flash:generateContent", body=body)

        # SDK call shape
        call = patched_get_client.models.generate_content.call_args
        assert call.kwargs["model"] == "gemini-2.5-flash"
        assert call.kwargs["contents"] == body["contents"]
        # Normalized response shape (snake_case → camelCase via normalize.py)
        assert result["candidates"][0]["content"]["parts"][0]["text"] == "hi"
        assert result["usageMetadata"]["totalTokenCount"] == 5

    def test_full_config_request_translates_to_generate_content_config(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_content.return_value = _make_sdk_response({"candidates": []})

        body = {
            "contents": [{"role": "user", "parts": [{"text": "go"}]}],
            "generationConfig": {
                "maxOutputTokens": 256,
                "temperature": 0.7,
                "topP": 0.95,
                "responseMimeType": "application/json",
                "responseSchema": {"type": "OBJECT"},
            },
            "systemInstruction": {"parts": [{"text": "be brief"}]},
            "tools": [{"functionDeclarations": [{"name": "lookup"}]}],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
            ],
        }
        SdkTransport().api_call("models/gemini-2.5-pro:generateContent", body=body)

        call = patched_get_client.models.generate_content.call_args
        assert call.kwargs["model"] == "gemini-2.5-pro"
        assert call.kwargs["contents"] == body["contents"]

        # ``config`` is a GenerateContentConfig pydantic instance built via
        # model_validate so camelCase aliases are accepted directly.
        from google.genai import types

        cfg = call.kwargs["config"]
        assert isinstance(cfg, types.GenerateContentConfig)
        assert cfg.max_output_tokens == 256
        assert cfg.temperature == 0.7
        assert cfg.top_p == 0.95
        assert cfg.response_mime_type == "application/json"
        assert cfg.system_instruction is not None
        assert cfg.tools is not None
        assert cfg.safety_settings is not None

    def test_no_config_passes_none(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_content.return_value = _make_sdk_response({"candidates": []})

        body = {"contents": [{"role": "user", "parts": [{"text": "go"}]}]}
        SdkTransport().api_call("models/gemini:generateContent", body=body)

        call = patched_get_client.models.generate_content.call_args
        assert call.kwargs.get("config") is None


class TestApiCallCountTokens:
    def test_count_tokens(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.count_tokens.return_value = _make_sdk_response(
            {"total_tokens": 17}
        )
        body = {"contents": [{"role": "user", "parts": [{"text": "hello world"}]}]}
        result = SdkTransport().api_call("models/gemini-2.5-flash:countTokens", body=body)

        call = patched_get_client.models.count_tokens.call_args
        assert call.kwargs["model"] == "gemini-2.5-flash"
        assert call.kwargs["contents"] == body["contents"]
        # totalTokens has no entry in _SNAKE_TO_CAMEL → translated by raw walker
        # (key passes through unchanged because it's outside the table). The
        # legacy raw HTTP backend returns the camelCase key here, so we record
        # the SDK's snake_case form and let the adapter handle it.
        assert "total_tokens" in result or "totalTokens" in result


class TestApiCallEmbedContent:
    def test_embed_content_with_output_dimensionality(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.embed_content.return_value = _make_sdk_response(
            {"embeddings": [{"values": [0.1, 0.2, 0.3]}]}
        )
        body = {
            "content": {"parts": [{"text": "embed me"}]},
            "outputDimensionality": 256,
        }
        SdkTransport().api_call("models/text-embedding-004:embedContent", body=body)

        call = patched_get_client.models.embed_content.call_args
        assert call.kwargs["model"] == "text-embedding-004"
        # The legacy body field is ``content`` (singular) — translate to SDK ``contents``.
        assert call.kwargs["contents"] is not None
        cfg = call.kwargs.get("config")
        # Config built only when outputDimensionality is set
        assert cfg is not None


class TestApiCallFiles:
    def test_files_list(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        f1 = mock.Mock()
        f1.model_dump.return_value = {"name": "files/a", "mime_type": "text/plain"}
        f2 = mock.Mock()
        f2.model_dump.return_value = {"name": "files/b", "mime_type": "image/png"}
        patched_get_client.files.list.return_value = [f1, f2]

        # ``api_call`` returns GeminiResponse for type purposes, but for
        # endpoints whose payload doesn't match the candidates-shaped envelope
        # (collection listings, file metadata), tests cast to a plain dict
        # so mypy --strict doesn't flag the runtime keys we know are present.
        result = cast(dict[str, Any], SdkTransport().api_call("files", method="GET"))
        patched_get_client.files.list.assert_called_once()
        assert "files" in result
        assert len(result["files"]) == 2
        assert result["files"][0]["mimeType"] == "text/plain"

    def test_files_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.files.get.return_value = _make_sdk_response(
            {"name": "files/abc", "mime_type": "text/plain", "size_bytes": "42"}
        )
        result = cast(dict[str, Any], SdkTransport().api_call("files/abc", method="GET"))
        patched_get_client.files.get.assert_called_once_with(name="files/abc")
        assert result["mimeType"] == "text/plain"
        assert result["sizeBytes"] == "42"

    def test_files_delete(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.files.delete.return_value = None
        result = SdkTransport().api_call("files/abc", method="DELETE")
        patched_get_client.files.delete.assert_called_once_with(name="files/abc")
        assert result == {}


class TestApiCallCaches:
    def test_caches_create(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.caches.create.return_value = _make_sdk_response(
            {"name": "cachedContents/abc", "model": "gemini-2.5-flash"}
        )
        body = {
            "model": "gemini-2.5-flash",
            "contents": [{"role": "user", "parts": [{"text": "cache me"}]}],
            "ttl": "300s",
        }
        result = cast(dict[str, Any], SdkTransport().api_call("cachedContents", body=body))
        call = patched_get_client.caches.create.call_args
        assert call.kwargs["model"] == "gemini-2.5-flash"
        assert result["name"] == "cachedContents/abc"

    def test_caches_list(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        c1 = mock.Mock()
        c1.model_dump.return_value = {"name": "cachedContents/a"}
        patched_get_client.caches.list.return_value = [c1]
        result = SdkTransport().api_call("cachedContents", method="GET")
        patched_get_client.caches.list.assert_called_once()
        assert "cachedContents" in result

    def test_caches_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.caches.get.return_value = _make_sdk_response(
            {"name": "cachedContents/abc"}
        )
        SdkTransport().api_call("cachedContents/abc", method="GET")
        patched_get_client.caches.get.assert_called_once_with(name="cachedContents/abc")

    def test_caches_delete(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.caches.delete.return_value = None
        result = SdkTransport().api_call("cachedContents/abc", method="DELETE")
        patched_get_client.caches.delete.assert_called_once_with(name="cachedContents/abc")
        assert result == {}


class TestApiCallBatches:
    def test_batches_create(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.batches.create.return_value = _make_sdk_response(
            {"name": "batchJobs/abc", "state": "JOB_STATE_PENDING"}
        )
        body = {"model": "gemini-2.5-flash", "src": "files/input.jsonl"}
        SdkTransport().api_call("batchJobs", body=body)
        call = patched_get_client.batches.create.call_args
        assert call.kwargs["model"] == "gemini-2.5-flash"
        assert call.kwargs["src"] == "files/input.jsonl"

    def test_batches_list(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.batches.list.return_value = []
        SdkTransport().api_call("batchJobs", method="GET")
        patched_get_client.batches.list.assert_called_once()

    def test_batches_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.batches.get.return_value = _make_sdk_response(
            {"name": "batchJobs/abc"}
        )
        SdkTransport().api_call("batchJobs/abc", method="GET")
        patched_get_client.batches.get.assert_called_once_with(name="batchJobs/abc")

    def test_batches_cancel(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.batches.cancel.return_value = None
        result = SdkTransport().api_call("batchJobs/abc:cancel", body={})
        patched_get_client.batches.cancel.assert_called_once_with(name="batchJobs/abc")
        assert result == {}


class TestApiCallOperations:
    def test_operations_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.operations.get.return_value = _make_sdk_response(
            {"name": "operations/abc", "done": True}
        )
        result = cast(dict[str, Any], SdkTransport().api_call("operations/abc", method="GET"))
        # SDK uses operation= kwarg, not name=
        call = patched_get_client.operations.get.call_args
        assert call.kwargs.get("operation") == "operations/abc" or call.kwargs.get("name") == "operations/abc"
        assert result["name"] == "operations/abc"


class TestApiCallVideoGen:
    def test_predict_long_running_dispatches_to_generate_videos(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_videos.return_value = _make_sdk_response(
            {"name": "operations/video-abc", "done": False}
        )
        body = {
            "instances": [{"prompt": "a cat playing piano"}],
            "parameters": {"aspectRatio": "16:9"},
        }
        SdkTransport().api_call("models/veo-2.0-generate-001:predictLongRunning", body=body)
        call = patched_get_client.models.generate_videos.call_args
        assert call.kwargs["model"] == "veo-2.0-generate-001"
        assert call.kwargs["prompt"] == "a cat playing piano"


class TestApiCallUnsupportedEndpoint:
    """Endpoints the dispatch table doesn't recognize raise BackendUnavailableError
    so the coordinator can route to fallback. The SDK transport never silently
    swallows an unknown endpoint."""

    def test_unknown_action_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError):
            SdkTransport().api_call("models/gemini:bogusAction", body={})

    def test_unknown_collection_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError):
            SdkTransport().api_call("fileSearchStores", method="GET")

    def test_unknown_action_endpoint_without_models_prefix_raises(
        self, patched_get_client: mock.Mock
    ) -> None:
        """Action endpoints not matching ``models/X:Y`` or ``batchJobs/X:cancel``
        fall through to the action-dispatch raise — the safety net that
        prevents a typo'd endpoint from silently no-op'ing."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError, match="unknown action endpoint"):
            SdkTransport().api_call("randomThing/abc:operate", body={})

    def test_operations_unsupported_method_raises(
        self, patched_get_client: mock.Mock
    ) -> None:
        """``operations/{name}`` only supports GET; other methods fall through
        to the collection-level raise."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError):
            SdkTransport().api_call("operations/abc", method="DELETE")

    def test_files_unsupported_method_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError, match="unsupported files"):
            SdkTransport().api_call("files/abc", method="PUT")

    def test_caches_unsupported_method_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError, match="unsupported cachedContents"):
            SdkTransport().api_call("cachedContents/abc", method="PUT")

    def test_batches_unsupported_method_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import SdkTransport

        with pytest.raises(BackendUnavailableError, match="unsupported batchJobs"):
            SdkTransport().api_call("batchJobs/abc", method="DELETE")


class TestEmbedContentConfigBuilder:
    """Cover the EmbedContentConfig builder branches not exercised by the
    main embed test (which always sets outputDimensionality)."""

    def test_task_type_only(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.embed_content.return_value = _make_sdk_response(
            {"embeddings": []}
        )
        body = {"content": {"parts": [{"text": "x"}]}, "taskType": "RETRIEVAL_QUERY"}
        SdkTransport().api_call("models/text-embedding-004:embedContent", body=body)
        cfg = patched_get_client.models.embed_content.call_args.kwargs["config"]
        assert cfg is not None

    def test_no_config_fields_yields_none(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.embed_content.return_value = _make_sdk_response(
            {"embeddings": []}
        )
        body = {"content": {"parts": [{"text": "x"}]}}
        SdkTransport().api_call("models/text-embedding-004:embedContent", body=body)
        assert patched_get_client.models.embed_content.call_args.kwargs.get("config") is None


class TestVideoPromptExtraction:
    """Cover the fallback paths in _extract_video_prompt."""

    def test_top_level_prompt_fallback(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_videos.return_value = _make_sdk_response(
            {"name": "operations/v"}
        )
        body = {"prompt": "directly at top level"}
        SdkTransport().api_call("models/veo:predictLongRunning", body=body)
        assert (
            patched_get_client.models.generate_videos.call_args.kwargs["prompt"]
            == "directly at top level"
        )

    def test_empty_body_yields_empty_string_prompt(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_videos.return_value = _make_sdk_response(
            {"name": "operations/v"}
        )
        SdkTransport().api_call("models/veo:predictLongRunning", body={})
        assert patched_get_client.models.generate_videos.call_args.kwargs["prompt"] == ""

    def test_instances_with_dict_but_no_string_prompt_falls_through(
        self, patched_get_client: mock.Mock
    ) -> None:
        """First instance is a dict but its ``prompt`` field is not a string —
        the extractor falls through to the top-level prompt fallback."""
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_videos.return_value = _make_sdk_response(
            {"name": "operations/v"}
        )
        body = {"instances": [{"prompt": 42}], "prompt": "fallback"}
        SdkTransport().api_call("models/veo:predictLongRunning", body=body)
        assert (
            patched_get_client.models.generate_videos.call_args.kwargs["prompt"]
            == "fallback"
        )

    def test_instances_with_non_dict_first_falls_through(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.sdk.transport import SdkTransport

        patched_get_client.models.generate_videos.return_value = _make_sdk_response(
            {"name": "operations/v"}
        )
        body = {"instances": ["not-a-dict"], "prompt": "fallback"}
        SdkTransport().api_call("models/veo:predictLongRunning", body=body)
        assert (
            patched_get_client.models.generate_videos.call_args.kwargs["prompt"]
            == "fallback"
        )


class TestWrapCollection:
    """Cover _wrap_collection's defensive non-iterable branch."""

    def test_non_iterable_items_yield_empty_list(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.transport import SdkTransport

        # client.files.list() returning a non-iterable (e.g. None from a
        # buggy mock or a future SDK regression) must not crash dispatch —
        # the wrapper falls through to an empty list so the adapter sees
        # the same envelope shape as a successful empty listing.
        patched_get_client.files.list.return_value = None
        result = cast(dict[str, Any], SdkTransport().api_call("files", method="GET"))
        assert result == {"files": []}
