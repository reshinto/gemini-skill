"""Tests for core/transport/sdk/async_transport.py — SdkAsyncTransport.

Phase 6 lands the async mirror of ``SdkTransport`` — a thin class that
dispatches into the ``client.aio.*`` namespace the google-genai SDK exposes.
The sync transport is already covered by ``test_transport.py``; this file
focuses on the async-specific surface:

1. Class skeleton: ``name == "sdk"``, ``AsyncTransport`` protocol fit,
   capability registry shared with the sync SdkTransport.
2. ``api_call`` dispatch through ``client.aio.models.*`` for the four
   model actions the sync dispatch supports (generateContent, countTokens,
   embedContent, predictLongRunning) plus a representative CRUD path.
3. ``stream_generate_content`` as an async generator over
   ``client.aio.models.generate_content_stream``.
4. ``upload_file`` via ``client.aio.files.upload`` with the same mime/CRLF
   validation ordering as the sync path.
5. Error wrapping through the shared ``_wrap_sdk_errors`` context manager.

All tests mock ``google.genai.Client.aio``; no live network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
from core.types import JSONObject


def _make_sdk_response(payload: JSONObject) -> mock.Mock:
    """Build a mock pydantic-shaped SDK response.

    Same contract as the sync-transport test helper: expose a callable
    ``model_dump`` that returns the snake_case payload normalize() will
    translate into camelCase.
    """
    fake = mock.Mock()
    fake.model_dump.return_value = payload
    return fake


def _async_return(value: object) -> mock.AsyncMock:
    """Return an ``AsyncMock`` whose ``return_value`` is ``value``.

    Short helper because every test needs to wire an ``AsyncMock`` into
    ``client.aio.X.Y`` — a bare ``.return_value = ...`` wouldn't work
    because the outer attribute is a ``Mock``, not an ``AsyncMock``.
    """
    m = mock.AsyncMock()
    m.return_value = value
    return m


@pytest.fixture
def fake_async_client() -> mock.Mock:
    """Return a Mock client with an ``aio`` namespace wired with mocked submodules."""
    client = mock.Mock(name="genai.Client")
    client.aio = mock.Mock(name="client.aio")
    client.aio.models = mock.Mock(name="client.aio.models")
    client.aio.files = mock.Mock(name="client.aio.files")
    client.aio.caches = mock.Mock(name="client.aio.caches")
    client.aio.batches = mock.Mock(name="client.aio.batches")
    client.aio.operations = mock.Mock(name="client.aio.operations")
    return client


@pytest.fixture
def patched_get_client(fake_async_client: mock.Mock) -> Iterator[mock.Mock]:
    """Patch ``get_client`` in the async transport module — the module
    reuses the sync factory because ``client.aio`` is a namespace on the
    singleton client, not a separate object."""
    with mock.patch(
        "core.transport.sdk.async_transport.get_client",
        return_value=fake_async_client,
    ):
        yield fake_async_client


@pytest.fixture(autouse=True)
def _reset_client_factory() -> Iterator[None]:
    """Drop the lru_cache so each test gets a fresh client."""
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


# ---------------------------------------------------------------------------
# Skeleton
# ---------------------------------------------------------------------------


class TestSdkAsyncTransportSkeleton:
    def test_name_is_sdk(self) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        assert SdkAsyncTransport.name == "sdk"
        assert SdkAsyncTransport().name == "sdk"

    def test_satisfies_async_transport_protocol(self) -> None:
        from core.transport.base import AsyncTransport
        from core.transport.sdk.async_transport import SdkAsyncTransport

        assert isinstance(SdkAsyncTransport(), AsyncTransport)

    def test_supports_delegates_to_sync_registry(self) -> None:
        """Async surface mirrors the sync capability registry — any
        capability the sync SdkTransport claims is also available via
        ``client.aio.*``. Reusing the frozenset keeps the two in lockstep
        and means a future pin bump only has to update one place."""
        from core.transport.sdk.async_transport import SdkAsyncTransport
        from core.transport.sdk.transport import SdkTransport

        transport = SdkAsyncTransport()
        for cap in SdkTransport._SUPPORTED_CAPABILITIES:
            assert transport.supports(cap) is True
        assert transport.supports("not_a_capability") is False


# ---------------------------------------------------------------------------
# api_call dispatch
# ---------------------------------------------------------------------------


class TestAsyncApiCallDispatch:
    @pytest.mark.asyncio
    async def test_generate_content_routes_through_aio_models(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.models.generate_content = _async_return(
            _make_sdk_response({"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})
        )
        transport = SdkAsyncTransport()

        result = await transport.api_call(
            endpoint="models/gemini-2.5-flash:generateContent",
            body={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )

        patched_get_client.aio.models.generate_content.assert_awaited_once()
        call_kwargs = patched_get_client.aio.models.generate_content.await_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert result["candidates"][0]["content"]["parts"][0]["text"] == "hi"

    @pytest.mark.asyncio
    async def test_count_tokens(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.models.count_tokens = _async_return(
            _make_sdk_response({"total_tokens": 7})
        )
        transport = SdkAsyncTransport()

        result = cast(
            JSONObject,
            await transport.api_call(
                endpoint="models/gemini-2.5-flash:countTokens",
                body={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
                method="POST",
                api_version="v1beta",
                timeout=30,
            ),
        )

        patched_get_client.aio.models.count_tokens.assert_awaited_once()
        assert result["totalTokens"] == 7

    @pytest.mark.asyncio
    async def test_embed_content(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.models.embed_content = _async_return(
            _make_sdk_response({"embedding": {"values": [0.1, 0.2]}})
        )
        transport = SdkAsyncTransport()

        result = cast(
            JSONObject,
            await transport.api_call(
                endpoint="models/embedding-001:embedContent",
                body={"content": {"parts": [{"text": "hello"}]}},
                method="POST",
                api_version="v1beta",
                timeout=30,
            ),
        )

        patched_get_client.aio.models.embed_content.assert_awaited_once()
        embedding = cast(dict[str, object], result["embedding"])
        assert embedding["values"] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_predict_long_running_video(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.models.generate_videos = _async_return(
            _make_sdk_response({"name": "operations/abc"})
        )
        transport = SdkAsyncTransport()

        result = cast(
            JSONObject,
            await transport.api_call(
                endpoint="models/veo-2.0-generate-001:predictLongRunning",
                body={"instances": [{"prompt": "a dog on the beach"}]},
                method="POST",
                api_version="v1beta",
                timeout=30,
            ),
        )

        patched_get_client.aio.models.generate_videos.assert_awaited_once()
        assert result["name"] == "operations/abc"

    @pytest.mark.asyncio
    async def test_unknown_model_action_raises_backend_unavailable(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        transport = SdkAsyncTransport()
        with pytest.raises(BackendUnavailableError, match="unknown model action"):
            await transport.api_call(
                endpoint="models/gemini:whatever",
                body={},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_files_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.files.get = _async_return(
            _make_sdk_response({"name": "files/abc", "state": "ACTIVE"})
        )
        transport = SdkAsyncTransport()

        result = cast(
            JSONObject,
            await transport.api_call(
                endpoint="files/abc",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            ),
        )

        patched_get_client.aio.files.get.assert_awaited_once_with(name="files/abc")
        assert result["name"] == "files/abc"

    @pytest.mark.asyncio
    async def test_files_delete(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.files.delete = _async_return(None)
        transport = SdkAsyncTransport()

        result = await transport.api_call(
            endpoint="files/abc",
            body=None,
            method="DELETE",
            api_version="v1beta",
            timeout=30,
        )

        patched_get_client.aio.files.delete.assert_awaited_once_with(name="files/abc")
        assert result == {}

    @pytest.mark.asyncio
    async def test_operations_get(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        patched_get_client.aio.operations.get = _async_return(
            _make_sdk_response({"name": "operations/foo", "done": True})
        )
        transport = SdkAsyncTransport()

        result = cast(
            JSONObject,
            await transport.api_call(
                endpoint="operations/foo",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            ),
        )

        patched_get_client.aio.operations.get.assert_awaited_once_with(operation="operations/foo")
        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_unknown_crud_endpoint_raises(self, patched_get_client: mock.Mock) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        transport = SdkAsyncTransport()
        with pytest.raises(BackendUnavailableError, match="unknown"):
            await transport.api_call(
                endpoint="widgets/abc",
                body=None,
                method="GET",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_non_models_action_endpoint_raises(self, patched_get_client: mock.Mock) -> None:
        """Action endpoints outside ``models/*`` aren't supported on the
        async path (batches.cancel has no async twin in 1.33.0). The
        dispatch must raise BackendUnavailableError with a clear message."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        transport = SdkAsyncTransport()
        with pytest.raises(BackendUnavailableError, match="unknown action endpoint"):
            await transport.api_call(
                endpoint="batchJobs/foo:cancel",
                body=None,
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_files_post_falls_through_to_unknown(self, patched_get_client: mock.Mock) -> None:
        """A POST to files without an id isn't in the async dispatch
        table — must raise BackendUnavailableError (sync path routes this
        through multipart upload, not api_call)."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        transport = SdkAsyncTransport()
        with pytest.raises(BackendUnavailableError, match="unknown POST"):
            await transport.api_call(
                endpoint="files",
                body={"name": "x"},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_operations_delete_falls_through(self, patched_get_client: mock.Mock) -> None:
        """Operations DELETE is not supported — falls through to unknown."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        transport = SdkAsyncTransport()
        with pytest.raises(BackendUnavailableError, match="unknown DELETE"):
            await transport.api_call(
                endpoint="operations/foo",
                body=None,
                method="DELETE",
                api_version="v1beta",
                timeout=30,
            )


# ---------------------------------------------------------------------------
# stream_generate_content
# ---------------------------------------------------------------------------


class TestAsyncStream:
    @pytest.mark.asyncio
    async def test_yields_normalized_chunks(self, patched_get_client: mock.Mock) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        chunks = [
            _make_sdk_response({"candidates": [{"content": {"parts": [{"text": "he"}]}}]}),
            _make_sdk_response({"candidates": [{"content": {"parts": [{"text": "llo"}]}}]}),
        ]

        async def fake_stream(**_: object) -> AsyncIterator[mock.Mock]:
            for c in chunks:
                yield c

        patched_get_client.aio.models.generate_content_stream = mock.Mock(
            side_effect=lambda **kw: fake_stream(**kw)
        )
        transport = SdkAsyncTransport()

        collected: list[str] = []
        async for chunk in transport.stream_generate_content(
            model="gemini-2.5-flash",
            body={"contents": [{"role": "user", "parts": [{"text": "say hi"}]}]},
            api_version="v1beta",
            timeout=30,
        ):
            collected.append(chunk["candidates"][0]["content"]["parts"][0]["text"])

        assert collected == ["he", "llo"]

    @pytest.mark.asyncio
    async def test_stream_error_mid_iteration_is_wrapped(
        self, patched_get_client: mock.Mock
    ) -> None:
        from core.infra.errors import APIError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        # Build a fake async iterator that yields one chunk then raises.
        class _ExplodingIter:
            def __init__(self) -> None:
                self._yielded = False

            def __aiter__(self) -> "_ExplodingIter":
                return self

            async def __anext__(self) -> object:
                if not self._yielded:
                    self._yielded = True
                    return _make_sdk_response(
                        {"candidates": [{"content": {"parts": [{"text": "x"}]}}]}
                    )
                from google.genai import errors as genai_errors

                raise genai_errors.ServerError(503, {"error": {"message": "boom"}})

        patched_get_client.aio.models.generate_content_stream = mock.Mock(
            return_value=_ExplodingIter()
        )
        transport = SdkAsyncTransport()

        collected: list[str] = []
        with pytest.raises(APIError):
            async for chunk in transport.stream_generate_content(
                model="gemini-2.5-flash",
                body={"contents": [{"role": "user", "parts": [{"text": "say hi"}]}]},
                api_version="v1beta",
                timeout=30,
            ):
                collected.append(chunk["candidates"][0]["content"]["parts"][0]["text"])
        assert collected == ["x"]


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


class TestAsyncUpload:
    @pytest.mark.asyncio
    async def test_upload_success(self, patched_get_client: mock.Mock, tmp_path: Path) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        src = tmp_path / "doc.txt"
        src.write_text("hello")
        patched_get_client.aio.files.upload = _async_return(
            _make_sdk_response({"name": "files/abc", "mime_type": "text/plain", "state": "ACTIVE"})
        )
        transport = SdkAsyncTransport()

        result = await transport.upload_file(
            file_path=src,
            mime_type="text/plain",
            display_name="doc",
            timeout=120,
        )

        patched_get_client.aio.files.upload.assert_awaited_once()
        assert result["name"] == "files/abc"
        assert result["mimeType"] == "text/plain"

    @pytest.mark.asyncio
    async def test_upload_with_none_display_name(
        self, patched_get_client: mock.Mock, tmp_path: Path
    ) -> None:
        """``display_name=None`` must skip the CR/LF validator entirely —
        the None path is explicit in the boundary check so callers can
        opt out of setting a display name without tripping validation."""
        from core.transport.sdk.async_transport import SdkAsyncTransport

        src = tmp_path / "doc.txt"
        src.write_text("hello")
        patched_get_client.aio.files.upload = _async_return(
            _make_sdk_response({"name": "files/abc", "mime_type": "text/plain"})
        )
        transport = SdkAsyncTransport()

        result = await transport.upload_file(
            file_path=src,
            mime_type="text/plain",
            display_name=None,
            timeout=120,
        )
        assert result["name"] == "files/abc"

    @pytest.mark.asyncio
    async def test_upload_rejects_bad_mime_before_client_call(
        self, patched_get_client: mock.Mock, tmp_path: Path
    ) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        src = tmp_path / "doc.txt"
        src.write_text("hello")
        patched_get_client.aio.files.upload = _async_return(None)
        transport = SdkAsyncTransport()

        with pytest.raises(ValueError):
            await transport.upload_file(
                file_path=src,
                mime_type="text/plain\r\nInjected: yes",
                display_name=None,
                timeout=120,
            )
        patched_get_client.aio.files.upload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_rejects_crlf_display_name(
        self, patched_get_client: mock.Mock, tmp_path: Path
    ) -> None:
        from core.transport.sdk.async_transport import SdkAsyncTransport

        src = tmp_path / "doc.txt"
        src.write_text("hello")
        patched_get_client.aio.files.upload = _async_return(None)
        transport = SdkAsyncTransport()

        with pytest.raises(ValueError):
            await transport.upload_file(
                file_path=src,
                mime_type="text/plain",
                display_name="bad\nname",
                timeout=120,
            )
        patched_get_client.aio.files.upload.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------


class TestAsyncErrorWrapping:
    @pytest.mark.asyncio
    async def test_client_error_401_maps_to_auth_error(self, patched_get_client: mock.Mock) -> None:
        from google.genai import errors as genai_errors

        from core.infra.errors import AuthError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        async def _raise(**_: object) -> None:
            raise genai_errors.ClientError(401, {"error": {"message": "bad key"}})

        patched_get_client.aio.models.generate_content = _raise
        transport = SdkAsyncTransport()

        with pytest.raises(AuthError):
            await transport.api_call(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_server_error_maps_to_api_error(self, patched_get_client: mock.Mock) -> None:
        from google.genai import errors as genai_errors

        from core.infra.errors import APIError
        from core.transport.sdk.async_transport import SdkAsyncTransport

        async def _raise(**_: object) -> None:
            raise genai_errors.ServerError(503, {"error": {"message": "unavail"}})

        patched_get_client.aio.models.generate_content = _raise
        transport = SdkAsyncTransport()

        with pytest.raises(APIError) as excinfo:
            await transport.api_call(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )
        assert excinfo.value.status_code == 503
