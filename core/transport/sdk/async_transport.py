"""SdkAsyncTransport — async mirror of ``SdkTransport``.

Phase 6 of the dual-backend transport refactor introduces an async dispatch
path so async-only capabilities (the Live API) and future ``--parallel``
adapters can reach the google-genai SDK without going through a sync
wrapper. This module is the thin async equivalent of
``core/transport/sdk/transport.py``:

1. **Shared capability registry.** The async transport advertises the exact
   same ``_SUPPORTED_CAPABILITIES`` as the sync ``SdkTransport`` — every
   capability the sync surface handles also has an async twin under
   ``client.aio.*``. Reusing the frozenset keeps the two in lockstep so a
   future SDK version bump only has to edit one place.

2. **``client.aio.*`` dispatch.** The sync transport calls
   ``client.models.generate_content(...)``; the async transport awaits
   ``client.aio.models.generate_content(...)``. Every other method on the
   aio namespace is the async twin of its sync counterpart, so the dispatch
   tables line up one-to-one.

3. **No fallback partner.** Raw HTTP is sync-only (urllib has no first-class
   async story and the refactor deliberately refuses to grow an httpx
   dependency), so the async coordinator's path doesn't call into raw HTTP.
   Async-only capabilities are SDK-only by design.

4. **Shared error mapping.** The module imports ``_wrap_sdk_errors`` from
   ``core/transport/sdk/transport.py`` so the sync and async paths route
   google.genai error classes through the SAME typed-mapping code — no
   duplication, no drift between the two surfaces.

What you'll learn from this file:
    - **Async generator functions**: a function with ``async def`` + ``yield``
      returns an ``AsyncIterator`` synchronously when called. Consumers use
      ``async for`` to drain it; the function body suspends at each ``yield``
      until the consumer advances.
    - **Sharing a contextmanager between sync and async call sites**: the
      ``@contextmanager`` decorator produces a context manager that's valid
      in both sync ``with`` and ``async with``-adjacent code as long as the
      wrapped body doesn't itself await. We use it from inside async methods
      here — the try/except surface runs synchronously during exception
      propagation, which is exactly what we want for error translation.

Dependencies: core/transport/sdk/client_factory.py (get_client —
the ``.aio`` namespace lives on the singleton client),
core/transport/sdk/transport.py (shared _wrap_sdk_errors + body
translation helpers), core/transport/normalize.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import ClassVar, Literal, cast

from core.infra.sanitize import sanitize
from core.transport._validation import validate_mime_type, validate_no_crlf
from core.transport.base import (
    BackendUnavailableError,
    FileMetadata,
    GeminiResponse,
    StreamChunk,
)
from core.transport.normalize import (
    sdk_file_to_metadata,
    sdk_response_to_rest_envelope,
    sdk_stream_chunk_to_envelope,
)
from core.transport.sdk.client_factory import get_client
from core.transport.sdk.transport import SdkTransport, _wrap_sdk_errors


class SdkAsyncTransport:
    """Async google-genai SDK backend implementing ``AsyncTransport``.

    This class intentionally shares its dispatch tables and capability
    registry with the sync ``SdkTransport``. The difference is mechanical:
    every SDK call site awaits a coroutine on ``client.aio.*`` instead of
    calling a sync method on ``client.*``. Tests that verify both surfaces
    therefore use the same fake payloads — the envelope-normalization
    contract is already covered by the sync test file.

    Attributes:
        name: Always ``"sdk"``. Same as the sync transport so dispatch
            layers and log readers don't need to special-case async.
    """

    name: ClassVar[Literal["sdk"]] = "sdk"

    def supports(self, capability: str) -> bool:
        """Return True iff the SDK advertises an async twin for ``capability``.

        Delegates to the sync SdkTransport's registry. The contract is that
        every sync capability has an async twin at ``client.aio.<same-path>``
        — the pinned google-genai 1.33.0 release satisfies this by construction
        (the aio namespace is code-generated from the same service definitions
        the sync namespace uses).

        Args:
            capability: Dispatch capability name.

        Returns:
            ``True`` iff the sync registry claims support; ``False`` otherwise.
        """
        return capability in SdkTransport._SUPPORTED_CAPABILITIES

    # ------------------------------------------------------------------
    # api_call dispatch
    # ------------------------------------------------------------------

    async def api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        method: str = "POST",
        api_version: str = "v1beta",
        timeout: int = 30,
    ) -> GeminiResponse:
        """Translate a REST-shaped endpoint into an awaited SDK aio call.

        Mirror of ``SdkTransport.api_call`` — see that module's docstring
        for the shape families and dispatch rules. Every branch here is
        the async twin of the corresponding sync branch.

        Args:
            endpoint: REST-shaped endpoint path (no leading slash).
            body: Request body (camelCase REST shape) or None for GET/DELETE.
            method: HTTP method. Used to disambiguate CRUD routes.
            api_version: Ignored — the SDK manages versioning.
            timeout: Currently unused (Phase 3.1 deadline-tracking hook
                is where this will flow through).

        Returns:
            A GeminiResponse dict normalized from the SDK response.

        Raises:
            BackendUnavailableError: On unknown endpoint shapes so the
                coordinator can surface a clear error. Async path has no
                fallback target, so this reaches the caller unchanged.
            APIError / AuthError: Translated by ``_wrap_sdk_errors`` from
                google.genai error classes.
        """
        client = get_client()
        method_upper = method.upper()
        body_dict: dict[str, object] = dict(body) if body is not None else {}

        with _wrap_sdk_errors():
            if ":" in endpoint:
                return await self._dispatch_action(client, endpoint, body_dict)
            parts = endpoint.split("/")
            return await self._dispatch_crud(client, parts, method_upper)

    async def _dispatch_action(
        self,
        client: object,
        endpoint: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        """Handle ``X:action`` endpoints by awaiting the right aio method."""
        path, _, action = endpoint.partition(":")
        if path.startswith("models/"):
            model = path[len("models/") :]
            return await self._dispatch_model_action(client, model, action, body)
        raise BackendUnavailableError(
            sanitize(f"SdkAsyncTransport: unknown action endpoint '{endpoint}'")
        )

    async def _dispatch_model_action(
        self,
        client: object,
        model: str,
        action: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        """Await the right ``client.aio.models.*`` method for a model action."""
        # Reuse the sync transport's body translation helpers — they are
        # pure functions that don't touch the client, so they work equally
        # well for sync and async call sites.
        sync = SdkTransport()

        if action == "generateContent":
            contents, config = sync._build_generate_content_kwargs(body)
            sdk_resp = await client.aio.models.generate_content(  # type: ignore[attr-defined]
                model=model, contents=contents, config=config
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "countTokens":
            sdk_resp = await client.aio.models.count_tokens(  # type: ignore[attr-defined]
                model=model, contents=body.get("contents", [])
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "embedContent":
            contents = body.get("content") or body.get("contents")
            config = sync._build_embed_content_config(body)
            sdk_resp = await client.aio.models.embed_content(  # type: ignore[attr-defined]
                model=model, contents=contents, config=config
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "predictLongRunning":
            prompt = sync._extract_video_prompt(body)
            sdk_resp = await client.aio.models.generate_videos(  # type: ignore[attr-defined]
                model=model, prompt=prompt
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        raise BackendUnavailableError(
            sanitize(f"SdkAsyncTransport: unknown model action '{action}' for model '{model}'")
        )

    async def _dispatch_crud(
        self,
        client: object,
        parts: list[str],
        method: str,
    ) -> GeminiResponse:
        """Handle CRUD endpoints (no colon) via the aio namespace."""
        collection = parts[0]
        has_id = len(parts) > 1
        full_name = "/".join(parts)

        if collection == "files":
            if has_id and method == "GET":
                sdk_resp = await client.aio.files.get(name=full_name)  # type: ignore[attr-defined]
                return sdk_response_to_rest_envelope(sdk_resp)
            if has_id and method == "DELETE":
                await client.aio.files.delete(name=full_name)  # type: ignore[attr-defined]
                return cast(GeminiResponse, {})

        if collection == "operations":
            if has_id and method == "GET":
                sdk_resp = await client.aio.operations.get(operation=full_name)  # type: ignore[attr-defined]
                return sdk_response_to_rest_envelope(sdk_resp)

        raise BackendUnavailableError(
            sanitize(
                f"SdkAsyncTransport: unknown {method} endpoint '{full_name}' "
                f"(collection '{collection}' not in async dispatch table)"
            )
        )

    # ------------------------------------------------------------------
    # stream_generate_content (async generator)
    # ------------------------------------------------------------------

    async def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str = "v1beta",
        timeout: int = 30,
    ) -> AsyncIterator[StreamChunk]:
        """Yield normalized stream chunks from ``client.aio.models.generate_content_stream``.

        Implemented as an async generator function so the caller uses
        ``async for`` to pull chunks. The SDK's aio streaming method
        returns an async iterator directly (not a coroutine that returns
        one), so we iterate it with ``async for`` inside the wrapper and
        forward each chunk through the normalizer.

        Args:
            model: Gemini model identifier.
            body: REST-shaped generateContent request body.
            api_version: Ignored — SDK manages versioning.
            timeout: Currently unused; deadline tracking is Phase 3.1.

        Yields:
            StreamChunk envelopes (camelCase REST shape) one per SDK chunk.

        Raises:
            APIError / AuthError: Translated from google.genai errors via
                ``_wrap_sdk_errors``. Errors raised mid-stream are wrapped
                the same way as errors raised from the initial call.
        """
        client = get_client()
        body_dict: dict[str, object] = dict(body)
        sync = SdkTransport()
        with _wrap_sdk_errors():
            contents, config = sync._build_generate_content_kwargs(body_dict)
            sdk_iterator = client.aio.models.generate_content_stream(
                model=model, contents=contents, config=config
            )
            async for chunk in sdk_iterator:
                yield sdk_stream_chunk_to_envelope(chunk)

    # ------------------------------------------------------------------
    # upload_file
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None = None,
        timeout: int = 120,
    ) -> FileMetadata:
        """Upload a file via ``client.aio.files.upload``.

        Mirror of the sync ``upload_file``. Validates mime/display_name
        at the boundary BEFORE awaiting the SDK so a malformed input
        never reaches the wire. The test
        ``test_upload_rejects_bad_mime_before_client_call`` asserts this
        ordering via ``assert_not_awaited`` on the mock upload.

        Args:
            file_path: Path to the file to upload.
            mime_type: MIME type, validated against the same regex the
                sync path uses.
            display_name: Optional display name; CR/LF rejected.
            timeout: Currently unused.

        Returns:
            FileMetadata envelope with camelCase keys.

        Raises:
            ValueError: For invalid mime_type or display_name. Bare
                ValueError matches policy.py's NEVER_FALLBACK list —
                there's no fallback target on the async path anyway,
                but the error class stays consistent with the sync
                transport.
        """
        validate_mime_type(mime_type)
        if display_name is not None:
            validate_no_crlf(display_name, field_name="display_name")

        client = get_client()
        with _wrap_sdk_errors():
            sdk_file = await client.aio.files.upload(
                file=str(file_path),
                config={"mime_type": mime_type, "display_name": display_name},
            )
        return sdk_file_to_metadata(sdk_file)
