"""TransportCoordinator — primary/fallback dispatch core for the dual-backend layer.

This module is the architectural heart of the dual-backend transport refactor.
It owns three decisions for every operation that flows through the public
facade:

1. **Capability gate** — when a capability name is known (the dispatch layer
   passes one), consult ``primary.supports(capability)`` BEFORE touching the
   primary backend's transport methods. A False return routes deterministically
   to the fallback backend with no try/except, no SDK probe, no log noise.
   This is the mechanism that makes capabilities like ``maps`` / ``music_gen``
   land on raw HTTP without ever invoking the SDK — the SDK never claims to
   support them, the coordinator never asks it to.

2. **Eligible-failure fallback** — when the primary backend raises an
   exception, consult ``policy.is_fallback_eligible(exc)``. If True AND a
   fallback backend exists, try the fallback. If False (auth error, bad
   request, programmer bug), re-raise immediately. If eligible but no
   fallback is configured, wrap the primary's exception as an ``APIError``
   carrying the primary backend context so log readers can tell which
   backend failed.

3. **Combined-error reporting** — when both backends fail, raise a single
   ``APIError`` whose ``primary_error`` / ``fallback_error`` fields carry
   both messages and whose ``__str__`` renders a structured two-line
   breakdown. This is what an operator sees when the system is fully
   degraded.

Design decisions made in the Phase 3 architect pass:

- **Capability is optional**: the legacy ``api_call`` facade signature does
  NOT carry a ``capability`` argument because every adapter in the repo
  imports through ``core/infra/client.py`` and we have a hard "zero adapter
  edits" contract. The coordinator accepts ``capability=None`` as the legacy
  path and skips the supports() gate in that case — only error-based
  fallback runs. The dispatch layer (Phase 3.5+) will eventually pass a real
  capability and turn on deterministic routing.
- **Singleton via the facade**: ``TransportCoordinator.from_config`` builds
  one coordinator from the current ``Config``. The facade in
  ``core/transport/__init__.py`` caches the result process-wide; tests use
  the ``reset_coordinator`` hook to drop the cache between runs.
- **Deadline tracking** is deferred to a Phase 3.1 follow-up. The
  ``timeout`` parameter is forwarded as-is to whichever backend handles
  the call; no remaining-budget bookkeeping yet.
- **Async path** is stubbed: ``execute_*_async`` raises
  ``NotImplementedError("Phase 6")`` so the symmetry is visible without
  blocking Phase 3.
- **Logging** lives here, not in policy.py. Policy is a pure decision
  function and stays side-effect-free; the coordinator emits one
  ``logging.WARNING`` per fallback (capability-gate or error-driven) so
  silent SDK→raw_http degradation is visible in production logs.

What you'll learn from this file:
    - **The Coordinator pattern**: a thin object that owns "which backend
      runs and when" and delegates the actual work. Adding a new backend
      means writing a Transport implementation; the coordinator never
      changes.
    - **Optional structured logging via the ``extra=`` kwarg**: every
      fallback is logged with a structured payload (primary, fallback,
      capability, reason) so log aggregators can filter on those fields
      without parsing message strings.

Dependencies: core/transport/base.py (Transport, BackendUnavailableError),
core/transport/policy.py (is_fallback_eligible),
core/infra/errors.py (APIError), core/infra/config.py (Config).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator, Mapping
from pathlib import Path
from typing import Callable, TypeVar, cast

from core.infra.config import Config
from core.infra.errors import APIError
from core.infra.sanitize import sanitize
from core.transport.base import (
    AsyncTransport,
    BackendUnavailableError,
    FileMetadata,
    GeminiResponse,
    StreamChunk,
    Transport,
)
from core.transport.policy import is_fallback_eligible

# Module-level logger. Tests assert on ``record.name == "core.transport.coordinator"``
# so this string is part of the contract — do not rename without updating the
# test harness in tests/transport/test_coordinator.py.
logger = logging.getLogger("core.transport.coordinator")

# Generic type variable for the operation-specific return value (a dict for
# ``api_call`` / ``upload_file``, an Iterator for ``stream_generate_content``).
# Lets ``_dispatch`` remain typed without forcing a Union return.
T = TypeVar("T")


class TransportCoordinator:
    """Owns the primary/fallback dispatch contract for the transport layer.

    Construct with a primary backend and an optional fallback backend, or
    use the ``from_config`` factory to build from a ``Config``. The
    coordinator is intentionally stateless beyond its two backend
    references — every call is independent.

    Attributes:
        primary: The backend the coordinator dispatches to first.
        fallback: The backend the coordinator dispatches to when the
            primary refuses (capability gate) or fails (eligible error).
            ``None`` means single-backend mode — failures bubble straight
            up as ``APIError``.
    """

    def __init__(
        self,
        primary: Transport,
        fallback: Transport | None,
        async_primary: AsyncTransport | None = None,
    ) -> None:
        # Same-backend construction is almost certainly a bug — the whole
        # point of the coordinator is to dispatch across two distinct
        # backends. Catching this at construction time means the
        # configuration error surfaces at startup, not on the first
        # fallback attempt during a real outage.
        if fallback is not None and primary is fallback:
            raise ValueError("TransportCoordinator: primary and fallback must differ")
        self.primary = primary
        self.fallback = fallback
        # Async primary is optional and has NO fallback partner. Raw HTTP
        # is sync-only (no urllib async story + the refactor deliberately
        # avoids an httpx dependency), and the Live API is SDK-only by
        # design. When the async primary is None, async dispatch raises
        # BackendUnavailableError — the caller either wired an async
        # primary at construction time or async methods can't run.
        self.async_primary = async_primary

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: Config) -> "TransportCoordinator":
        """Build a coordinator from a ``Config`` instance.

        Reads ``config.primary_backend`` / ``config.fallback_backend``
        and instantiates the matching ``Transport`` implementations.
        Raises whatever the underlying backend's constructor raises if
        the SDK is not importable — which the facade catches and reports
        via the standard error pipeline.

        Args:
            config: A validated ``core.infra.config.Config`` instance.

        Returns:
            A coordinator wired with the primary and (optionally)
            fallback backends per the config.
        """
        primary = _build_backend(config.primary_backend)
        fallback_name = config.fallback_backend
        fallback = _build_backend(fallback_name) if fallback_name is not None else None
        # Build an async primary ONLY when the SDK is the sync primary.
        # If raw HTTP is primary, no async path exists (sync-only backend);
        # if SDK is primary, the async path targets client.aio.*.
        async_primary: AsyncTransport | None = None
        if config.primary_backend == "sdk":
            async_primary = _build_async_backend()
        return cls(primary=primary, fallback=fallback, async_primary=async_primary)

    # ------------------------------------------------------------------
    # Public dispatch methods (mirror the Transport surface)
    # ------------------------------------------------------------------

    def execute_api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None,
        method: str,
        api_version: str,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> GeminiResponse:
        """Dispatch an ``api_call`` through the primary/fallback decision matrix.

        Args:
            endpoint: REST-shaped endpoint string passed straight through to
                whichever backend handles the call.
            body: JSON-serializable request body, or ``None`` for GET.
            method: HTTP method.
            api_version: API version segment.
            timeout: Request timeout in seconds. Forwarded as-is; deadline
                tracking across the fallback is a Phase 3.1 follow-up.
            capability: Optional capability name (e.g. ``"text"``,
                ``"maps"``). When provided, the coordinator consults
                ``primary.supports(capability)`` before dispatching. When
                ``None`` (the legacy facade path), the gate is skipped
                and the primary always runs first.

        Returns:
            The normalized ``GeminiResponse`` envelope from whichever
            backend ultimately handled the call.

        Raises:
            BackendUnavailableError: If the primary's capability gate
                returned False AND no fallback is configured.
            APIError: When both backends fail, or when the primary's
                error is fallback-eligible but no fallback exists. The
                error carries ``primary_backend`` / ``primary_error`` /
                ``fallback_backend`` / ``fallback_error`` context fields.
            BaseException: A non-fallback-eligible exception from the
                primary backend (auth errors, programmer bugs, …)
                propagates unchanged.
        """
        return self._dispatch(
            op_name="api_call",
            capability=capability,
            call=lambda backend: backend.api_call(
                endpoint=endpoint,
                body=body,
                method=method,
                api_version=api_version,
                timeout=timeout,
            ),
        )

    def execute_stream(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> Iterator[StreamChunk]:
        """Dispatch a streaming generate call. See ``execute_api_call`` for the matrix."""
        return self._dispatch(
            op_name="stream_generate_content",
            capability=capability,
            call=lambda backend: backend.stream_generate_content(
                model=model,
                body=body,
                api_version=api_version,
                timeout=timeout,
            ),
        )

    def execute_upload(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> FileMetadata:
        """Dispatch a file upload. See ``execute_api_call`` for the matrix."""
        return self._dispatch(
            op_name="upload_file",
            capability=capability,
            call=lambda backend: backend.upload_file(
                file_path=file_path,
                mime_type=mime_type,
                display_name=display_name,
                timeout=timeout,
            ),
        )

    # ------------------------------------------------------------------
    # Async stubs (Phase 6)
    # ------------------------------------------------------------------

    async def execute_api_call_async(
        self,
        endpoint: str,
        body: Mapping[str, object] | None,
        method: str,
        api_version: str,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> GeminiResponse:
        """Async dispatch of an ``api_call`` through the async primary.

        The async path has no fallback partner (raw HTTP is sync-only),
        so the decision matrix is simpler than the sync dispatch:

        1. No async primary configured → BackendUnavailableError.
        2. Capability gate: ``supports(capability)`` False →
           BackendUnavailableError (no fallback to route to).
        3. Otherwise: await the async primary's api_call and return.
           Every exception propagates unchanged — the caller handles retry.

        Args:
            endpoint: REST-shaped endpoint string.
            body: Request body or None.
            method: HTTP method.
            api_version: API version segment (ignored by SDK; accepted
                for symmetry with the sync API).
            timeout: Request timeout in seconds.
            capability: Optional capability name for the gate check.

        Returns:
            The normalized GeminiResponse envelope from the async primary.

        Raises:
            BackendUnavailableError: When no async primary is configured,
                or when the capability gate refuses the capability.
            BaseException: Every exception from the async primary propagates
                unchanged — there's no fallback to swallow it.
        """
        async_primary = self._require_async_primary(op_name="api_call")
        self._async_capability_gate(async_primary, op_name="api_call", capability=capability)
        return await async_primary.api_call(
            endpoint=endpoint,
            body=body,
            method=method,
            api_version=api_version,
            timeout=timeout,
        )

    async def execute_stream_async(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Async stream dispatch. Yields normalized chunks from the async primary.

        Implemented as an async generator so callers use ``async for`` to
        drain. Raises BackendUnavailableError BEFORE yielding if no async
        primary is configured or if the capability gate refuses.

        Args:
            model: Gemini model identifier.
            body: REST-shaped request body.
            api_version: API version segment.
            timeout: Per-chunk-read timeout.
            capability: Optional capability name.

        Yields:
            StreamChunk envelopes from the async primary's stream.

        Raises:
            BackendUnavailableError: When no async primary is configured,
                or when the capability gate refuses.
        """
        async_primary = self._require_async_primary(op_name="stream_generate_content")
        self._async_capability_gate(
            async_primary, op_name="stream_generate_content", capability=capability
        )
        async for chunk in async_primary.stream_generate_content(
            model=model, body=body, api_version=api_version, timeout=timeout
        ):
            yield chunk

    async def execute_upload_async(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None,
        timeout: int,
        *,
        capability: str | None = None,
    ) -> FileMetadata:
        """Async upload dispatch through the async primary.

        Args:
            file_path: Path to file to upload.
            mime_type: MIME type.
            display_name: Optional display name.
            timeout: Upload timeout.
            capability: Optional capability name for the gate.

        Returns:
            FileMetadata envelope.

        Raises:
            BackendUnavailableError: When no async primary is configured
                or when the capability gate refuses.
        """
        async_primary = self._require_async_primary(op_name="upload_file")
        self._async_capability_gate(async_primary, op_name="upload_file", capability=capability)
        return await async_primary.upload_file(
            file_path=file_path,
            mime_type=mime_type,
            display_name=display_name,
            timeout=timeout,
        )

    def _require_async_primary(self, *, op_name: str) -> AsyncTransport:
        """Return self.async_primary or raise BackendUnavailableError.

        Extracted so the three public async methods share one error
        message instead of diverging over time.
        """
        if self.async_primary is None:
            raise BackendUnavailableError(
                sanitize(
                    f"TransportCoordinator: async dispatch requires an async "
                    f"primary backend, but none is configured (op='{op_name}'). "
                    f"Async-only capabilities (Live API) need GEMINI_IS_SDK_PRIORITY=true."
                )
            )
        return self.async_primary

    def _async_capability_gate(
        self,
        async_primary: AsyncTransport,
        *,
        op_name: str,
        capability: str | None,
    ) -> None:
        """Raise if the async primary refuses ``capability``.

        Async path has no fallback, so an unsupported capability is a
        hard error. Logs at WARNING the same way the sync capability
        gate does so log aggregators see a consistent reason string.
        """
        if capability is None:
            return
        if async_primary.supports(capability):
            return
        logger.warning(
            "transport_async_gate primary=%s capability=%s op=%s reason=capability_gate",
            async_primary.name,
            capability,
            op_name,
            extra={
                "primary": async_primary.name,
                "capability": capability,
                "op": op_name,
                "reason": "capability_gate_async",
            },
        )
        raise BackendUnavailableError(
            sanitize(
                f"Capability '{capability}' is not supported by async primary "
                f"backend '{async_primary.name}' (async path has no fallback)."
            )
        )

    # ------------------------------------------------------------------
    # Private dispatch core
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        op_name: str,
        capability: str | None,
        call: Callable[[Transport], T],
    ) -> T:
        """The decision matrix shared by every public dispatch method.

        This is intentionally one method, not three, so the
        capability-gate / error-fallback / combined-error logic stays in
        a single place. The caller passes a closure that knows how to
        invoke the right method on whichever backend it receives.

        Args:
            op_name: Logical operation name (``"api_call"`` /
                ``"stream_generate_content"`` / ``"upload_file"``). Used
                for log line ``op=`` field; not consulted in routing.
            capability: Optional capability name. ``None`` skips the gate.
            call: Closure that takes a backend and runs the operation.
                Returns whatever shape the underlying Transport method
                returns — the coordinator doesn't peek at the result.

        Returns:
            Whatever ``call(backend)`` returns from the backend that
            ultimately handled the dispatch.
        """
        # ---------- Step 1: capability gate ----------
        # Only runs when the dispatch layer told us what capability this
        # call represents. The legacy facade leaves capability=None and
        # falls through to the always-try-primary path.
        if capability is not None and not self.primary.supports(capability):
            return self._route_via_capability_gate(
                op_name=op_name, capability=capability, call=call
            )

        # ---------- Step 2: try the primary ----------
        try:
            return call(self.primary)
        except BaseException as primary_exc:
            return self._handle_primary_failure(
                op_name=op_name,
                capability=capability,
                call=call,
                primary_exc=primary_exc,
            )

    def _route_via_capability_gate(
        self,
        op_name: str,
        capability: str,
        call: Callable[[Transport], T],
    ) -> T:
        """Deterministic route to fallback when the primary refuses a capability.

        Logged at WARNING with ``reason="capability_gate"`` so operators
        can grep for which capabilities are silently routing to raw HTTP
        and decide whether to flip them to first-class SDK in a future
        version bump.
        """
        if self.fallback is None:
            # No fallback configured → raise BackendUnavailableError so
            # the user sees a clear "this capability is unsupported on
            # this backend and you have no fallback" message instead of
            # a mysterious 404 or the primary backend silently doing the
            # wrong thing.
            raise BackendUnavailableError(
                sanitize(
                    f"Capability '{capability}' is not supported by "
                    f"primary backend '{self.primary.name}' and no "
                    f"fallback is configured."
                )
            )
        logger.warning(
            "transport_fallback primary=%s fallback=%s capability=%s op=%s reason=capability_gate",
            self.primary.name,
            self.fallback.name,
            capability,
            op_name,
            extra={
                "primary": self.primary.name,
                "fallback": self.fallback.name,
                "capability": capability,
                "op": op_name,
                "reason": "capability_gate",
            },
        )
        return call(self.fallback)

    def _handle_primary_failure(
        self,
        op_name: str,
        capability: str | None,
        call: Callable[[Transport], T],
        primary_exc: BaseException,
    ) -> T:
        """Decide what to do when the primary backend raised an exception.

        Three possible outcomes:
        1. **Not eligible**: re-raise the original exception with its
           traceback intact.
        2. **Eligible, no fallback**: wrap as an APIError carrying the
           primary backend context, chained from the primary exception
           so post-mortem debuggers can still walk back to the backend
           call site.
        3. **Eligible, fallback exists**: log + try the fallback. If the
           fallback also fails, raise a combined APIError chained from
           the most recent failure (the fallback's exception).
        """
        # 1. Programmer bugs, auth failures, cost limits → re-raise.
        # ``raise`` (no expression) preserves the original traceback —
        # ``raise primary_exc`` would re-raise from this line and lose
        # the backend call-site frame, making post-mortem debugging
        # harder for no benefit.
        if not is_fallback_eligible(primary_exc):
            raise

        # 2. Eligible but nowhere to go → wrap as APIError with primary context.
        # ``from primary_exc`` preserves the cause chain so Sentry /
        # logger.exception can show the original backend exception's
        # traceback alongside the wrapper. The structured fields hold
        # the *string* form for grep-ability; the chain holds the
        # *traceback* for debugging.
        if self.fallback is None:
            raise APIError(
                sanitize(
                    f"Primary backend '{self.primary.name}' failed and no "
                    f"fallback is configured."
                ),
                status_code=getattr(primary_exc, "status_code", None),
                primary_backend=self.primary.name,
                primary_error=str(primary_exc),
            ) from primary_exc

        # 3. Eligible AND fallback exists → log + try fallback.
        logger.warning(
            "transport_fallback primary=%s fallback=%s capability=%s op=%s reason=%s",
            self.primary.name,
            self.fallback.name,
            capability,
            op_name,
            type(primary_exc).__name__,
            extra={
                "primary": self.primary.name,
                "fallback": self.fallback.name,
                "capability": capability,
                "op": op_name,
                "reason": type(primary_exc).__name__,
            },
        )
        try:
            return call(self.fallback)
        except BaseException as fallback_exc:
            # Both backends failed — surface a combined APIError so the
            # log reader sees both error strings without inspecting the
            # exception attributes. ``from fallback_exc`` chains the
            # most recent failure (preserving its traceback for
            # post-mortems); the primary's traceback is not preserved
            # in the chain but its *string* form is in primary_error.
            # APIError sanitizes primary_error / fallback_error in its
            # constructor, so the raw exception strings are safe to
            # forward here without an explicit sanitize() wrap.
            raise APIError(
                sanitize(f"Both backends failed for op '{op_name}'."),
                status_code=getattr(fallback_exc, "status_code", None),
                primary_backend=self.primary.name,
                fallback_backend=self.fallback.name,
                primary_error=str(primary_exc),
                fallback_error=str(fallback_exc),
            ) from fallback_exc


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------


def _build_backend(name: str) -> Transport:
    """Construct the Transport implementation for a named backend.

    A free function (not a static method) so tests can mock it without
    reaching for a class attribute. The function itself is trivial — its
    only purpose is to keep the SDK + raw HTTP imports lazy enough that
    a coordinator built with raw HTTP only never touches google.genai.

    Args:
        name: Either ``"sdk"`` or ``"raw_http"``.

    Returns:
        A fresh Transport instance for the named backend.

    Raises:
        ValueError: If ``name`` is not a recognized backend label.
    """
    # Each concrete backend declares ``name`` as a narrow ``Literal["sdk"]``
    # / ``Literal["raw_http"]`` ClassVar, while the Protocol declares the
    # broader ``Literal["sdk", "raw_http"]``. mypy --strict cannot prove the
    # narrow class-level Literals satisfy the broader Protocol field, so we
    # cast at the boundary. This is sound: every constructed backend is one
    # of the two members of the Protocol's Literal union.
    if name == "sdk":
        # Lazy import — keeps the raw HTTP path importable even when
        # google-genai is not installed.
        from core.transport.sdk.transport import SdkTransport

        return cast(Transport, SdkTransport())
    if name == "raw_http":
        from core.transport.raw_http.transport import RawHttpTransport

        return cast(Transport, RawHttpTransport())
    raise ValueError(f"Unknown transport backend: {name!r}")


def _build_async_backend() -> AsyncTransport:
    """Construct the async SDK backend.

    Separate from ``_build_backend`` because there's only one async
    implementation (SDK) — raw HTTP has no async twin. A free function
    (not a static method) so tests can mock it without reaching for a
    class attribute. Lazy-imports the module so a coordinator built
    with raw HTTP primary never loads google.genai.

    Returns:
        A fresh SdkAsyncTransport instance, cast to the AsyncTransport
        Protocol for the same Literal-variance reason as _build_backend.
    """
    from core.transport.sdk.async_transport import SdkAsyncTransport

    return cast(AsyncTransport, SdkAsyncTransport())
