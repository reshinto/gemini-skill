"""RawHttpTransport — Transport-protocol wrapper around the urllib client.

This module is intentionally tiny: it adapts the three module-level functions
in ``core/transport/raw_http/client.py`` (``api_call``,
``stream_generate_content``, ``upload_file``) into a class that satisfies the
``core.transport.base.Transport`` Protocol. The coordinator instantiates this
class once per process and dispatches calls into it.

Why a wrapper class instead of "just use the functions directly"? The
coordinator needs polymorphism — at runtime it holds a
``primary: Transport`` and a ``fallback: Transport | None`` and calls the
same method names regardless of which backend is in either slot. A class is
the cheapest way to expose the same shape from both the SDK backend and the
raw HTTP backend without forcing the coordinator to branch on
``isinstance(backend, types.ModuleType)``.

All retry, SSE, multipart, error-extraction, and mime-validation logic lives
in ``client.py`` and is unchanged by the move. This file contains zero
business logic.

What you'll learn from this file:
    - The **Adapter pattern**: same interface (Transport), two
      implementations (raw HTTP and — landing in Phase 2 — SDK). The
      coordinator interacts with the abstract interface and never sees
      either implementation directly.
    - **Module-level imports under aliases** (``... as _client_api_call``)
      are how you expose a function to ``unittest.mock.patch`` without
      polluting the public API surface. The leading underscore signals
      "internal — do not import" to readers and to ``__all__``-aware
      tooling, while the patch target stays stable for tests.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

from core.transport.base import FileMetadata, GeminiResponse, StreamChunk
from core.transport.raw_http.client import api_call as _client_api_call
from core.transport.raw_http.client import (
    stream_generate_content as _client_stream_generate_content,
)
from core.transport.raw_http.client import upload_file as _client_upload_file


class RawHttpTransport:
    """Synchronous Transport implementation backed by ``urllib``.

    This class is **stateless** — every method call is a fresh, independent
    HTTP request. A single instance can be reused across the lifetime of the
    process; the coordinator holds exactly one for the duration of a session.

    The Protocol contract (see ``core/transport/base.py::Transport``) is
    satisfied structurally — there is no need to inherit from ``Transport``
    because Python's ``@runtime_checkable`` Protocol verifies method
    presence rather than class hierarchy. We could add ``Transport`` as a
    base class for documentation, but doing so would force a runtime import
    cycle (transport.base imports from infra.errors, infra.errors does not
    import from transport, and we want to keep it that way).
    """

    name: Literal["raw_http"] = "raw_http"

    def api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None,
        method: str,
        api_version: str,
        timeout: int,
    ) -> GeminiResponse:
        """Forward an authenticated REST call to the urllib client.

        Every argument flows through unchanged — this method exists purely
        to satisfy the Transport Protocol shape so the coordinator can
        polymorphically dispatch into either backend.

        Args:
            endpoint: REST path relative to ``BASE_URL`` (e.g.
                ``"models/gemini-2.5-flash:generateContent"``).
            body: JSON-serializable request body, or ``None`` for GET.
            method: HTTP verb (``"GET"`` or ``"POST"``).
            api_version: API version segment (``"v1"`` or ``"v1beta"``).
            timeout: Request timeout in seconds.

        Returns:
            The parsed JSON response as a ``GeminiResponse`` dict.

        Raises:
            APIError: Bubbled up from the underlying client on HTTP
                failures, network errors, or SSL issues.
        """
        # return-value: client.py returns ``dict[str, Any]``; we re-type as
        # the precise GeminiResponse TypedDict at the Protocol boundary.
        return _client_api_call(  # type: ignore[return-value]
            endpoint=endpoint,
            # arg-type: client.py declares ``body: dict[str, Any] | None``
            # so passing a ``Mapping[str, object]`` triggers an arg-type
            # error. Legacy signature debt — left until a later cleanup.
            body=body,  # type: ignore[arg-type]
            method=method,
            api_version=api_version,
            timeout=timeout,
        )

    def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str,
        timeout: int,
    ) -> Iterator[StreamChunk]:
        """Yield streaming response chunks from the urllib client.

        Args:
            model: Gemini model name (e.g. ``"gemini-2.5-flash"``).
            body: JSON request body — must include ``contents``.
            api_version: API version segment.
            timeout: Request timeout in seconds.

        Yields:
            Parsed JSON chunks shaped like ``StreamChunk``.
        """
        # ``yield from`` propagates StopIteration cleanly and lets the caller
        # treat the result as any other iterator without a wrapper layer.
        # The type-ignore is narrow: client.py's underlying generator is
        # typed as ``Generator[dict[str, Any], None, None]`` (legacy debt),
        # which mypy cannot prove satisfies ``Iterator[StreamChunk]``.
        yield from _client_stream_generate_content(  # type: ignore[misc]
            model=model,
            # body: client.py declares ``dict[str, Any]`` so passing a
            # ``Mapping[str, object]`` triggers an arg-type error until the
            # legacy signature is tightened in a later cleanup pass.
            body=body,  # type: ignore[arg-type]
            api_version=api_version,
            timeout=timeout,
        )

    def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None,
        timeout: int,
    ) -> FileMetadata:
        """Forward a multipart file upload to the urllib client.

        Args:
            file_path: Path to the file on disk. Accepts ``str`` or
                ``Path`` because the underlying client coerces to
                ``Path`` internally.
            mime_type: MIME type string. Validated for CRLF injection
                inside the underlying client.
            display_name: Optional display name shown by the Files API.
            timeout: Request timeout in seconds (default 120 in client).

        Returns:
            A ``FileMetadata`` dict mirroring the Files API JSON envelope.

        Raises:
            ValueError: If ``mime_type`` contains unsafe characters.
            APIError: Bubbled up from the underlying client on HTTP
                failures.
        """
        # return-value: client.py returns ``dict[str, Any]``; we re-type as
        # the precise FileMetadata TypedDict at the Protocol boundary.
        return _client_upload_file(  # type: ignore[return-value]
            # arg-type: client.py declares ``file_path: Path`` so a
            # ``str`` triggers an arg-type error even though the function
            # body coerces via ``Path(file_path)``. Legacy signature debt.
            file_path=file_path,  # type: ignore[arg-type]
            mime_type=mime_type,
            display_name=display_name,
            timeout=timeout,
        )
