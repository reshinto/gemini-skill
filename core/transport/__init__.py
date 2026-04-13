"""Dual-backend Gemini transport package — public facade.

This module is the **only** entry point adapters and the legacy
``core/infra/client.py`` shim should import from. Three sync functions
(``api_call``, ``stream_generate_content``, ``upload_file``) match the
legacy raw HTTP client signature byte-for-byte so the 19 adapters in
``adapters/`` need ZERO edits.

Behind each function sits a process-wide ``TransportCoordinator``
singleton built lazily from the current ``Config`` on first access.
The singleton owns the primary/fallback decision matrix; this facade is
intentionally thin — it just forwards kwargs and returns the result.

Why is this a singleton? Two reasons:

1. **Config is read once at process start.** Re-reading on every call
   would burn unnecessary I/O and re-probe SDK availability, which
   matters when the SDK isn't installed.
2. **The lru_cache on ``client_factory.get_client`` is process-wide
   too.** A per-call coordinator construction would still hit the
   same cached SDK client, so making the coordinator per-call buys
   nothing but extra allocations.

Tests use ``reset_coordinator()`` to drop the cache between runs.

Why no ``capability`` argument on the public facade? The dispatch layer
(Phase 3.5+) is the one that knows what capability each call
represents. Plumbing a capability through every adapter would touch
all 19 files and break the "zero adapter edits" contract this refactor
explicitly promises. Until dispatch.py is migrated, the facade calls
the coordinator with ``capability=None``; the coordinator's
capability-gate code path simply doesn't run, and only error-based
fallback can fire. Adapters that care about deterministic capability
routing today can opt in by calling ``get_coordinator()`` directly.

What you'll learn from this file:
    - **Module-level singleton with a reset hook**: a private
      module-level variable (``_COORDINATOR``) plus public
      ``get_coordinator`` / ``reset_coordinator`` accessors gives you
      lazy initialization and an easy test-isolation seam without
      pulling in a singleton library.
    - **Re-exporting names through ``__all__``**: the facade exports
      its public names explicitly so ``from core.transport import *``
      pulls only the intended surface, and so static-analysis tools
      know which names are part of the public contract.

Dependencies: core/transport/coordinator.py (TransportCoordinator),
core/infra/config.py (Config), core/transport/raw_http/client.py
(BASE_URL re-export, direct-key bypass).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from pathlib import Path

from core.transport.base import FileMetadata, GeminiResponse, StreamChunk
from core.transport.coordinator import TransportCoordinator
from core.transport.raw_http.client import BASE_URL

__all__ = [
    "BASE_URL",
    "api_call",
    "stream_generate_content",
    "upload_file",
    "async_api_call",
    "async_stream_generate_content",
    "async_upload_file",
    "get_coordinator",
    "reset_coordinator",
]

# Module-level singleton — built lazily on first ``_get_coordinator()`` call.
# ``None`` means "not yet built"; the test hook ``reset_coordinator()`` resets
# the slot back to None so a fresh build runs on the next access.
_COORDINATOR: TransportCoordinator | None = None


def get_coordinator() -> TransportCoordinator:
    """Return the process-wide TransportCoordinator, building it on first use.

    Public alias for the private ``_get_coordinator``. Adapters that want
    to reach the coordinator directly (e.g. to pass an explicit
    ``capability`` for deterministic routing) call this — every other
    caller should use ``api_call`` / ``stream_generate_content`` /
    ``upload_file``, which delegate to it internally.

    Returns:
        The cached ``TransportCoordinator`` instance. Identical across
        calls until ``reset_coordinator`` is invoked.
    """
    return _get_coordinator()


def reset_coordinator() -> None:
    """Drop the cached coordinator so the next call rebuilds from Config.

    Test-isolation seam. Production code never calls this. Tests call
    it between runs (typically via an autouse fixture in
    ``tests/transport/conftest.py``) to make sure each test sees a
    fresh coordinator built from whatever Config the test arranged.
    """
    global _COORDINATOR
    _COORDINATOR = None


def _get_coordinator() -> TransportCoordinator:
    """Lazy singleton builder — internal entry point."""
    global _COORDINATOR
    if _COORDINATOR is None:
        # Lazy import keeps test mocks easy: tests can replace
        # ``load_config`` at the call site without monkey-patching the
        # module top.
        from core.infra.config import load_config

        _COORDINATOR = TransportCoordinator.from_config(load_config())
    return _COORDINATOR


def api_call(
    endpoint: str,
    body: Mapping[str, object] | None = None,
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
) -> GeminiResponse:
    """Make an authenticated request through the dual-backend coordinator.

    Signature matches ``core/transport/raw_http/client.py::api_call`` for
    every kwarg the adapters use. The legacy ``api_key=`` bypass parameter
    is **not** on this facade — it lives on ``core/infra/client.py``
    (the legacy shim) instead, because explicit-key auth is a raw-HTTP-only
    concept and would couple this backend-agnostic facade to one backend's
    auth model. Adapters that need explicit-key auth import via the shim;
    everyone else (the 19 production adapters) flows through here without
    noticing the difference.

    Args:
        endpoint: REST endpoint path (e.g. ``"models/gemini:generateContent"``).
        body: JSON request body, or ``None`` for GET.
        method: HTTP method.
        api_version: API version segment.
        timeout: Request timeout in seconds.

    Returns:
        The parsed ``GeminiResponse`` envelope from whichever backend
        ultimately handled the call.
    """
    return _get_coordinator().execute_api_call(
        endpoint=endpoint,
        body=body,
        method=method,
        api_version=api_version,
        timeout=timeout,
        capability=None,
    )


def stream_generate_content(
    model: str,
    body: Mapping[str, object],
    api_version: str = "v1beta",
    timeout: int = 30,
) -> Iterator[StreamChunk]:
    """Stream generateContent responses through the coordinator.

    Signature matches ``core/transport/raw_http/client.py::stream_generate_content``.

    Args:
        model: Gemini model name (e.g. ``"gemini-2.5-flash"``).
        body: Request body — must include ``contents``.
        api_version: API version segment.
        timeout: Request timeout in seconds.

    Yields:
        ``StreamChunk`` dicts (camelCase REST envelope) from whichever
        backend ultimately handled the stream.
    """
    yield from _get_coordinator().execute_stream(
        model=model,
        body=body,
        api_version=api_version,
        timeout=timeout,
        capability=None,
    )


def upload_file(
    file_path: Path | str,
    mime_type: str,
    display_name: str | None = None,
    timeout: int = 120,
) -> FileMetadata:
    """Upload a file through the coordinator.

    Signature matches ``core/transport/raw_http/client.py::upload_file``.

    Args:
        file_path: Path to the file (str or Path accepted).
        mime_type: MIME type of the upload. Validated by both backends
            against the same RFC 2045 regex.
        display_name: Optional display name shown by the Files API.
        timeout: Request timeout in seconds (default 120).

    Returns:
        A ``FileMetadata`` dict with camelCase keys.
    """
    return _get_coordinator().execute_upload(
        file_path=file_path,
        mime_type=mime_type,
        display_name=display_name,
        timeout=timeout,
        capability=None,
    )


# ---------------------------------------------------------------------------
# Async facade (Phase 6)
# ---------------------------------------------------------------------------
#
# Async mirrors of the three sync methods. The coordinator's async surface
# only runs when an async primary (SDK) is wired; raw HTTP has no async
# twin so the facade does NOT accept an ``api_key=`` bypass here either —
# explicit-key auth stays on the sync shim.


async def async_api_call(
    endpoint: str,
    body: Mapping[str, object] | None = None,
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
) -> GeminiResponse:
    """Async twin of :func:`api_call`.

    Forwards to ``TransportCoordinator.execute_api_call_async``. Raises
    ``BackendUnavailableError`` when no async primary is configured
    (i.e. when ``GEMINI_IS_SDK_PRIORITY=false`` and the coordinator only
    has a raw HTTP primary — raw HTTP is sync-only).

    Args:
        endpoint: REST-shaped endpoint string.
        body: JSON request body or None.
        method: HTTP method.
        api_version: API version segment.
        timeout: Request timeout in seconds.

    Returns:
        The normalized ``GeminiResponse`` from the async primary.
    """
    return await _get_coordinator().execute_api_call_async(
        endpoint=endpoint,
        body=body,
        method=method,
        api_version=api_version,
        timeout=timeout,
        capability=None,
    )


async def async_stream_generate_content(
    model: str,
    body: Mapping[str, object],
    api_version: str = "v1beta",
    timeout: int = 30,
) -> AsyncIterator[StreamChunk]:
    """Async twin of :func:`stream_generate_content`.

    Implemented as an async generator so callers use ``async for`` to
    drain chunks. Forwards to the coordinator's async stream dispatch.
    """
    async for chunk in _get_coordinator().execute_stream_async(
        model=model,
        body=body,
        api_version=api_version,
        timeout=timeout,
        capability=None,
    ):
        yield chunk


async def async_upload_file(
    file_path: Path | str,
    mime_type: str,
    display_name: str | None = None,
    timeout: int = 120,
) -> FileMetadata:
    """Async twin of :func:`upload_file`. Forwards to the coordinator."""
    return await _get_coordinator().execute_upload_async(
        file_path=file_path,
        mime_type=mime_type,
        display_name=display_name,
        timeout=timeout,
        capability=None,
    )
