"""Shared types, Protocols, and exceptions for the dual-backend transport layer.

This module is the **layering linchpin** of the transport package. It holds:

1. ``BackendUnavailableError`` — raised when a backend cannot start at all
   (SDK not importable, requested capability not implemented).
2. ``Transport`` / ``AsyncTransport`` runtime-checkable Protocols — the
   structural contract every backend must satisfy. ``isinstance(obj, Transport)``
   returns True for any object that exposes the right method names; there is
   no explicit subclassing required.
3. ``GeminiResponse`` / ``StreamChunk`` / ``FileMetadata`` TypedDicts — the
   normalized REST envelope shape that flows out of every backend so adapters
   stay backend-agnostic. At runtime these are plain ``dict`` subclasses;
   the TypedDict declarations exist so ``mypy --strict`` can type-check the
   keys without any third-party validation library.

Why does ``BackendUnavailableError`` live here instead of
``core/infra/errors.py``? Layering. ``core/infra`` is the foundation layer
and must not depend on transport semantics — the transport layer is *above*
infra. Putting the error here keeps the dependency arrow pointing from
transport → infra, never the reverse. ``BackendUnavailableError`` still
inherits from ``GeminiSkillError`` so callers can catch the base class
without knowing about transport at all.

What you'll learn from this file:
    - **Protocol** is Python's structural-typing primitive (PEP 544). Unlike
      a normal base class, an object satisfies a Protocol just by having the
      right methods — no inheritance needed. Marking a Protocol with
      ``@runtime_checkable`` lets ``isinstance()`` perform the same check at
      runtime, which is what the coordinator's tests rely on.
    - **TypedDict** (PEP 589) is how Python types dict shapes. ``total=False``
      means every key is optional — the right choice for response envelopes
      because Gemini omits empty fields.
    - How to extend an exception hierarchy across packages without circular
      imports — define new exceptions in the layer that introduces the
      concept, not in the layer that owns the base class.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from pathlib import Path
from typing import Literal, Protocol, TypedDict, runtime_checkable

from core.infra.errors import GeminiSkillError


class BackendUnavailableError(GeminiSkillError):
    """A transport backend cannot be used at this moment.

    Raised when:
    - The google-genai SDK is not importable in the active venv.
    - A backend object cannot be constructed (e.g. missing credentials).
    - The coordinator was asked for an async path but only a sync backend
      is configured.
    - A capability is not implemented by the requested backend AND no
      fallback is available.

    The coordinator treats this exception as fallback-eligible: if the
    primary backend raises it, the coordinator will try the fallback
    backend before surfacing the failure.

    Inherits from ``GeminiSkillError`` (not directly from ``Exception``) so
    catch-all handlers at the CLI boundary catch it alongside every other
    skill error without needing to know about transport-layer details.
    """


# ---------------------------------------------------------------------------
# Normalized REST envelope TypedDicts
# ---------------------------------------------------------------------------
#
# These mirror the v1beta REST shape that ``core/adapter/helpers.py`` already
# expects (e.g. ``response["candidates"][0]["content"]["parts"][0]["text"]``).
# Both backends emit these dicts so the helpers and adapters never need to
# know which backend ran the call.
#
# Every field is ``total=False`` because Gemini omits empty fields from
# responses — declaring fields as required would force every test fixture
# to include keys the real API doesn't always send.


class InlineData(TypedDict, total=False):
    """A base64-encoded inline blob — used for inline images, audio, video."""

    mimeType: str
    data: str


class FunctionCall(TypedDict, total=False):
    """A model-emitted function call awaiting a client-side response."""

    name: str
    args: Mapping[str, object]


class FunctionResponse(TypedDict, total=False):
    """A client-side function response fed back to the model."""

    name: str
    response: Mapping[str, object]


class ExecutableCode(TypedDict, total=False):
    """A model-emitted code block produced by the code-execution tool."""

    language: str
    code: str


class CodeExecutionResult(TypedDict, total=False):
    """The outcome of running a model-emitted code block."""

    outcome: str
    output: str


class Part(TypedDict, total=False):
    """One element of a Content's parts list. At most one of the variant
    keys is set in a real response, but TypedDict cannot model that
    constraint — the adapters check which key is present at runtime."""

    text: str
    inlineData: InlineData
    functionCall: FunctionCall
    functionResponse: FunctionResponse
    executableCode: ExecutableCode
    codeExecutionResult: CodeExecutionResult


class Content(TypedDict, total=False):
    """A single conversational turn — either user input or model output."""

    role: Literal["user", "model"]
    parts: list[Part]


class SafetyRating(TypedDict, total=False):
    """One safety category's verdict for a candidate or prompt."""

    category: str
    probability: str
    blocked: bool


class GroundingChunk(TypedDict, total=False):
    """One source the model grounded its answer on (search / maps / files)."""

    web: Mapping[str, object]
    retrievedContext: Mapping[str, object]


class SearchEntryPoint(TypedDict, total=False):
    """The renderable HTML widget Google requires you to display whenever
    search-grounding results are surfaced. ``renderedContent`` holds the
    HTML snippet itself.

    A separate TypedDict (rather than ``Mapping[str, object]``) so the
    ``rendered_content`` → ``renderedContent`` translation in
    ``core/transport/normalize.py`` has a typed home and mypy can catch
    field drift if Google adds or renames a key."""

    renderedContent: str
    sdkBlob: str


class GroundingMetadata(TypedDict, total=False):
    """Grounding evidence returned alongside a candidate when search /
    maps / file-search tools were active."""

    webSearchQueries: list[str]
    groundingChunks: list[GroundingChunk]
    searchEntryPoint: SearchEntryPoint


class Candidate(TypedDict, total=False):
    """One candidate completion produced by the model."""

    content: Content
    finishReason: str
    safetyRatings: list[SafetyRating]
    groundingMetadata: GroundingMetadata
    index: int


class UsageMetadata(TypedDict, total=False):
    """Token accounting attached to every successful generateContent call."""

    promptTokenCount: int
    candidatesTokenCount: int
    totalTokenCount: int
    cachedContentTokenCount: int


class PromptFeedback(TypedDict, total=False):
    """Safety verdict on the user's prompt (separate from candidate ratings)."""

    blockReason: str
    safetyRatings: list[SafetyRating]


class GeminiResponse(TypedDict, total=False):
    """The normalized REST envelope every backend produces for non-streaming
    calls. Adapters consume this shape directly via ``extract_text`` /
    ``extract_parts`` helpers in ``core/adapter/helpers.py``."""

    candidates: list[Candidate]
    usageMetadata: UsageMetadata
    promptFeedback: PromptFeedback


class StreamChunk(GeminiResponse):
    """One SSE chunk yielded by streamGenerateContent. Same shape as
    ``GeminiResponse`` because Gemini ships partial envelopes per chunk
    rather than a separate streaming protocol."""


class FileMetadata(TypedDict, total=False):
    """The Files API response shape — returned by upload, list, and get."""

    name: str
    displayName: str
    mimeType: str
    sizeBytes: str
    createTime: str
    updateTime: str
    expirationTime: str
    sha256Hash: str
    uri: str
    state: str


# ---------------------------------------------------------------------------
# Transport Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Transport(Protocol):
    """Structural contract every synchronous backend must satisfy.

    A backend is ANY object exposing these three methods plus a ``name``
    attribute. There is no required base class — Python's
    ``@runtime_checkable`` decorator lets ``isinstance(obj, Transport)``
    confirm the structural fit at runtime, which is what the coordinator
    factory relies on when wiring up primary / fallback.

    The ``name`` literal lets the coordinator log which backend handled a
    call without depending on ``type(obj).__name__`` (which would break if
    a future backend wrapped another for instrumentation).
    """

    name: Literal["sdk", "raw_http"]

    def api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None,
        method: str,
        api_version: str,
        timeout: int,
    ) -> GeminiResponse: ...

    def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str,
        timeout: int,
    ) -> Iterator[StreamChunk]: ...

    def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None,
        timeout: int,
    ) -> FileMetadata: ...


@runtime_checkable
class AsyncTransport(Protocol):
    """Async mirror of ``Transport``. Only the SDK backend implements this;
    the raw HTTP backend is intentionally sync-only because urllib does not
    have a first-class async API and the Live API (the only async-mandatory
    capability) is SDK-only anyway.
    """

    name: Literal["sdk"]

    async def api_call(
        self,
        endpoint: str,
        body: Mapping[str, object] | None,
        method: str,
        api_version: str,
        timeout: int,
    ) -> GeminiResponse: ...

    # NOTE: declared as an ``async def`` returning ``AsyncIterator`` (rather
    # than a plain ``def`` returning the same) so ``isinstance`` Protocol
    # conformance enforces an async-callable shape — a sync generator that
    # happens to satisfy ``AsyncIterator`` typing would be a contract bug
    # and we want the structural check to catch it.
    async def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str,
        timeout: int,
    ) -> AsyncIterator[StreamChunk]: ...

    async def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None,
        timeout: int,
    ) -> FileMetadata: ...
