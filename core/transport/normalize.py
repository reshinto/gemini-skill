"""SDK response → REST envelope translation.

The google-genai SDK exposes responses as pydantic models with snake_case
field names (e.g. ``response.usage_metadata.total_token_count``). The skill's
existing adapter helpers in ``core/adapter/helpers.py`` and every adapter
under ``adapters/`` consume the **REST v1beta** envelope shape with
camelCase field names (e.g. ``response["usageMetadata"]["totalTokenCount"]``).

This module bridges the two without forcing every adapter to learn the SDK's
type system. Both transports (raw HTTP and SDK) emit the same camelCase dict
shape, and the coordinator never has to translate at the call site.

Architectural decision (see the dual-backend refactor plan, "Normalize layer
hardening" section): we deliberately do NOT rely on
``model_dump(by_alias=True)`` to emit camelCase. Pydantic's alias coverage is
inconsistent across nested google-genai types — some models declare
``Field(..., alias='camelCase')`` and some don't. Trusting the alias mode
would mean shape drift slips into production whenever the SDK adds a new
field without an alias.

Instead we walk the dict produced by ``model_dump(exclude_none=True)``
(snake_case throughout) and translate keys via an explicit, hand-maintained
``_SNAKE_TO_CAMEL`` mapping table. Every translation has a corresponding
test row in ``tests/transport/test_normalize.py``, so adding a new field is
a deliberate three-line change: extend the table, add a test, regenerate
fixtures.

What you'll learn from this file:
    - **Why explicit mapping beats clever serialization**: a literal dict
      lookup is impossible to mis-parse, easy to grep, and trivially
      testable. Implicit alias machinery is none of those things.
    - **Recursive dict transformation in Python**: walk the structure,
      branch on ``isinstance(value, (dict, list))``, recurse into nested
      collections, return primitives unchanged. The pattern generalizes to
      any "translate one tree shape to another" problem.

Dependencies: core/transport/base.py (GeminiResponse, FileMetadata, StreamChunk).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from core.transport.base import FileMetadata, GeminiResponse, StreamChunk

# ---------------------------------------------------------------------------
# snake_case → camelCase translation table
# ---------------------------------------------------------------------------
#
# This table is the **canonical source of truth** for how SDK field names map
# onto the REST envelope keys the adapters expect. Maintenance rules:
#
# 1. Every entry has at least one assertion in
#    ``tests/transport/test_normalize.py::TestSnakeToCamelMapping``.
# 2. Adding a new field requires editing this table AND adding a test row.
# 3. Removing an entry requires confirming no adapter or helper still reads
#    the camelCase key (grep the codebase first).
# 4. The table is alphabetized within each logical group for ease of review.
#
# Generated from the pinned ``google-genai==1.33.0`` by walking the
# ``GenerateContentResponse``, ``File``, and related pydantic models and
# inspecting their actual field names.

_SNAKE_TO_CAMEL: Mapping[str, str] = {
    # --- Candidate / content / parts ---
    "code_execution_result": "codeExecutionResult",
    "executable_code": "executableCode",
    "finish_reason": "finishReason",
    "function_call": "functionCall",
    "function_response": "functionResponse",
    "inline_data": "inlineData",
    "mime_type": "mimeType",
    "safety_ratings": "safetyRatings",
    # --- Usage metadata ---
    "cached_content_token_count": "cachedContentTokenCount",
    "candidates_token_count": "candidatesTokenCount",
    "prompt_token_count": "promptTokenCount",
    "total_token_count": "totalTokenCount",
    # countTokens response: the SDK returns ``total_tokens`` at the top
    # level (not ``total_token_count``), but the raw HTTP backend echoes
    # the REST envelope key ``totalTokens``. Both must end up at the same
    # camelCase key so adapters reading ``response["totalTokens"]`` work
    # under either backend.
    "total_tokens": "totalTokens",
    "usage_metadata": "usageMetadata",
    # --- Prompt feedback (top-level safety verdict on the user prompt) ---
    "block_reason": "blockReason",
    "prompt_feedback": "promptFeedback",
    # --- Grounding metadata (search / maps / file-search results) ---
    "grounding_chunks": "groundingChunks",
    "grounding_metadata": "groundingMetadata",
    "rendered_content": "renderedContent",
    "retrieved_context": "retrievedContext",
    "search_entry_point": "searchEntryPoint",
    "web_search_queries": "webSearchQueries",
    # --- File metadata (Files API) ---
    "create_time": "createTime",
    "display_name": "displayName",
    "expiration_time": "expirationTime",
    "sha256_hash": "sha256Hash",
    "size_bytes": "sizeBytes",
    "update_time": "updateTime",
}


def _translate_keys(value: object) -> object:
    """Recursively walk a JSON-ish structure renaming dict keys.

    Any key found in ``_SNAKE_TO_CAMEL`` is replaced with its camelCase
    counterpart. Keys not in the table pass through unchanged — this lets
    already-camelCase responses (from the raw HTTP backend, for example)
    flow through this function as a no-op so both transports can share the
    same downstream code paths without an isinstance branch.

    Args:
        value: A dict, list, or primitive. ``dict`` values are recursed
            into and their keys translated. ``list`` values are recursed
            into element-by-element. Everything else (str, int, float,
            bool, None, bytes) is returned unchanged.

    Returns:
        A structurally-identical copy of ``value`` with translated keys.
        The function never mutates its input — always returns a fresh
        container so callers can hold both shapes for comparison if needed.
    """
    if isinstance(value, dict):
        # Build a fresh dict so the caller's input is not mutated. The
        # ``.get(k, k)`` pattern means "look up k in the table; if missing,
        # use k itself" — a one-line idiom for "rename if known else keep".
        translated: dict[str, object] = {}
        for k, v in value.items():
            new_key = _SNAKE_TO_CAMEL.get(k, k)
            translated[new_key] = _translate_keys(v)
        return translated

    if isinstance(value, list):
        # Recurse into each element. List-of-primitives just round-trips,
        # list-of-dicts gets translated element-wise.
        return [_translate_keys(item) for item in value]

    # Primitive: return as-is. ``str``, ``int``, ``float``, ``bool``,
    # ``None``, ``bytes`` all reach this branch.
    return value


def _validate_envelope(envelope: object) -> None:
    """Sanity-check that an object looks like a GeminiResponse envelope.

    This guard is **opt-in**: none of the public translators
    (``sdk_response_to_rest_envelope``, ``sdk_stream_chunk_to_envelope``,
    ``sdk_file_to_metadata``) call it on the hot path. Callers that want
    drift detection in CI should invoke it explicitly inside a debug
    wrapper or behind a ``GEMINI_DEBUG_VALIDATE_ENVELOPE`` env-var check.
    Wiring it into the hot path is intentionally left to a later commit
    so the cost is opt-in rather than paid by every production request.

    This is a lightweight runtime guard — NOT a full schema validator. It
    catches the two failure modes that matter at the transport boundary:

    1. Someone passed a non-dict (e.g. a list, a string, a Mock that
       slipped through). This means the SDK shape changed in a way the
       translator can't handle.
    2. ``candidates`` is present but is not a list. Adapters call
       ``response["candidates"][0]`` and would crash with a confusing
       ``TypeError`` deep in helpers.py if this slipped through.

    Args:
        envelope: The object to validate. Expected to be a translated
            ``GeminiResponse`` dict.

    Raises:
        TypeError: If ``envelope`` is not a dict, or if ``candidates`` is
            present but not a list.
    """
    if not isinstance(envelope, dict):
        raise TypeError(
            f"Expected a dict-shaped GeminiResponse envelope, got {type(envelope).__name__}"
        )
    if "candidates" in envelope and not isinstance(envelope["candidates"], list):
        raise TypeError(
            f"Envelope 'candidates' must be a list, got {type(envelope['candidates']).__name__}"
        )


def _model_dump_or_raise(sdk_obj: object) -> dict[str, object]:
    """Coerce a pydantic-shaped SDK object into a dict via ``model_dump``.

    Centralized so all three public translators (``sdk_response_to_rest_envelope``,
    ``sdk_stream_chunk_to_envelope``, ``sdk_file_to_metadata``) raise the same
    ``TypeError`` shape when handed something the normalize layer cannot
    process. This gives the SDK transport a single error surface to catch
    and re-wrap.

    Args:
        sdk_obj: An object expected to expose a ``model_dump`` method
            (every pydantic model does).

    Returns:
        The dict produced by ``sdk_obj.model_dump(exclude_none=True)``.

    Raises:
        TypeError: If ``sdk_obj`` does not have a callable ``model_dump``
            attribute. The error message starts with ``"Cannot normalize"``
            so callers can match on it.
    """
    model_dump = getattr(sdk_obj, "model_dump", None)
    if not callable(model_dump):
        raise TypeError(
            f"Cannot normalize {type(sdk_obj).__name__}: object has no callable model_dump()"
        )
    return cast(dict[str, object], model_dump(exclude_none=True))


def sdk_response_to_rest_envelope(sdk_obj: object) -> GeminiResponse:
    """Translate a google-genai SDK response into the REST envelope dict.

    This is the public entrypoint the SDK transport calls after every
    ``client.models.generate_content(...)`` (and similar) invocation. The
    returned dict is structurally identical to what
    ``RawHttpTransport.api_call`` produces, so adapters never have to
    branch on which backend ran the call.

    Args:
        sdk_obj: A pydantic-based SDK response object (e.g.
            ``google.genai.types.GenerateContentResponse``). Must expose
            a ``model_dump`` method — which every pydantic model does.

    Returns:
        A ``GeminiResponse`` TypedDict (a regular dict at runtime) whose
        keys have been translated from snake_case to camelCase per
        ``_SNAKE_TO_CAMEL``.

    Raises:
        TypeError: If ``sdk_obj`` is not pydantic-shaped.

    Example:
        >>> from unittest.mock import MagicMock
        >>> sdk_obj = MagicMock()
        >>> sdk_obj.model_dump.return_value = {"usage_metadata": {"total_token_count": 5}}
        >>> envelope = sdk_response_to_rest_envelope(sdk_obj)
        >>> envelope["usageMetadata"]["totalTokenCount"]
        5
    """
    raw = _model_dump_or_raise(sdk_obj)
    translated = _translate_keys(raw)
    # _translate_keys returns ``object`` because it walks arbitrary structures.
    # We cast back to the typed envelope here so callers see the precise type.
    return cast(GeminiResponse, translated)


def sdk_stream_chunk_to_envelope(sdk_obj: object) -> StreamChunk:
    """Translate one streaming SDK chunk into a StreamChunk dict.

    Streaming chunks share the same shape as full responses (Gemini ships
    partial envelopes per SSE chunk rather than a separate streaming
    protocol), so this is a thin alias around the response translator —
    kept as a separate function name for call-site clarity at the
    SDK-transport boundary.

    Args:
        sdk_obj: A streaming chunk pydantic object.

    Returns:
        A ``StreamChunk`` TypedDict.

    Raises:
        TypeError: If ``sdk_obj`` is not pydantic-shaped.
    """
    # StreamChunk is a structural alias for GeminiResponse — at runtime they
    # are the same dict shape, so we route through the response translator
    # and re-cast for the stream-specific type signature.
    raw = _model_dump_or_raise(sdk_obj)
    translated = _translate_keys(raw)
    return cast(StreamChunk, translated)


def sdk_file_to_metadata(sdk_file: object) -> FileMetadata:
    """Translate an SDK ``File`` object into the FileMetadata dict.

    Used by the SDK transport's ``upload_file`` to flatten the SDK's
    ``google.genai.types.File`` pydantic model into the same shape the
    raw HTTP backend's multipart upload returns.

    Args:
        sdk_file: A pydantic File object from
            ``client.files.upload(...)``.

    Returns:
        A ``FileMetadata`` TypedDict with camelCase keys.

    Raises:
        TypeError: If ``sdk_file`` is not pydantic-shaped.
    """
    raw = _model_dump_or_raise(sdk_file)
    translated = _translate_keys(raw)
    return cast(FileMetadata, translated)
