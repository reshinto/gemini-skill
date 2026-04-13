"""Tests for core/transport/__init__.py — the public facade.

The facade is the thin wrapper that adapters and the legacy
``core/infra/client.py`` shim call through. It owns the
process-wide TransportCoordinator singleton and exposes three
sync methods (api_call, stream_generate_content, upload_file)
whose signatures match the legacy raw HTTP client byte-for-byte
so the 19 existing adapters require ZERO edits.

The facade NEVER passes a capability through to the coordinator —
the coordinator's capability gate is reserved for a future Phase 3.5
dispatch-layer migration. Today every adapter call uses the
"primary always runs first, fallback on eligible error" path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest import mock

import pytest
from core.types import JSONObject

# NOTE: Singleton reset is handled by the autouse fixture in
# tests/transport/conftest.py — do not duplicate here.


class TestSingleton:
    def test_get_coordinator_returns_same_instance(self) -> None:
        import core.transport as facade

        c1 = facade.get_coordinator()
        c2 = facade.get_coordinator()
        assert c1 is c2

    def test_reset_coordinator_drops_singleton(self) -> None:
        import core.transport as facade

        c1 = facade.get_coordinator()
        facade.reset_coordinator()
        c2 = facade.get_coordinator()
        assert c1 is not c2


class TestPublicSurface:
    def test_exports_legacy_three_functions(self) -> None:
        import core.transport as facade

        assert callable(facade.api_call)
        assert callable(facade.stream_generate_content)
        assert callable(facade.upload_file)

    def test_exports_reset_and_get_coordinator(self) -> None:
        import core.transport as facade

        assert callable(facade.get_coordinator)
        assert callable(facade.reset_coordinator)


class TestApiCallDelegation:
    """``api_call`` must delegate to the coordinator with the matching kwargs."""

    def test_forwards_kwargs_and_returns_result(self) -> None:
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_api_call.return_value = {"candidates": [{"text": "ok"}]}
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            result = facade.api_call(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )
        assert result == {"candidates": [{"text": "ok"}]}
        fake_coord.execute_api_call.assert_called_once_with(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability=None,
        )

    def test_legacy_default_args_match_raw_http_client_defaults(self) -> None:
        """The 19 existing adapters call api_call with positional and
        keyword args. The defaults must exactly match
        ``core/transport/raw_http/client.py::api_call`` so nothing breaks."""
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_api_call.return_value = {"candidates": []}
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            facade.api_call("models/gemini:generateContent")

        call = fake_coord.execute_api_call.call_args
        assert call.kwargs["body"] is None
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["api_version"] == "v1beta"
        assert call.kwargs["timeout"] == 30


class TestFacadeHasNoApiKeyParam:
    """The public facade's ``api_call`` does NOT accept an ``api_key`` kwarg.

    The legacy ``api_key=`` bypass lives on ``core.infra.client.api_call``
    (the shim), not here, because explicit-key auth is a raw-HTTP-only
    concept. Pin this so a future refactor that re-introduces the kwarg on
    the facade trips a visible test failure rather than silently coupling
    the backend-agnostic facade to one backend's auth model.
    """

    def test_api_call_rejects_api_key_kwarg(self) -> None:
        import core.transport as facade

        with pytest.raises(TypeError, match="api_key"):
            facade.api_call(  # type: ignore[call-arg]
                endpoint="models/gemini:generateContent",
                api_key="should-be-rejected",
            )


class TestStreamDelegation:
    def test_yields_through_to_coordinator(self) -> None:
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_stream.return_value = iter([{"chunk": 1}, {"chunk": 2}])
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            chunks = list(
                facade.stream_generate_content(
                    model="gemini",
                    body={"contents": []},
                    api_version="v1beta",
                    timeout=30,
                )
            )
        assert chunks == [{"chunk": 1}, {"chunk": 2}]
        fake_coord.execute_stream.assert_called_once_with(
            model="gemini",
            body={"contents": []},
            api_version="v1beta",
            timeout=30,
            capability=None,
        )


class TestUploadDelegation:
    def test_forwards_to_coordinator(self, tmp_path: Path) -> None:
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_upload.return_value = {"name": "files/abc"}
        f = tmp_path / "x.bin"
        f.write_bytes(b"hi")
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            result = facade.upload_file(
                file_path=f,
                mime_type="application/octet-stream",
                display_name="x",
                timeout=120,
            )
        assert result == {"name": "files/abc"}
        fake_coord.execute_upload.assert_called_once_with(
            file_path=f,
            mime_type="application/octet-stream",
            display_name="x",
            timeout=120,
            capability=None,
        )


class TestAsyncFacade:
    """Async facade mirrors — ``async_api_call`` / ``async_stream_generate_content``
    / ``async_upload_file`` forward to the coordinator's async methods the
    same way the sync facade forwards to the sync methods.
    """

    def test_exports_three_async_functions(self) -> None:
        import core.transport as facade

        assert callable(facade.async_api_call)
        assert callable(facade.async_stream_generate_content)
        assert callable(facade.async_upload_file)

    @pytest.mark.asyncio
    async def test_async_api_call_forwards_to_coordinator(self) -> None:
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_api_call_async = mock.AsyncMock(
            return_value={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            result = await facade.async_api_call(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )
        assert result["candidates"][0]["content"]["parts"][0]["text"] == "ok"
        fake_coord.execute_api_call_async.assert_awaited_once_with(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability=None,
        )

    @pytest.mark.asyncio
    async def test_async_stream_forwards_to_coordinator(self) -> None:
        import core.transport as facade

        async def _fake_stream(**_: object) -> AsyncIterator[JSONObject]:
            yield {"chunk": 1}
            yield {"chunk": 2}

        fake_coord = mock.Mock()
        fake_coord.execute_stream_async = mock.Mock(side_effect=lambda **kw: _fake_stream(**kw))
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            chunks = [
                c
                async for c in facade.async_stream_generate_content(
                    model="gemini",
                    body={"contents": []},
                    api_version="v1beta",
                    timeout=30,
                )
            ]
        assert chunks == [{"chunk": 1}, {"chunk": 2}]

    @pytest.mark.asyncio
    async def test_async_upload_forwards_to_coordinator(self, tmp_path: Path) -> None:
        import core.transport as facade

        f = tmp_path / "x.bin"
        f.write_bytes(b"hi")
        fake_coord = mock.Mock()
        fake_coord.execute_upload_async = mock.AsyncMock(return_value={"name": "files/abc"})
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            result = await facade.async_upload_file(
                file_path=f,
                mime_type="application/octet-stream",
                display_name=None,
                timeout=120,
            )
        assert result == {"name": "files/abc"}
        fake_coord.execute_upload_async.assert_awaited_once()


class TestBaseUrlReExport:
    """``BASE_URL`` is re-exported because ``core/infra/client.py`` already
    re-exports it and adapter tests have asserted on it for years."""

    def test_base_url_is_re_exported(self) -> None:
        import core.transport as facade
        from core.transport.raw_http.client import BASE_URL

        assert facade.BASE_URL == BASE_URL
