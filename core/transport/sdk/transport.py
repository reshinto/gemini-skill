"""SdkTransport — google-genai SDK backend implementing the Transport protocol.

This module is the **SDK side** of the dual-backend transport layer. It
translates the legacy REST-shaped endpoint strings the adapters use (e.g.
``models/gemini-2.5-flash:generateContent``) into google-genai SDK method
calls (e.g. ``client.models.generate_content``) and normalizes the SDK's
pydantic responses back into the camelCase REST envelope dict shape so
adapters never notice which backend ran the call.

Architectural notes:

1. **Capability registry, not heuristics.** The class carries an explicit
   ``_SUPPORTED_CAPABILITIES`` frozenset that lists every capability the SDK
   is *known* to handle at the pinned ``google-genai==1.33.0`` version. The
   coordinator (Phase 3) consults ``primary.supports(capability)`` BEFORE
   dispatching, so the SDK transport is never asked to handle a capability
   it doesn't claim. This replaces the earlier "try SDK and catch
   AttributeError" heuristic, which was rejected during architect review:
   string-matching on exception messages is too fragile and would silently
   swallow legitimate bugs.

2. **Endpoint string is the dispatch key.** The transport never sees the
   capability name — only the endpoint path the adapter passed to
   ``api_call``. Two capabilities can map to the same endpoint shape
   (``text`` and ``maps`` both POST ``models/{model}:generateContent``);
   the coordinator's capability gate is what decides which one reaches the
   SDK transport.

3. **Stateless.** ``SdkTransport`` holds no instance state — every method
   reaches for the cached client via ``client_factory.get_client()`` so the
   class is safe to instantiate freely (used by the coordinator factory and
   by tests).

What you'll learn from this file:
    - **Protocol implementation by structural typing**: ``SdkTransport`` does
      not inherit from ``Transport``. It only needs to expose the right
      method names and a ``name`` class attribute. ``isinstance(obj,
      Transport)`` returns True purely because the shape matches — that's
      PEP 544 in action.
    - **`frozenset` for read-only registries**: a frozenset is an immutable
      set with O(1) membership tests. Perfect for "is X in this fixed list
      of allowed values" checks where mutation would be a bug.
    - **`ClassVar` annotations**: marks a class attribute as belonging to
      the class itself, not to instances. Required by mypy --strict to
      distinguish a class-level constant from a per-instance field.

Dependencies: core/transport/base.py (Transport protocol),
core/transport/sdk/client_factory.py (cached genai.Client).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import ClassVar, Literal

from core.transport.base import FileMetadata, GeminiResponse, StreamChunk


class SdkTransport:
    """google-genai SDK backend implementing the ``Transport`` protocol.

    The class is intentionally minimal — every operation flows through
    ``client_factory.get_client()`` so there is no instance state to
    manage. The Transport protocol is satisfied structurally; no explicit
    inheritance is needed.

    Attributes:
        name: Always ``"sdk"``. Used by the coordinator's logging and by
            tests that assert which backend handled a call.
    """

    # ``ClassVar`` tells mypy this attribute belongs to the class, not to
    # instances. Without it, mypy --strict flags ``name: Literal["sdk"]``
    # as a per-instance annotation that lacks a default, which would be a
    # type error. The Literal narrowing means callers can pattern-match
    # on the value with exhaustiveness checking.
    name: ClassVar[Literal["sdk"]] = "sdk"

    # Capabilities the SDK is KNOWN to support at google-genai==1.33.0.
    # Updated when the pinned version is bumped and the parity audit is
    # re-run. Keys must match the dispatch capability names used in
    # core/cli/dispatch.py and registry/capabilities.json.
    #
    # Capabilities NOT in this set are handled by the raw HTTP backend
    # without any SDK probe. This is the deterministic-routing contract
    # the architect review locked in (see the canonical plan, "Explicit
    # capability registration" section).
    _SUPPORTED_CAPABILITIES: ClassVar[frozenset[str]] = frozenset(
        {
            # --- Generation ---
            "text",
            "structured",
            "multimodal",
            "streaming",
            # --- Counting / embeddings ---
            "embed",
            "token_count",
            # --- Tools (only those whose Tool class exists in the pinned SDK) ---
            "function_calling",
            "code_exec",
            "search",
            # --- Media generation ---
            "image_gen",
            "video_gen",
            # --- Data plane ---
            "files",
            "cache",
            "batch",
            # --- Long-running ---
            "deep_research",
            # NOT included (route to raw HTTP via coordinator deterministic fallback):
            #   "maps"          — no GoogleMaps tool class in 1.33.0
            #   "music_gen"     — no Lyria surface in 1.33.0
            #   "computer_use"  — no ComputerUse tool class in 1.33.0
            #   "file_search"   — no client.file_search_stores in 1.33.0
        }
    )

    def supports(self, capability: str) -> bool:
        """Return True iff the SDK is known to handle this capability.

        The coordinator calls this BEFORE dispatching any operation. A
        ``False`` return triggers deterministic routing to the fallback
        backend without any SDK probe — no try/except, no exception
        handling, no log noise. This is the layering rule that makes the
        coordinator's behavior predictable.

        Args:
            capability: The capability name from the dispatch layer
                (e.g. ``"text"``, ``"image_gen"``, ``"file_search"``).
                Unknown names return False (closed-world default).

        Returns:
            True if ``capability`` is in ``_SUPPORTED_CAPABILITIES``,
            False otherwise (including unknown capability names).
        """
        # Access the registry through the class object, not ``self``. The
        # frozenset is a class-level constant; going through ``self`` would
        # make a future subclass that shadows the attribute silently bypass
        # the contract this method enforces. Class-direct access also
        # mirrors the canonical plan's pseudocode verbatim.
        return capability in SdkTransport._SUPPORTED_CAPABILITIES

    # ------------------------------------------------------------------
    # Transport protocol methods (stubs filled in by Phase 2 slices 2b/2c)
    # ------------------------------------------------------------------
    #
    # These three methods exist so the class structurally satisfies the
    # ``Transport`` Protocol — ``isinstance(SdkTransport(), Transport)``
    # must return True for the coordinator's tests to pass. The bodies
    # raise ``NotImplementedError`` until subsequent slices fill them in;
    # callers that hit a stub will see a clear "not implemented yet" trace
    # rather than a confusing AttributeError.

    def api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        method: str = "POST",
        api_version: str = "v1beta",
        timeout: int = 30,
    ) -> GeminiResponse:
        """Dispatch a REST-shaped endpoint call into the SDK. (slice 2b)"""
        raise NotImplementedError("SdkTransport.api_call lands in Phase 2 slice 2b")

    def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str = "v1beta",
        timeout: int = 30,
    ) -> Iterator[StreamChunk]:
        """Stream chunks from generate_content_stream. (slice 2c)"""
        raise NotImplementedError("SdkTransport.stream_generate_content lands in Phase 2 slice 2c")

    def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None = None,
        timeout: int = 120,
    ) -> FileMetadata:
        """Upload a file via client.files.upload. (slice 2c)"""
        raise NotImplementedError("SdkTransport.upload_file lands in Phase 2 slice 2c")
