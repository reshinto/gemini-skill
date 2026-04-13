"""Shared types and exceptions for the dual-backend transport layer.

This module is intentionally lightweight. It holds the pieces that every
other transport module needs to import without creating circular
dependencies:

- ``BackendUnavailableError`` — raised when a backend can't even start
  (e.g. google-genai is not importable, or a requested capability has no
  implementation in this backend at all).

Later phases of the dual-backend refactor will extend this file with the
``Transport`` / ``AsyncTransport`` Protocols and the ``GeminiResponse``
TypedDict family. For Phase 1 we land only the exception so the policy
layer has something to import.

Why does ``BackendUnavailableError`` live here instead of
``core.infra.errors``? Layering. ``core.infra`` is the foundation layer and
must not depend on transport semantics — the transport layer is *above*
infra. Putting the error here keeps the dependency arrow pointing from
transport → infra, never the reverse. ``BackendUnavailableError`` still
inherits from ``GeminiSkillError`` so callers can catch the base class
without knowing about transport at all.

What you'll learn from this file:
- How to extend an exception hierarchy across packages without circular
  imports — define new exceptions in the layer that introduces the concept,
  not in the layer that owns the base class.
"""
from __future__ import annotations

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
