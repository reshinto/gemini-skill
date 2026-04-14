"""Tests for core/transport/coordinator.py — TransportCoordinator.

The coordinator is the dual-backend dispatch core. It owns three decisions:

1. **Capability gate** (when a capability name is known): if the primary
   backend's ``supports(capability)`` returns False, route deterministically
   to the fallback. No try/except, no SDK probe, no log noise.
2. **Eligible-failure fallback** (when the primary fails): consult
   ``policy.is_fallback_eligible(exc)``. If True and a fallback exists,
   try the fallback. If False or no fallback, re-raise / wrap as APIError.
3. **Combined-error reporting**: when both backends fail, raise
   ``APIError`` with both backends' messages attached to the structured
   ``primary_error`` / ``fallback_error`` fields so log readers can see
   both at once.

Tests use ``unittest.mock.Mock(spec=Transport)`` so the mock matches the
Protocol shape and any signature drift surfaces as an immediate test
failure rather than a silent attribute lookup.

The test file is structured so each behavior matrix is its own class —
this keeps failures locally scoped and the test names read like a
spec table.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest import mock

import pytest

from core.infra.errors import APIError, AuthError
from core.transport.base import BackendUnavailableError, StreamChunk, Transport


def _make_backend(
    name: str = "primary",
    *,
    supports: bool = True,
    api_call_return: object | None = None,
    api_call_side_effect: object | None = None,
) -> mock.Mock:
    """Build a Mock that satisfies the Transport Protocol shape.

    Using ``spec=Transport`` here gives us auto-generated mock methods
    for every Protocol attribute and rejects accesses to names the
    Protocol does not declare — surfacing typo'd assertions immediately.
    """
    backend = mock.Mock(spec=Transport)
    # ``name`` is a class attribute on real backends, so we set it on the
    # Mock the same way. ``Mock(spec=...)`` does NOT auto-create attributes
    # for non-method members of a Protocol, so we set this explicitly.
    backend.name = name
    backend.supports = mock.Mock(return_value=supports)
    backend.api_call = mock.Mock(
        return_value=(api_call_return if api_call_return is not None else {"candidates": []}),
        side_effect=api_call_side_effect,
    )
    backend.stream_generate_content = mock.Mock(return_value=iter([]))
    backend.upload_file = mock.Mock(return_value={})
    return backend


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestCoordinatorConstruction:
    def test_holds_primary_and_fallback(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)
        assert coord.primary is primary
        assert coord.fallback is fallback

    def test_holds_primary_only_when_no_fallback(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        coord = TransportCoordinator(primary=primary, fallback=None)
        assert coord.primary is primary
        assert coord.fallback is None

    def test_rejects_same_backend_for_primary_and_fallback(self) -> None:
        """If primary == fallback the coordinator's whole point evaporates;
        reject this construction outright instead of silently doing nothing
        on the fallback path."""
        from core.transport.coordinator import TransportCoordinator

        backend = _make_backend("sdk")
        with pytest.raises(ValueError, match="primary and fallback must differ"):
            TransportCoordinator(primary=backend, fallback=backend)


# ---------------------------------------------------------------------------
# Capability gate (slice 3b core)
# ---------------------------------------------------------------------------


class TestCapabilityGate:
    """The supports(capability) gate routes deterministically without
    touching the primary's transport methods. This is the mechanism that
    makes ``maps`` / ``music_gen`` / ``computer_use`` etc. land on raw
    HTTP without an SDK probe."""

    def test_unsupported_capability_routes_to_fallback_without_calling_primary(
        self,
    ) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk", supports=False)
        fallback = _make_backend("raw_http", api_call_return={"candidates": [{"index": 0}]})
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = coord.execute_api_call(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="maps",
        )

        assert result == {"candidates": [{"index": 0}]}
        primary.supports.assert_called_once_with("maps")
        primary.api_call.assert_not_called()
        fallback.api_call.assert_called_once()

    def test_unsupported_capability_with_no_fallback_raises_backend_unavailable(
        self,
    ) -> None:
        """If the primary refuses and there's no fallback, the coordinator
        must NOT silently invoke the primary anyway — that defeats the
        determinism contract."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk", supports=False)
        coord = TransportCoordinator(primary=primary, fallback=None)

        with pytest.raises(BackendUnavailableError, match="maps") as exc_info:
            coord.execute_api_call(
                endpoint="x",
                body={},
                method="POST",
                api_version="v1beta",
                timeout=30,
                capability="maps",
            )
        # Sanity: the primary's transport methods were never touched.
        primary.api_call.assert_not_called()
        assert "sdk" in str(exc_info.value)

    def test_capability_none_skips_gate_and_dispatches_primary(self) -> None:
        """When the legacy facade calls without a capability, the gate is
        skipped — primary runs unconditionally and only error-based
        fallback kicks in. This is the path adapters use today."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk", supports=False, api_call_return={"candidates": [{"text": "hi"}]}
        )
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = coord.execute_api_call(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability=None,
        )

        assert result == {"candidates": [{"text": "hi"}]}
        primary.supports.assert_not_called()
        primary.api_call.assert_called_once()
        fallback.api_call.assert_not_called()

    def test_supported_capability_dispatches_to_primary(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk", supports=True, api_call_return={"candidates": [{"text": "ok"}]}
        )
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = coord.execute_api_call(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="text",
        )

        assert result == {"candidates": [{"text": "ok"}]}
        primary.supports.assert_called_once_with("text")
        primary.api_call.assert_called_once()
        fallback.api_call.assert_not_called()


# ---------------------------------------------------------------------------
# Error-eligibility fallback (the original "primary fails, retry on fallback")
# ---------------------------------------------------------------------------


class TestErrorFallback:
    def test_eligible_error_routes_to_fallback(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk",
            supports=True,
            api_call_side_effect=APIError("upstream 503", status_code=503),
        )
        fallback = _make_backend(
            "raw_http", api_call_return={"candidates": [{"text": "from fallback"}]}
        )
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = coord.execute_api_call(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="text",
        )

        assert result == {"candidates": [{"text": "from fallback"}]}
        primary.api_call.assert_called_once()
        fallback.api_call.assert_called_once()

    def test_non_eligible_error_propagates_immediately(self) -> None:
        """AuthError is in policy._NEVER_FALLBACK — the coordinator must
        re-raise without touching the fallback (a bad key is bad on every
        backend; trying again would just hide the error)."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk",
            supports=True,
            api_call_side_effect=AuthError("bad key"),
        )
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        with pytest.raises(AuthError, match="bad key"):
            coord.execute_api_call(
                endpoint="x",
                body={},
                method="POST",
                api_version="v1beta",
                timeout=30,
                capability="text",
            )
        fallback.api_call.assert_not_called()

    def test_eligible_error_with_no_fallback_wraps_as_combined_apierror(
        self,
    ) -> None:
        """When there's no fallback to try, the eligible error becomes an
        APIError with primary_backend / primary_error context attached so
        log readers can see which backend failed."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk",
            supports=True,
            api_call_side_effect=APIError("upstream 503", status_code=503),
        )
        coord = TransportCoordinator(primary=primary, fallback=None)

        with pytest.raises(APIError) as exc_info:
            coord.execute_api_call(
                endpoint="x",
                body={},
                method="POST",
                api_version="v1beta",
                timeout=30,
                capability="text",
            )

        err = exc_info.value
        assert err.primary_backend == "sdk"
        assert err.fallback_backend is None
        assert "503" in (err.primary_error or "")

    def test_both_backends_fail_raises_combined_apierror(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend(
            "sdk",
            supports=True,
            api_call_side_effect=APIError("sdk timeout", status_code=504),
        )
        fallback = _make_backend(
            "raw_http",
            api_call_side_effect=APIError("raw 503", status_code=503),
        )
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        with pytest.raises(APIError) as exc_info:
            coord.execute_api_call(
                endpoint="x",
                body={},
                method="POST",
                api_version="v1beta",
                timeout=30,
                capability="text",
            )

        err = exc_info.value
        assert err.primary_backend == "sdk"
        assert err.fallback_backend == "raw_http"
        assert "sdk timeout" in (err.primary_error or "")
        assert "raw 503" in (err.fallback_error or "")
        # The structured str() must surface both backend messages.
        text = str(err)
        assert "sdk timeout" in text
        assert "raw 503" in text


# ---------------------------------------------------------------------------
# Stream + upload dispatch (mirror api_call's matrix at a smaller scale)
# ---------------------------------------------------------------------------


class TestStreamDispatch:
    def test_stream_yields_from_primary_on_success(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        chunks = [{"a": 1}, {"a": 2}]
        primary = _make_backend("sdk", supports=True)
        primary.stream_generate_content = mock.Mock(return_value=iter(chunks))
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = list(
            coord.execute_stream(
                model="gemini",
                body={"contents": []},
                api_version="v1beta",
                timeout=30,
                capability="streaming",
            )
        )
        assert result == chunks
        fallback.stream_generate_content.assert_not_called()

    def test_stream_capability_unsupported_routes_to_fallback(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk", supports=False)
        fallback_chunks = [{"b": 1}]
        fallback = _make_backend("raw_http")
        fallback.stream_generate_content = mock.Mock(return_value=iter(fallback_chunks))
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        result = list(
            coord.execute_stream(
                model="gemini",
                body={"contents": []},
                api_version="v1beta",
                timeout=30,
                capability="maps",
            )
        )
        assert result == fallback_chunks
        primary.stream_generate_content.assert_not_called()


class TestUploadDispatch:
    def test_upload_dispatches_to_primary_on_success(self, tmp_path: Path) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk", supports=True)
        primary.upload_file = mock.Mock(return_value={"name": "files/abc"})
        fallback = _make_backend("raw_http")
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        f = tmp_path / "x.bin"
        f.write_bytes(b"hi")
        result = coord.execute_upload(
            file_path=f,
            mime_type="application/octet-stream",
            display_name="x",
            timeout=120,
            capability="files",
        )
        assert result == {"name": "files/abc"}
        fallback.upload_file.assert_not_called()


# ---------------------------------------------------------------------------
# Fallback log
# ---------------------------------------------------------------------------


class TestFallbackLogging:
    def test_eligible_fallback_emits_warning_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Per CR-3 in the canonical plan, every fallback invocation
        emits one structured WARNING line so silent SDK→raw_http
        degradation is visible in production logs."""
        import logging

        from core.transport.coordinator import TransportCoordinator

        caplog.set_level(logging.WARNING, logger="core.transport.coordinator")
        primary = _make_backend(
            "sdk",
            supports=True,
            api_call_side_effect=APIError("upstream 503", status_code=503),
        )
        fallback = _make_backend("raw_http", api_call_return={"candidates": []})
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        coord.execute_api_call(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="text",
        )

        records = [r for r in caplog.records if r.name == "core.transport.coordinator"]
        assert len(records) == 1
        record = records[0]
        assert record.levelno == logging.WARNING
        assert getattr(record, "primary", None) == "sdk"
        assert getattr(record, "fallback", None) == "raw_http"
        assert getattr(record, "capability", None) == "text"

    def test_capability_gate_route_emits_warning_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Deterministic capability-gate routes also log so reviewers
        can grep for which capabilities are silently routing to raw HTTP
        in production — that's the signal to flip them to first-class
        SDK once the SDK adds the surface."""
        import logging

        from core.transport.coordinator import TransportCoordinator

        caplog.set_level(logging.WARNING, logger="core.transport.coordinator")
        primary = _make_backend("sdk", supports=False)
        fallback = _make_backend("raw_http", api_call_return={"candidates": []})
        coord = TransportCoordinator(primary=primary, fallback=fallback)

        coord.execute_api_call(
            endpoint="x",
            body={},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="maps",
        )

        records = [r for r in caplog.records if r.name == "core.transport.coordinator"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert getattr(records[0], "reason", None) == "capability_gate"


# ---------------------------------------------------------------------------
# from_config factory
# ---------------------------------------------------------------------------


def _make_async_backend(
    name: str = "sdk",
    *,
    supports: bool = True,
    api_call_return: object | None = None,
    api_call_side_effect: object | None = None,
    upload_return: object | None = None,
) -> mock.Mock:
    """Build a Mock that satisfies the AsyncTransport Protocol shape.

    ``AsyncMock`` gives coroutine returns for awaited methods.
    ``stream_generate_content`` is a regular Mock that returns an async
    iterator (the async-gen call site returns the iterator synchronously).
    """
    from core.transport.base import AsyncTransport

    backend = mock.Mock(spec=AsyncTransport)
    backend.name = name
    backend.supports = mock.Mock(return_value=supports)
    backend.api_call = mock.AsyncMock(
        return_value=(api_call_return if api_call_return is not None else {"candidates": []}),
        side_effect=api_call_side_effect,
    )

    async def _empty_stream() -> AsyncIterator[StreamChunk]:
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]

    backend.stream_generate_content = mock.Mock(return_value=_empty_stream())
    backend.upload_file = mock.AsyncMock(
        return_value=upload_return if upload_return is not None else {}
    )
    return backend


class TestAsyncDispatch:
    """Phase 6: execute_*_async mirrors the sync dispatch but has no
    fallback partner — raw HTTP is sync-only and the Live API is SDK-only.

    The async coordinator either runs the configured async primary or
    raises BackendUnavailableError when one wasn't configured.
    """

    def test_execute_api_call_async_raises_when_no_async_primary(self) -> None:
        import asyncio

        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        coord = TransportCoordinator(primary=primary, fallback=None)

        with pytest.raises(BackendUnavailableError, match="async"):
            asyncio.run(
                coord.execute_api_call_async(
                    endpoint="x",
                    body=None,
                    method="GET",
                    api_version="v1beta",
                    timeout=30,
                )
            )

    def test_execute_stream_async_raises_when_no_async_primary(self) -> None:
        import asyncio

        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        coord = TransportCoordinator(primary=primary, fallback=None)

        async def drain() -> list[StreamChunk]:
            gen = coord.execute_stream_async(
                model="gemini",
                body={"contents": []},
                api_version="v1beta",
                timeout=30,
            )
            return [chunk async for chunk in gen]

        with pytest.raises(BackendUnavailableError, match="async"):
            asyncio.run(drain())

    def test_execute_upload_async_raises_when_no_async_primary(self, tmp_path: Path) -> None:
        import asyncio

        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        coord = TransportCoordinator(primary=primary, fallback=None)

        with pytest.raises(BackendUnavailableError, match="async"):
            asyncio.run(
                coord.execute_upload_async(
                    file_path=tmp_path / "x.bin",
                    mime_type="application/octet-stream",
                    display_name=None,
                    timeout=120,
                )
            )

    @pytest.mark.asyncio
    async def test_execute_api_call_async_routes_to_async_primary(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend(
            "sdk",
            api_call_return={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        result = await coord.execute_api_call_async(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
        )
        assert result["candidates"][0]["content"]["parts"][0]["text"] == "ok"
        async_primary.api_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_api_call_async_capability_gate_passes(self) -> None:
        """A capability the async primary supports flows through the
        gate silently — the call is awaited and the return is forwarded."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend(
            "sdk",
            supports=True,
            api_call_return={"candidates": []},
        )
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        result = await coord.execute_api_call_async(
            endpoint="models/gemini:generateContent",
            body={"contents": []},
            method="POST",
            api_version="v1beta",
            timeout=30,
            capability="text",
        )
        assert result == {"candidates": []}
        async_primary.api_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_api_call_async_capability_gate_raises(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend("sdk", supports=False)
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        with pytest.raises(BackendUnavailableError, match="maps"):
            await coord.execute_api_call_async(
                endpoint="x",
                body=None,
                method="POST",
                api_version="v1beta",
                timeout=30,
                capability="maps",
            )
        async_primary.api_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_api_call_async_propagates_auth_error(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend("sdk", api_call_side_effect=AuthError("bad key"))
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        with pytest.raises(AuthError):
            await coord.execute_api_call_async(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )

    @pytest.mark.asyncio
    async def test_execute_api_call_async_propagates_api_error_unwrapped(
        self,
    ) -> None:
        """Async path has no fallback so eligible errors propagate as-is.
        The sync path wraps them in an APIError carrying primary context
        because it can cleanly surface a "no fallback configured" message;
        async path's contract is simpler — errors reach the caller
        unchanged and the caller handles retry logic."""
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        err = APIError("503 boom", status_code=503)
        async_primary = _make_async_backend("sdk", api_call_side_effect=err)
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        with pytest.raises(APIError) as excinfo:
            await coord.execute_api_call_async(
                endpoint="models/gemini:generateContent",
                body={"contents": []},
                method="POST",
                api_version="v1beta",
                timeout=30,
            )
        assert excinfo.value.status_code == 503

    @pytest.mark.asyncio
    async def test_execute_stream_async_yields_chunks(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")

        async def _stream() -> AsyncIterator[StreamChunk]:
            yield {"candidates": [{"content": {"parts": [{"text": "a"}]}}]}
            yield {"candidates": [{"content": {"parts": [{"text": "b"}]}}]}

        async_primary = _make_async_backend("sdk")
        async_primary.stream_generate_content = mock.Mock(return_value=_stream())
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        collected: list[str] = []
        async for chunk in coord.execute_stream_async(
            model="gemini",
            body={"contents": []},
            api_version="v1beta",
            timeout=30,
        ):
            collected.append(chunk["candidates"][0]["content"]["parts"][0]["text"])
        assert collected == ["a", "b"]

    @pytest.mark.asyncio
    async def test_execute_stream_async_capability_gate_raises(self) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend("sdk", supports=False)
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        async def drain() -> list[StreamChunk]:
            return [
                c
                async for c in coord.execute_stream_async(
                    model="gemini",
                    body={"contents": []},
                    api_version="v1beta",
                    timeout=30,
                    capability="live",
                )
            ]

        with pytest.raises(BackendUnavailableError, match="live"):
            await drain()

    @pytest.mark.asyncio
    async def test_execute_upload_async_routes_to_async_primary(self, tmp_path: Path) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend("sdk", upload_return={"name": "files/abc"})
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        src = tmp_path / "x.txt"
        src.write_text("hi")
        result = await coord.execute_upload_async(
            file_path=src,
            mime_type="text/plain",
            display_name=None,
            timeout=120,
        )
        assert result["name"] == "files/abc"
        async_primary.upload_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_upload_async_capability_gate_raises(self, tmp_path: Path) -> None:
        from core.transport.coordinator import TransportCoordinator

        primary = _make_backend("sdk")
        async_primary = _make_async_backend("sdk", supports=False)
        coord = TransportCoordinator(primary=primary, fallback=None, async_primary=async_primary)

        src = tmp_path / "x.txt"
        src.write_text("hi")
        with pytest.raises(BackendUnavailableError, match="files"):
            await coord.execute_upload_async(
                file_path=src,
                mime_type="text/plain",
                display_name=None,
                timeout=120,
                capability="files",
            )


class TestBuildBackendFactory:
    """The _build_backend helper is the only place the coordinator
    materializes Transport instances. An unknown name must surface as a
    ValueError immediately rather than failing later with a confusing
    AttributeError on a None backend."""

    def test_unknown_name_raises_value_error(self) -> None:
        from core.transport.coordinator import _build_backend

        with pytest.raises(ValueError, match="Unknown transport backend"):
            _build_backend("vertex")

    def test_known_names_build_real_transports(self) -> None:
        from core.transport.coordinator import _build_backend

        assert _build_backend("sdk").name == "sdk"
        assert _build_backend("raw_http").name == "raw_http"


class TestFromConfig:
    def test_from_config_builds_sdk_primary_when_sdk_priority(self) -> None:
        from core.infra.config import Config
        from core.transport.coordinator import TransportCoordinator

        cfg = Config(is_sdk_priority=True, is_rawhttp_priority=True)
        coord = TransportCoordinator.from_config(cfg)
        assert coord.primary.name == "sdk"
        assert coord.fallback is not None
        assert coord.fallback.name == "raw_http"

    def test_from_config_builds_raw_http_with_sdk_fallback_when_only_raw_http(
        self,
    ) -> None:
        from core.infra.config import Config
        from core.transport.coordinator import TransportCoordinator

        cfg = Config(is_sdk_priority=False, is_rawhttp_priority=True)
        coord = TransportCoordinator.from_config(cfg)
        assert coord.primary.name == "raw_http"
        assert coord.fallback is not None
        assert coord.fallback.name == "sdk"

    def test_from_config_builds_sdk_with_raw_http_fallback_when_only_sdk(self) -> None:
        from core.infra.config import Config
        from core.transport.coordinator import TransportCoordinator

        cfg = Config(is_sdk_priority=True, is_rawhttp_priority=False)
        coord = TransportCoordinator.from_config(cfg)
        assert coord.primary.name == "sdk"
        assert coord.fallback is not None
        assert coord.fallback.name == "raw_http"

    def test_from_config_builds_sdk_with_raw_http_fallback_when_both_flags_false(
        self,
    ) -> None:
        from core.infra.config import Config
        from core.transport.coordinator import TransportCoordinator

        cfg = Config(is_sdk_priority=False, is_rawhttp_priority=False)
        coord = TransportCoordinator.from_config(cfg)
        assert coord.primary.name == "sdk"
        assert coord.fallback is not None
        assert coord.fallback.name == "raw_http"
