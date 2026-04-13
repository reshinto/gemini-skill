"""Parity tests — SDK and raw HTTP backends must produce identical envelopes.

This is the Phase 2 exit gate. The whole point of the dual-backend refactor
is that adapters can route through either transport without noticing; that
guarantee only holds if both backends emit **byte-identical** normalized
``GeminiResponse`` dicts for the same logical operation.

The tests here pin that contract end-to-end for every endpoint shape the
dispatch matrix supports:

- ``generateContent`` in every flavor the skill's adapters exercise: text,
  multimodal, function_call, code_execution, grounding, safety block, usage
  metadata.
- ``countTokens``, ``embedContent``, ``generate_videos`` (predictLongRunning).
- ``files`` list / get / delete.
- ``cachedContents`` get / delete.
- ``batchJobs`` get.
- ``operations`` get.
- ``upload_file`` metadata.
- ``stream_generate_content`` chunk equivalence.

Test strategy — single source of truth per scenario:

1. Author the **SDK-shape** (snake_case) payload once per scenario. This is
   what a real google-genai pydantic response would emit from ``model_dump``.
2. Derive the **REST-shape** (camelCase) expected dict by running the payload
   through ``core.transport.normalize._translate_keys`` — the same function
   the SDK transport uses. This guarantees the expectation always matches
   whatever the translator produces for the current ``_SNAKE_TO_CAMEL``
   table, so adding a new field is a one-place update.
3. Mock the raw HTTP transport to return the derived camelCase dict (raw
   HTTP already speaks REST, so no translation is needed).
4. Mock the SDK transport to return a pydantic-shaped object wrapping the
   snake_case payload.
5. Invoke both backends with the same endpoint and body.
6. Assert ``DeepDiff(raw_result, sdk_result, ignore_order=True)`` is empty —
   the two envelopes must be structurally identical. Dict key ordering is
   ignored because Python dicts preserve insertion order but different
   code paths can insert keys in different orders and that is not a
   contract violation.

Why DeepDiff instead of ``==``? Plain equality catches value drift but
produces an unreadable diff when it fails (``{a: 1, b: 2} != {a: 1, b: 3}``
gives no hint which key differs on nested dicts). DeepDiff prints the exact
path and old/new value, which is what a reviewer needs when a parity test
fails in CI months from now.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from deepdiff import DeepDiff  # type: ignore[import-untyped]

from core.transport.normalize import _translate_keys


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_sdk_obj(payload: dict[str, Any]) -> mock.Mock:
    """Wrap a snake_case payload as a pydantic-shaped SDK response mock.

    The normalize layer only cares that the object exposes a callable
    ``model_dump`` returning the snake_case dict — that's the contract
    pydantic models satisfy. A Mock with ``model_dump.return_value``
    wired up is the cheapest possible stand-in for a real SDK response.
    """
    fake = mock.Mock()
    fake.model_dump.return_value = payload
    return fake


def _derive_camel(snake_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the camelCase envelope the SDK normalizer would produce.

    Running the snake_case payload through ``_translate_keys`` is the
    authoritative definition of the REST envelope shape — any divergence
    between this and what the SDK transport emits would be a bug in
    ``sdk_response_to_rest_envelope``, which is what the parity tests
    exist to catch.
    """
    return cast(dict[str, Any], _translate_keys(snake_payload))


def _assert_parity(raw_result: object, sdk_result: object) -> None:
    """Assert two backend responses are structurally identical.

    Uses DeepDiff with ``ignore_order=True`` so dict key insertion-order
    differences (a non-contract) don't fail the test. List element order
    is also ignored — the Gemini API never guarantees list ordering on
    its own, and test fixtures that happen to share ordering would be a
    brittle assertion.
    """
    diff = DeepDiff(raw_result, sdk_result, ignore_order=True)
    assert not diff, f"Backend response divergence:\n{diff.pretty()}"


@pytest.fixture
def fake_client() -> mock.Mock:
    """A Mock google.genai.Client with the namespaces the dispatch touches."""
    client = mock.Mock(name="genai.Client")
    client.models = mock.Mock(name="client.models")
    client.files = mock.Mock(name="client.files")
    client.caches = mock.Mock(name="client.caches")
    client.batches = mock.Mock(name="client.batches")
    client.operations = mock.Mock(name="client.operations")
    return client


@pytest.fixture
def patched_sdk_client(fake_client: mock.Mock) -> Iterator[mock.Mock]:
    """Replace ``get_client`` at the SDK transport's import site."""
    with mock.patch("core.transport.sdk.transport.get_client", return_value=fake_client):
        yield fake_client


@pytest.fixture(autouse=True)
def _reset_client_factory() -> Iterator[None]:
    """Drop the ``client_factory.get_client`` lru_cache between tests."""
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


# ---------------------------------------------------------------------------
# generateContent family
# ---------------------------------------------------------------------------


class TestGenerateContentParity:
    """Both backends must emit identical envelopes for ``generateContent``.

    The SDK transport flows the SDK response through
    ``sdk_response_to_rest_envelope``, which walks the snake_case dict and
    renames every key in ``_SNAKE_TO_CAMEL``. The raw HTTP transport hands
    the already-camelCase REST response back untouched. For the same
    upstream data, the two must meet in the middle.
    """

    def test_text_response_with_usage_metadata(self, patched_sdk_client: mock.Mock) -> None:
        """Plain text generation — most common case; text + token counts."""
        snake = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Hello, world!"}],
                    },
                    "finish_reason": "STOP",
                    "safety_ratings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "probability": "NEGLIGIBLE"}
                    ],
                }
            ],
            "usage_metadata": {
                "prompt_token_count": 5,
                "candidates_token_count": 3,
                "total_token_count": 8,
            },
        }
        camel = _derive_camel(snake)

        # Raw HTTP path: mock the underlying urllib client to return the
        # REST-shaped (camelCase) response the real Gemini API sends back.
        from core.transport.raw_http.transport import RawHttpTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        # SDK path: mock the SDK client to return a pydantic-shaped object
        # wrapping the snake_case payload. The SDK transport normalizes.
        from core.transport.sdk.transport import SdkTransport

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_multimodal_response_with_inline_data(
        self, patched_sdk_client: mock.Mock
    ) -> None:
        """Multimodal — parts carry inline_data with a mime_type."""
        snake = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "Here is the image you asked for:"},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAA=",
                                }
                            },
                        ],
                    },
                    "finish_reason": "STOP",
                }
            ],
            "usage_metadata": {"total_token_count": 42},
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_function_call_response(self, patched_sdk_client: mock.Mock) -> None:
        """function_call in parts — used by function_calling adapter."""
        snake = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "function_call": {
                                    "name": "get_weather",
                                    "args": {"city": "Tokyo"},
                                }
                            }
                        ],
                    },
                    "finish_reason": "STOP",
                }
            ],
            "usage_metadata": {
                "prompt_token_count": 12,
                "candidates_token_count": 8,
                "total_token_count": 20,
            },
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_code_execution_response(self, patched_sdk_client: mock.Mock) -> None:
        """executable_code + code_execution_result parts — code_exec adapter."""
        snake = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "executable_code": {
                                    "language": "PYTHON",
                                    "code": "print(2 + 2)",
                                }
                            },
                            {
                                "code_execution_result": {
                                    "outcome": "OUTCOME_OK",
                                    "output": "4\n",
                                }
                            },
                            {"text": "The answer is 4."},
                        ],
                    },
                    "finish_reason": "STOP",
                }
            ]
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_grounding_metadata_response(self, patched_sdk_client: mock.Mock) -> None:
        """grounding_metadata with web_search_queries — search adapter."""
        snake = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "According to the search results..."}],
                    },
                    "grounding_metadata": {
                        "web_search_queries": ["current weather Tokyo"],
                        "grounding_chunks": [
                            {
                                "web": {
                                    "uri": "https://example.com/weather",
                                    "title": "Weather",
                                }
                            }
                        ],
                        "search_entry_point": {
                            "rendered_content": "<div>Search suggestions</div>",
                        },
                    },
                    "finish_reason": "STOP",
                }
            ]
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_safety_block_response(self, patched_sdk_client: mock.Mock) -> None:
        """prompt_feedback with block_reason — safety filter engaged."""
        snake = {
            "prompt_feedback": {
                "block_reason": "SAFETY",
                "safety_ratings": [
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "probability": "HIGH",
                    }
                ],
            }
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


# ---------------------------------------------------------------------------
# Auxiliary generate-family endpoints
# ---------------------------------------------------------------------------


class TestCountTokensParity:
    def test_count_tokens_total_tokens_key(self, patched_sdk_client: mock.Mock) -> None:
        """The SDK emits top-level ``total_tokens`` (not ``total_token_count``).

        Both backends must surface this as ``totalTokens`` so adapters
        reading ``response["totalTokens"]`` work under either backend.
        Pin the mapping table entry that makes this true.
        """
        snake = {"total_tokens": 17}
        camel = _derive_camel(snake)
        assert camel == {"totalTokens": 17}

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:countTokens",
                body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.count_tokens.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:countTokens",
            body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_count_tokens_envelope(self, patched_sdk_client: mock.Mock) -> None:
        snake = {
            "total_token_count": 42,
            "cached_content_token_count": 0,
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/gemini-2.5-flash:countTokens",
                body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.count_tokens.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/gemini-2.5-flash:countTokens",
            body={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


class TestPredictLongRunningParity:
    def test_generate_videos_envelope(self, patched_sdk_client: mock.Mock) -> None:
        """Veo video-gen returns a long-running Operation on both backends."""
        snake = {
            "name": "operations/video-xyz",
            "done": False,
            "metadata": {"state": "RUNNING"},
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        body = {"instances": [{"prompt": "a cat playing piano"}]}
        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/veo-2.0-generate-001:predictLongRunning",
                body=body,
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.generate_videos.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/veo-2.0-generate-001:predictLongRunning",
            body=body,
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


class TestEmbedContentParity:
    def test_embed_content_envelope(self, patched_sdk_client: mock.Mock) -> None:
        snake = {
            "embedding": {"values": [0.1, 0.2, 0.3]},
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="models/embedding-001:embedContent",
                body={"content": {"parts": [{"text": "hi"}]}},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.models.embed_content.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="models/embedding-001:embedContent",
            body={"content": {"parts": [{"text": "hi"}]}},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


# ---------------------------------------------------------------------------
# Files / caches / batches / operations
# ---------------------------------------------------------------------------


class TestFilesParity:
    def test_files_get_single(self, patched_sdk_client: mock.Mock) -> None:
        """Fetching a single file returns a FileMetadata shape — same both sides."""
        snake = {
            "name": "files/abc123",
            "display_name": "upload.pdf",
            "mime_type": "application/pdf",
            "size_bytes": "1024",
            "state": "ACTIVE",
            "uri": "https://files.googleapis.com/v1beta/files/abc123",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T00:00:00Z",
            "sha256_hash": "deadbeef",
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="files/abc123",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.files.get.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="files/abc123",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_files_list_collection(self, patched_sdk_client: mock.Mock) -> None:
        """List endpoint wraps items in ``{files: [...]}`` on both backends."""
        snake_items = [
            {
                "name": "files/a",
                "display_name": "one.pdf",
                "mime_type": "application/pdf",
                "size_bytes": "100",
                "state": "ACTIVE",
                "uri": "https://files/a",
            },
            {
                "name": "files/b",
                "display_name": "two.pdf",
                "mime_type": "application/pdf",
                "size_bytes": "200",
                "state": "ACTIVE",
                "uri": "https://files/b",
            },
        ]
        # Raw HTTP shape: camelCase list wrapped in {files: [...]}.
        camel = {"files": [_derive_camel(item) for item in snake_items]}

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="files",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        # SDK shape: client.files.list() yields an iterable of pydantic objects.
        patched_sdk_client.files.list.return_value = [_make_sdk_obj(i) for i in snake_items]
        sdk_result = SdkTransport().api_call(
            endpoint="files",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_files_delete_empty_envelope(self, patched_sdk_client: mock.Mock) -> None:
        """DELETE returns an empty envelope ``{}`` on both backends."""
        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value={}
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="files/abc123",
                body=None,
                method="DELETE",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.files.delete.return_value = None
        sdk_result = SdkTransport().api_call(
            endpoint="files/abc123",
            body=None,
            method="DELETE",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)
        patched_sdk_client.files.delete.assert_called_once_with(name="files/abc123")


class TestCachesParity:
    def test_caches_create(self, patched_sdk_client: mock.Mock) -> None:
        """Create cache — POST collection. Both backends return the created metadata."""
        snake = {
            "name": "cachedContents/new",
            "display_name": "created",
            "model": "models/gemini-2.5-flash",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T00:00:00Z",
            "expiration_time": "2026-04-14T00:00:00Z",
        }
        camel = _derive_camel(snake)
        body = {
            "model": "models/gemini-2.5-flash",
            "displayName": "created",
            "contents": [{"role": "user", "parts": [{"text": "cached prompt"}]}],
        }

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="cachedContents",
                body=body,
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.caches.create.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="cachedContents",
            body=body,
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_caches_list(self, patched_sdk_client: mock.Mock) -> None:
        """List caches — both backends wrap items in ``{cachedContents: [...]}``."""
        snake_items = [
            {
                "name": "cachedContents/a",
                "display_name": "one",
                "model": "models/gemini-2.5-flash",
            },
            {
                "name": "cachedContents/b",
                "display_name": "two",
                "model": "models/gemini-2.5-flash",
            },
        ]
        camel = {"cachedContents": [_derive_camel(i) for i in snake_items]}

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="cachedContents",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.caches.list.return_value = [
            _make_sdk_obj(i) for i in snake_items
        ]
        sdk_result = SdkTransport().api_call(
            endpoint="cachedContents",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)
    def test_caches_get_single(self, patched_sdk_client: mock.Mock) -> None:
        snake = {
            "name": "cachedContents/abc",
            "display_name": "my cache",
            "model": "models/gemini-2.5-flash",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T00:00:00Z",
            "expiration_time": "2026-04-14T00:00:00Z",
            "usage_metadata": {"total_token_count": 500},
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="cachedContents/abc",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.caches.get.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="cachedContents/abc",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


class TestBatchesParity:
    def test_batches_create(self, patched_sdk_client: mock.Mock) -> None:
        """Create batch job — POST collection. Returns the created Job metadata."""
        snake = {
            "name": "batchJobs/new",
            "display_name": "nightly batch",
            "state": "BATCH_STATE_PENDING",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T00:00:00Z",
        }
        camel = _derive_camel(snake)
        body = {"model": "models/gemini-2.5-flash", "src": "inline_requests"}

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="batchJobs",
                body=body,
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.batches.create.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="batchJobs",
            body=body,
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_batches_list(self, patched_sdk_client: mock.Mock) -> None:
        """List batch jobs — both backends wrap items in ``{batchJobs: [...]}``."""
        snake_items = [
            {
                "name": "batchJobs/a",
                "display_name": "first",
                "state": "BATCH_STATE_SUCCEEDED",
            },
            {
                "name": "batchJobs/b",
                "display_name": "second",
                "state": "BATCH_STATE_RUNNING",
            },
        ]
        camel = {"batchJobs": [_derive_camel(i) for i in snake_items]}

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="batchJobs",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.batches.list.return_value = [
            _make_sdk_obj(i) for i in snake_items
        ]
        sdk_result = SdkTransport().api_call(
            endpoint="batchJobs",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)

    def test_batches_cancel_empty_envelope(
        self, patched_sdk_client: mock.Mock
    ) -> None:
        """``batchJobs/{name}:cancel`` returns empty ``{}`` on both backends."""
        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value={}
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="batchJobs/xyz:cancel",
                body=None,
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.batches.cancel.return_value = None
        sdk_result = SdkTransport().api_call(
            endpoint="batchJobs/xyz:cancel",
            body=None,
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)
        patched_sdk_client.batches.cancel.assert_called_once_with(name="batchJobs/xyz")

    def test_batches_get_single(self, patched_sdk_client: mock.Mock) -> None:
        snake = {
            "name": "batchJobs/xyz",
            "display_name": "nightly batch",
            "state": "BATCH_STATE_SUCCEEDED",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T01:00:00Z",
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="batchJobs/xyz",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.batches.get.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="batchJobs/xyz",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


class TestOperationsParity:
    def test_operations_get(self, patched_sdk_client: mock.Mock) -> None:
        """Long-running operation poll — used by video_gen + file_search."""
        snake = {
            "name": "operations/abc",
            "done": True,
            "metadata": {"progress_percent": 100},
        }
        camel = _derive_camel(snake)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_api_call", return_value=camel
        ):
            raw_result = RawHttpTransport().api_call(
                endpoint="operations/abc",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

        patched_sdk_client.operations.get.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().api_call(
            endpoint="operations/abc",
            body=None,
            method="GET",
            api_version="v1beta",
            timeout=30,
        )

        _assert_parity(raw_result, sdk_result)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class TestStreamParity:
    def test_stream_chunks_byte_identical(self, patched_sdk_client: mock.Mock) -> None:
        """Each streaming chunk must match byte-for-byte across backends."""
        snake_chunks: list[dict[str, Any]] = [
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Hello"}],
                        },
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": ", world!"}],
                        },
                        "finish_reason": "STOP",
                    }
                ],
                "usage_metadata": {
                    "prompt_token_count": 3,
                    "candidates_token_count": 4,
                    "total_token_count": 7,
                },
            },
        ]
        camel_chunks = [_derive_camel(c) for c in snake_chunks]

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        # Raw HTTP path — client.stream_generate_content already yields REST dicts.
        def _raw_gen(*_a: object, **_kw: object) -> Iterator[dict[str, Any]]:
            yield from camel_chunks

        with mock.patch(
            "core.transport.raw_http.transport._client_stream_generate_content",
            side_effect=_raw_gen,
        ):
            raw_chunks = list(
                RawHttpTransport().stream_generate_content(
                    model="gemini-2.5-flash",
                    body={"contents": []},
                    api_version="v1beta",
                    timeout=30,
                )
            )

        # SDK path — client.models.generate_content_stream yields pydantic objects.
        patched_sdk_client.models.generate_content_stream.return_value = iter(
            [_make_sdk_obj(c) for c in snake_chunks]
        )
        sdk_chunks = list(
            SdkTransport().stream_generate_content(
                model="gemini-2.5-flash",
                body={"contents": []},
                api_version="v1beta",
                timeout=30,
            )
        )

        assert len(raw_chunks) == len(sdk_chunks) == len(camel_chunks)
        for raw_chunk, sdk_chunk in zip(raw_chunks, sdk_chunks):
            _assert_parity(raw_chunk, sdk_chunk)


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


class TestUploadFileParity:
    def test_upload_file_metadata(
        self, patched_sdk_client: mock.Mock, tmp_path: Path
    ) -> None:
        """File upload metadata must match across backends.

        Both transports ultimately return a ``FileMetadata`` shape — raw HTTP
        decodes the JSON response from the multipart upload endpoint, SDK
        translates the pydantic ``File`` through ``sdk_file_to_metadata``.
        """
        snake = {
            "name": "files/newfile",
            "display_name": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": "42",
            "state": "ACTIVE",
            "uri": "https://files/newfile",
            "sha256_hash": "abc123",
            "create_time": "2026-04-13T00:00:00Z",
            "update_time": "2026-04-13T00:00:00Z",
        }
        camel = _derive_camel(snake)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n" + b"x" * 32)

        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.raw_http.transport._client_upload_file", return_value=camel
        ):
            raw_result = RawHttpTransport().upload_file(
                file_path=test_file,
                mime_type="application/pdf",
                display_name="test.pdf",
                timeout=120,
            )

        patched_sdk_client.files.upload.return_value = _make_sdk_obj(snake)
        sdk_result = SdkTransport().upload_file(
            file_path=test_file,
            mime_type="application/pdf",
            display_name="test.pdf",
            timeout=120,
        )

        _assert_parity(raw_result, sdk_result)
