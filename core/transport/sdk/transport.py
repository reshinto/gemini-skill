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
from typing import ClassVar, Literal, cast

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
from core.transport._validation import validate_mime_type, validate_no_crlf
from core.transport.sdk.client_factory import get_client


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
            # NOT included (route to raw HTTP via coordinator deterministic fallback):
            #   "maps"          — no GoogleMaps tool class in 1.33.0
            #   "music_gen"     — no Lyria surface in 1.33.0
            #   "computer_use"  — no ComputerUse tool class in 1.33.0
            #   "file_search"   — no client.file_search_stores in 1.33.0
            #   "deep_research" — no client.interactions namespace in 1.33.0
            #     (the canonical plan's parity audit was wrong about this;
            #     verified directly against the installed pinned SDK)
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
        """Translate a legacy REST endpoint string into a google-genai SDK call.

        This is the dispatch core. The ``endpoint`` string follows the same
        shape adapters pass to the raw HTTP backend, so the same call sites
        work with either transport behind the coordinator. Three shape
        families are recognized:

        1. **Action endpoints** containing a colon, e.g.
           ``models/gemini-2.5-flash:generateContent`` or
           ``batchJobs/{name}:cancel``. The substring after the colon names
           the SDK method to dispatch to.
        2. **Collection endpoints** with no slash, e.g. ``files`` or
           ``cachedContents`` — POST means create, GET means list.
        3. **Resource endpoints** with one or more slashes, e.g.
           ``files/abc`` or ``operations/foo/bar`` — GET means get,
           DELETE means delete.

        Anything that doesn't match a known shape raises
        ``BackendUnavailableError`` so the coordinator routes the call to
        the raw HTTP fallback. We deliberately do NOT catch the SDK's own
        exceptions in this slice — that's slice 2d's job.

        Args:
            endpoint: The REST-shaped endpoint string (no leading slash,
                no api_version prefix — same as the raw HTTP backend
                accepts). Examples: ``"models/gemini:generateContent"``,
                ``"files"``, ``"files/abc"``, ``"batchJobs/abc:cancel"``.
            body: Request body dict in the legacy REST shape (camelCase
                top-level keys). May be ``None`` for GET / DELETE.
            method: HTTP method. Used only to disambiguate
                collection-vs-resource POST/GET/DELETE.
            api_version: Ignored — the SDK manages its own API version.
                Accepted for Transport-protocol shape compatibility.
            timeout: Ignored in this slice — see slice 2d for the SDK
                request_options timeout wiring.

        Returns:
            A GeminiResponse dict with camelCase keys, normalized via
            ``core.transport.normalize.sdk_response_to_rest_envelope``.

        Raises:
            BackendUnavailableError: If the endpoint shape is unrecognized,
                so the coordinator can fall back to raw HTTP.
        """
        client = get_client()
        method_upper = method.upper()
        body_dict: dict[str, object] = dict(body) if body is not None else {}

        # 1. Action endpoints (contain ':')
        if ":" in endpoint:
            return self._dispatch_action(client, endpoint, body_dict)

        # 2/3. CRUD endpoints — split into [collection, *path_tail]
        parts = endpoint.split("/")
        return self._dispatch_crud(client, parts, method_upper, body_dict)

    # ------------------------------------------------------------------
    # Dispatch helpers (private)
    # ------------------------------------------------------------------

    def _dispatch_action(
        self,
        client: object,
        endpoint: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        """Handle endpoints that contain ':' — typically ``X:action``."""
        path, _, action = endpoint.partition(":")

        # models/{model}:{action} — generation family
        if path.startswith("models/"):
            model = path[len("models/") :]
            return self._dispatch_model_action(client, model, action, body)

        # batchJobs/{name}:cancel — note that ``str.partition(":")`` returns
        # the substring BEFORE the separator, so ``path == "batchJobs/abc"``
        # already excludes the ":cancel" suffix and is the correct value to
        # pass as the SDK ``name=`` argument. A future refactor that switches
        # to ``endpoint.split(":", 1)[0]`` would also be correct, but a
        # naive ``endpoint.split(":")[0]`` would silently drop additional
        # colons in the resource ID — preserved by partition().
        if action == "cancel" and path.startswith("batchJobs/"):
            client.batches.cancel(name=path)  # type: ignore[attr-defined]
            return cast(GeminiResponse, {})

        raise BackendUnavailableError(
            f"SdkTransport: unknown action endpoint '{endpoint}'"
        )

    def _dispatch_model_action(
        self,
        client: object,
        model: str,
        action: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        """Handle ``models/{m}:{action}`` calls — the generate family.

        Each branch builds the right kwargs dict for the corresponding
        ``client.models.X`` method and normalizes the response.
        """
        if action == "generateContent":
            contents, config = self._build_generate_content_kwargs(body)
            sdk_resp = client.models.generate_content(  # type: ignore[attr-defined]
                model=model, contents=contents, config=config
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "countTokens":
            sdk_resp = client.models.count_tokens(  # type: ignore[attr-defined]
                model=model, contents=body.get("contents", [])
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "embedContent":
            # Legacy body uses singular ``content``; SDK takes plural ``contents``.
            contents = body.get("content") or body.get("contents")
            config = self._build_embed_content_config(body)
            sdk_resp = client.models.embed_content(  # type: ignore[attr-defined]
                model=model, contents=contents, config=config
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        if action == "predictLongRunning":
            # Veo video generation — body uses the vertex-style ``instances``
            # + ``parameters`` shape; SDK takes prompt + config separately.
            prompt = self._extract_video_prompt(body)
            sdk_resp = client.models.generate_videos(  # type: ignore[attr-defined]
                model=model, prompt=prompt
            )
            return sdk_response_to_rest_envelope(sdk_resp)

        raise BackendUnavailableError(
            f"SdkTransport: unknown model action '{action}' for model '{model}'"
        )

    def _dispatch_crud(
        self,
        client: object,
        parts: list[str],
        method: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        """Handle CRUD-style endpoints (no colon).

        ``parts[0]`` is the collection name. ``len(parts) > 1`` indicates
        the call targets a specific resource (the full endpoint string is
        used as the SDK ``name=`` argument because the SDK's resource
        identifiers include the collection prefix).
        """
        collection = parts[0]
        has_id = len(parts) > 1
        full_name = "/".join(parts)

        if collection == "files":
            return self._dispatch_files(client, has_id, full_name, method)
        if collection == "cachedContents":
            return self._dispatch_caches(client, has_id, full_name, method, body)
        if collection == "batchJobs":
            return self._dispatch_batches(client, has_id, full_name, method, body)
        if collection == "operations":
            if has_id and method == "GET":
                sdk_resp = client.operations.get(operation=full_name)  # type: ignore[attr-defined]
                return sdk_response_to_rest_envelope(sdk_resp)
            # Operations IS in the table — only the method/shape combo is
            # unsupported. Use a precise message so coordinator logs and
            # reviewers immediately see what's wrong instead of chasing a
            # misleading "collection not in dispatch table" string.
            raise BackendUnavailableError(
                f"SdkTransport: operations only supports GET on a resource id, "
                f"got {method} '{full_name}'"
            )

        raise BackendUnavailableError(
            f"SdkTransport: unknown {method} endpoint '{full_name}' "
            f"(collection '{collection}' not in dispatch table)"
        )

    def _dispatch_files(
        self,
        client: object,
        has_id: bool,
        full_name: str,
        method: str,
    ) -> GeminiResponse:
        if not has_id and method == "GET":
            items = client.files.list()  # type: ignore[attr-defined]
            return self._wrap_collection("files", items)
        if has_id and method == "GET":
            sdk_resp = client.files.get(name=full_name)  # type: ignore[attr-defined]
            return sdk_response_to_rest_envelope(sdk_resp)
        if has_id and method == "DELETE":
            client.files.delete(name=full_name)  # type: ignore[attr-defined]
            return cast(GeminiResponse, {})
        raise BackendUnavailableError(
            f"SdkTransport: unsupported files {method} on '{full_name}'"
        )

    def _dispatch_caches(
        self,
        client: object,
        has_id: bool,
        full_name: str,
        method: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        if not has_id and method == "POST":
            # caches.create takes model + config separately. Build a
            # CreateCachedContentConfig from the rest of the body so
            # camelCase aliases (ttl, contents, systemInstruction, …) are
            # accepted directly. The body's ``model`` key is consumed
            # separately and removed from the config dict.
            from google.genai import types

            cfg_dict = {k: v for k, v in body.items() if k != "model"}
            cfg = types.CreateCachedContentConfig.model_validate(cfg_dict)
            sdk_resp = client.caches.create(  # type: ignore[attr-defined]
                model=body.get("model"), config=cfg
            )
            return sdk_response_to_rest_envelope(sdk_resp)
        if not has_id and method == "GET":
            items = client.caches.list()  # type: ignore[attr-defined]
            return self._wrap_collection("cachedContents", items)
        if has_id and method == "GET":
            sdk_resp = client.caches.get(name=full_name)  # type: ignore[attr-defined]
            return sdk_response_to_rest_envelope(sdk_resp)
        if has_id and method == "DELETE":
            client.caches.delete(name=full_name)  # type: ignore[attr-defined]
            return cast(GeminiResponse, {})
        raise BackendUnavailableError(
            f"SdkTransport: unsupported cachedContents {method} on '{full_name}'"
        )

    def _dispatch_batches(
        self,
        client: object,
        has_id: bool,
        full_name: str,
        method: str,
        body: dict[str, object],
    ) -> GeminiResponse:
        if not has_id and method == "POST":
            sdk_resp = client.batches.create(  # type: ignore[attr-defined]
                model=body.get("model"), src=body.get("src")
            )
            return sdk_response_to_rest_envelope(sdk_resp)
        if not has_id and method == "GET":
            items = client.batches.list()  # type: ignore[attr-defined]
            return self._wrap_collection("batchJobs", items)
        if has_id and method == "GET":
            sdk_resp = client.batches.get(name=full_name)  # type: ignore[attr-defined]
            return sdk_response_to_rest_envelope(sdk_resp)
        raise BackendUnavailableError(
            f"SdkTransport: unsupported batchJobs {method} on '{full_name}'"
        )

    # ------------------------------------------------------------------
    # Body translation helpers
    # ------------------------------------------------------------------

    def _build_generate_content_kwargs(
        self, body: dict[str, object]
    ) -> tuple[object, object | None]:
        """Translate a legacy generateContent body into (contents, config).

        The legacy body uses camelCase top-level keys. google-genai's
        ``GenerateContentConfig`` declares aliases for every camelCase
        REST field (verified at the pinned 1.33.0 version), so we can
        ``model_validate(camelCase_dict)`` directly — pydantic accepts
        either form because the model has ``populate_by_name=True``.

        The four top-level *sibling* keys (``systemInstruction``, ``tools``,
        ``safetySettings``, ``cachedContent``) plus the nested
        ``generationConfig`` dict are folded into a single dict before
        validation because the SDK puts them all on ``GenerateContentConfig``.
        """
        contents = body.get("contents", [])

        # Start from the nested generationConfig dict (if present) and
        # fold in the four sibling keys the SDK expects on the same config.
        cfg_dict: dict[str, object] = {}
        gen_cfg = body.get("generationConfig")
        if isinstance(gen_cfg, dict):
            cfg_dict.update(gen_cfg)
        for sibling in ("systemInstruction", "tools", "safetySettings", "cachedContent"):
            if sibling in body:
                cfg_dict[sibling] = body[sibling]

        if not cfg_dict:
            return contents, None

        # Lazy import — keeps the module importable without google-genai.
        from google.genai import types

        config = types.GenerateContentConfig.model_validate(cfg_dict)
        return contents, config

    def _build_embed_content_config(self, body: dict[str, object]) -> object | None:
        """Build an EmbedContentConfig from legacy body fields."""
        cfg_dict: dict[str, object] = {}
        if "outputDimensionality" in body:
            cfg_dict["outputDimensionality"] = body["outputDimensionality"]
        if "taskType" in body:
            cfg_dict["taskType"] = body["taskType"]
        if not cfg_dict:
            return None
        from google.genai import types

        return types.EmbedContentConfig.model_validate(cfg_dict)

    def _extract_video_prompt(self, body: dict[str, object]) -> str:
        """Extract the prompt string from a Veo predictLongRunning body.

        The vertex-style body shape is ``{"instances": [{"prompt": "..."}]}``,
        which the legacy adapter passes through unchanged.
        """
        instances = body.get("instances")
        if isinstance(instances, list) and instances:
            first = instances[0]
            if isinstance(first, dict):
                prompt = first.get("prompt")
                if isinstance(prompt, str):
                    return prompt
        # Fallback: top-level prompt key
        prompt = body.get("prompt")
        if isinstance(prompt, str):
            return prompt
        return ""

    def _wrap_collection(self, key: str, items: object) -> GeminiResponse:
        """Normalize a list-returning SDK call into ``{<key>: [<items>]}``.

        ``client.files.list()`` and friends return an iterable of pydantic
        File objects; the legacy raw HTTP backend returns
        ``{"files": [<dict>, ...]}``. This helper bridges the two shapes.
        """
        result: list[dict[str, object]] = []
        # Use hasattr() to check iterability instead of try/except TypeError
        # so a TypeError raised for ANOTHER reason (e.g. a future SDK signature
        # change inside the items object) propagates naturally instead of being
        # silently swallowed and returned as an empty list. The hasattr check
        # is exactly the contract Python uses internally to decide if iter()
        # will succeed for a non-builtin type.
        if not hasattr(items, "__iter__"):
            return cast(GeminiResponse, {key: []})
        # ``items`` is typed ``object`` for the lazy-import-friendliness
        # discussed at module top, but the hasattr() guard above proves
        # to the human reader that ``iter()`` will not raise here. mypy
        # cannot narrow object→Iterable from hasattr, so the call-overload
        # ignore below stays.
        iterator = iter(items)
        for item in iterator:
            envelope = sdk_response_to_rest_envelope(item)
            result.append(cast(dict[str, object], envelope))
        return cast(GeminiResponse, {key: result})

    def stream_generate_content(
        self,
        model: str,
        body: Mapping[str, object],
        api_version: str = "v1beta",
        timeout: int = 30,
    ) -> Iterator[StreamChunk]:
        """Yield normalized stream chunks from ``client.models.generate_content_stream``.

        Streaming uses the same body translation as ``api_call`` for
        ``generateContent`` — pulls ``contents`` and folds the rest of the
        body into a ``GenerateContentConfig``. Each chunk the SDK yields is
        a pydantic-shaped object with the same field surface as a full
        response, so we route every chunk through
        ``sdk_stream_chunk_to_envelope`` to land it in the camelCase REST
        envelope the adapter loop expects.

        Args:
            model: The Gemini model identifier (e.g. ``"gemini-2.5-flash"``).
                Passed straight through to the SDK as the ``model`` kwarg.
            body: Legacy REST-shaped request body. Same shape as the
                ``api_call`` body for ``generateContent``.
            api_version: Ignored — the SDK manages its own versioning.
                Accepted for Transport-protocol shape compatibility.
            timeout: Ignored in this slice — see slice 2d for the SDK
                request_options timeout wiring.

        Yields:
            ``StreamChunk`` dicts (one per SDK chunk) with camelCase keys.
            The generator runs to exhaustion when the SDK iterator stops.

        Raises:
            BackendUnavailableError: Propagated from ``get_client()`` if
                google-genai is not importable.
        """
        client = get_client()
        body_dict: dict[str, object] = dict(body)
        contents, config = self._build_generate_content_kwargs(body_dict)
        # The SDK call returns a generator; iterating it issues the HTTP
        # request and reads SSE chunks lazily. We forward each chunk through
        # the normalize translator one at a time so a slow consumer's
        # backpressure flows back to the SDK naturally.
        sdk_iterator = client.models.generate_content_stream(
            model=model, contents=contents, config=config
        )
        # Wrap iteration in try/finally so the SDK iterator is closed even
        # if the consumer breaks out of the loop early (timeout, exception,
        # GeneratorExit from the coordinator). CPython's reference counting
        # would close the iterator promptly anyway, but the explicit
        # ``close()`` call makes the lifecycle obvious and works on any
        # Python implementation. The guard around hasattr() keeps the
        # behavior safe for SDK iterators that don't implement close()
        # (older or mock objects).
        try:
            for chunk in sdk_iterator:
                yield sdk_stream_chunk_to_envelope(chunk)
        finally:
            close = getattr(sdk_iterator, "close", None)
            if callable(close):
                close()

    def upload_file(
        self,
        file_path: Path | str,
        mime_type: str,
        display_name: str | None = None,
        timeout: int = 120,
    ) -> FileMetadata:
        """Upload a file via ``client.files.upload`` and return its metadata.

        The SDK's ``files.upload`` accepts ``file=<path>`` plus a config
        dict carrying ``mime_type`` and ``display_name``. We deliberately
        validate the mime_type before reaching the SDK using the SAME
        regex the raw HTTP backend uses — defense in depth, identical
        sanitization on both backends so a CRLF injection cannot reach
        the wire on either path.

        Args:
            file_path: Path to the file to upload. Accepted as either a
                ``Path`` or a string for caller convenience; the SDK
                expects a string so we coerce.
            mime_type: MIME type of the upload. Validated against the
                same RFC 2045 regex the raw HTTP backend uses
                (``_SAFE_MIME_RE`` in ``core/transport/raw_http/client.py``).
            display_name: Optional human-readable display name. ``None``
                tells the SDK to fall back to the filename.
            timeout: Ignored in this slice — see slice 2d for the SDK
                request_options timeout wiring.

        Returns:
            A ``FileMetadata`` dict with camelCase keys (``name``,
            ``displayName``, ``mimeType``, ``sizeBytes``, ``state``,
            ``uri``), normalized via ``sdk_file_to_metadata``.

        Raises:
            ValueError: If ``mime_type`` contains unsafe characters
                (CRLF or anything outside the RFC 2045 media-type regex).
            BackendUnavailableError: Propagated from ``get_client()`` if
                google-genai is not importable.
        """
        # Validate FIRST — even before fetching the client. This means a
        # malformed mime never even causes a network probe; the test that
        # asserts ``files.upload.assert_not_called()`` after a bad mime
        # relies on this ordering.
        validate_mime_type(mime_type)
        # display_name is a free-form string that might end up in a
        # Content-Disposition header somewhere downstream of the SDK. The
        # SDK should sanitize it, but defense in depth means we reject
        # CR/LF here at the transport boundary so a malicious display
        # name can never reach the wire on either backend. (The raw HTTP
        # backend never honored display_name in headers in the first
        # place — this guard pre-empts the same risk on the SDK path.)
        if display_name is not None:
            validate_no_crlf(display_name, field_name="display_name")

        client = get_client()
        sdk_file = client.files.upload(
            file=str(file_path),
            config={"mime_type": mime_type, "display_name": display_name},
        )
        return sdk_file_to_metadata(sdk_file)
