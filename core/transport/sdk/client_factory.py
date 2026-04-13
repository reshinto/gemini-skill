"""Lazy ``google.genai.Client`` factory — API-key authentication only.

This module is the **single point** in the skill where a ``google.genai.Client``
is constructed. Every other piece of SDK code (the synchronous transport, the
async transport, the live-API adapter) reaches for its client through
``get_client()`` or ``get_async_client()``. Centralizing construction has three
concrete benefits:

1. **Lazy import**: ``import google.genai`` happens *inside* the function
   body, never at module top. The skill must remain importable on machines
   where ``google-genai`` is not installed — that's the whole point of the
   dual-backend design (raw HTTP keeps working without the SDK). Putting the
   import inside the function defers the ``ImportError`` until something
   actually asks for an SDK client, at which point we translate it into a
   ``BackendUnavailableError`` the coordinator's fallback policy can recognize.

2. **API-key auth only**: the client is always built with ``api_key=...``.
   Vertex AI mode, Application Default Credentials (ADC), and the
   ``google-auth`` dependency are explicitly out of scope for this skill —
   that decision is recorded in the dual-backend refactor plan and is the
   reason ``setup/requirements.txt`` does not pin ``google-auth``.

3. **Singleton caching**: ``functools.lru_cache(maxsize=1)`` ensures every
   call within a process returns the same Client instance. The SDK's Client
   does its own connection pooling internally; rebuilding it on every call
   would defeat that. Tests can drop the cache between runs via
   ``get_client.cache_clear()``.

What you'll learn from this file:
    - **Lazy imports as a layering tool**: an ``import`` statement inside a
      function body is evaluated only when the function runs. This lets a
      module declare an *optional* dependency without forcing every importer
      to install it. The trade-off is that import errors surface at call
      time, not module-load time — which is exactly what we want here so
      the coordinator can route past a missing SDK.
    - **`functools.lru_cache` for trivial singletons**: when a function takes
      no arguments and you want it to return the same object forever,
      ``@lru_cache(maxsize=1)`` is a one-line idiom that's easier to read
      and easier to reset (via ``.cache_clear()``) than a hand-rolled
      module-level singleton with a sentinel.

Dependencies: core/auth/auth.py (resolve_key), core/transport/base.py
(BackendUnavailableError).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from core.auth.auth import resolve_key
from core.infra.sanitize import sanitize
from core.transport.base import BackendUnavailableError


@lru_cache(maxsize=1)
def get_client() -> Any:
    """Return a configured ``google.genai.Client`` (singleton per process).

    The client is built with ``api_key=resolve_key()`` — there is no other
    auth path supported by this skill. The first call imports
    ``google.genai`` lazily; subsequent calls return the cached instance.

    Returns:
        A ``google.genai.Client`` instance authenticated with the resolved
        Gemini API key. The return type is annotated as ``Any`` because
        ``google.genai`` is an optional runtime dependency — using the real
        type would force every importer to have google-genai installed even
        when only the raw HTTP backend is in use.

    Raises:
        BackendUnavailableError: If ``google.genai`` cannot be imported, or
            if ``genai.Client(...)`` raises during construction (e.g. SDK
            validation failure). The construction error is sanitized via
            ``core.infra.sanitize`` before being re-raised so the api_key
            value can never leak into the resulting exception message.
            This is the signal the coordinator interprets as "SDK backend
            unavailable, route to fallback" — see core/transport/policy.py.
        AuthError: If ``resolve_key()`` cannot find a Gemini API key. This
            propagates unchanged because auth failures are NOT eligible for
            fallback (a bad key is bad on every backend).

    Caveat — key rotation:
        Because the result is cached for the process lifetime via
        ``functools.lru_cache(maxsize=1)``, rotating ``GEMINI_API_KEY`` in
        the environment after the first call has NO effect on the running
        process — the cached client keeps using the old key until the
        process restarts or a caller explicitly invokes
        ``get_client.cache_clear()``. Long-lived workers that need to honor
        rotation should call ``cache_clear()`` from their auth-failure
        recovery path so the next call re-resolves the key.

    Example:
        >>> from unittest import mock
        >>> import sys
        >>> fake_genai = mock.Mock()
        >>> fake_genai.Client.return_value = "fake-client"
        >>> with mock.patch.dict(sys.modules, {"google.genai": fake_genai}):
        ...     with mock.patch("core.transport.sdk.client_factory.resolve_key",
        ...                     return_value="AIzaTestKey"):
        ...         get_client.cache_clear()
        ...         client = get_client()
        >>> client
        'fake-client'
    """
    # Lazy import: the ImportError below is the load-bearing signal that the
    # SDK backend is unavailable on this machine. We translate it into a
    # BackendUnavailableError so the coordinator's fallback policy can match
    # on a single exception class instead of having to know about ImportError.
    try:
        from google import genai
    except ImportError as exc:
        raise BackendUnavailableError(
            "google-genai is not installed in the active Python environment. "
            "Run setup/install.py to create the skill venv with the pinned "
            "SDK version, or pip install google-genai==1.33.0 in your dev venv."
        ) from exc

    # API-key auth ONLY. No project, no location, no credentials — those
    # are Vertex-mode parameters and Vertex is out of scope per the refactor
    # plan. resolve_key() raises AuthError if no key is found, which
    # propagates because auth failures are not fallback-eligible.
    #
    # Wrap construction in sanitize(): if google.genai's constructor raises
    # for any reason (validation, connectivity probe, …), the exception
    # message could legitimately echo the api_key value back. The raw HTTP
    # backend wraps every error path through core.infra.sanitize for the
    # same reason; the SDK path must match so the dual-backend skill never
    # leaks a key on either backend's error surface.
    key = resolve_key()
    try:
        return genai.Client(api_key=key)
    except Exception as exc:
        raise BackendUnavailableError(
            f"Failed to construct google.genai.Client: {sanitize(str(exc))}"
        ) from exc


def get_async_client() -> Any:
    """Return the async surface of the singleton ``google.genai.Client``.

    The SDK exposes its async API as ``client.aio.<service>`` (e.g.
    ``client.aio.models.generate_content(...)``). This helper returns the
    ``.aio`` namespace directly so async callers don't need to know about
    the parent client.

    Returns:
        The ``client.aio`` namespace from the singleton client. Typed as
        ``Any`` for the same reason as ``get_client``: google-genai is
        optional at runtime.

    Raises:
        BackendUnavailableError: If ``google.genai`` cannot be imported.
        AuthError: If no Gemini API key can be resolved.
    """
    # Reusing the singleton means the async client shares the same
    # connection pool and credentials as the sync client — which is exactly
    # what google-genai's design intends. The returned ``.aio`` namespace is
    # therefore stable across calls *because* get_client() is lru-cached;
    # this function deliberately does NOT add its own cache decorator so
    # the layering stays "one cache, one source of truth".
    return get_client().aio
