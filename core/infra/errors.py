"""Error types and retry classification for the gemini-skill.

This module defines the error hierarchy used throughout the project.
All errors inherit from GeminiSkillError. The classify_retry() function
determines the appropriate retry action for a given HTTP status code.
format_user_error() produces clean, user-friendly messages without
stack traces, suitable for stdout consumption by Claude Code.

Dependencies: core.infra.sanitize (single in-package import — used by
APIError.__init__ to scrub error strings at the construction boundary
so any caller that builds an APIError with raw upstream content gets
defense-in-depth redaction). sanitize is itself a leaf module with
zero core/* imports, so no circular risk.
"""
from __future__ import annotations

from core.infra.sanitize import sanitize as _sanitize



class GeminiSkillError(Exception):
    """Base error for all gemini-skill errors.

    All errors raised by the skill should inherit from this class
    so callers can catch the entire family with one except clause.
    """


class AuthError(GeminiSkillError):
    """Raised when the API key is missing, invalid, or cannot be resolved."""


class ModelNotFoundError(GeminiSkillError):
    """Raised when the requested model does not exist or is unavailable."""


class CapabilityUnavailableError(GeminiSkillError):
    """Raised when a requested capability is not supported by the current setup."""


class CostLimitError(GeminiSkillError):
    """Raised when an operation would exceed the configured daily cost limit.

    Attributes:
        current: The current accumulated cost for today (USD).
        limit: The configured daily cost limit (USD).
    """

    def __init__(self, message: str, current: float = 0.0, limit: float = 0.0) -> None:
        super().__init__(message)
        self.current = current
        self.limit = limit


class APIError(GeminiSkillError):
    """Raised when the Gemini API (or one of the dual-backend transports) errors.

    The four dual-backend context fields are populated by
    ``core/transport/coordinator.py::TransportCoordinator`` when both
    backends fail or when the coordinator wants to surface which backend
    actually handled a primary-only error. Bare construction
    (``APIError("msg", status_code=N)``) keeps the legacy single-backend
    semantics — the new fields default to ``None`` and the ``__str__``
    rendering falls back to the message-only form.

    Attributes:
        status_code: The HTTP status code from the API response, or None
            if the error did not originate from an HTTP response.
        primary_backend: When set (e.g. ``"sdk"``), names which backend
            ran first. The coordinator populates this when reporting any
            multi-backend failure so log readers can tell where the
            error originated without parsing the message.
        fallback_backend: When set (e.g. ``"raw_http"``), names the
            backend the coordinator escalated to after the primary
            failed. ``None`` when no fallback was tried (because the
            primary's error was not fallback-eligible, or because no
            fallback was configured for this dispatch).
        primary_error: The ``str()`` of the primary backend's exception,
            captured by the coordinator. Mirrors ``fallback_error``.
        fallback_error: The ``str()`` of the fallback backend's exception
            when both backends failed.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        primary_backend: str | None = None,
        fallback_backend: str | None = None,
        primary_error: str | None = None,
        fallback_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.primary_backend = primary_backend
        self.fallback_backend = fallback_backend
        # Sanitize error-string fields at the constructor boundary.
        # Defense in depth: the coordinator already pre-sanitizes when
        # it populates these from upstream exceptions, but ``APIError``
        # is a public class — any future caller (or Phase 4 adapter
        # code, or third-party callers via the shim) that constructs
        # an APIError directly with an unsanitized error string would
        # otherwise leak it through ``__str__`` / ``format_user_error``.
        # Sanitizing here closes that gap structurally instead of
        # relying on every call site to remember. ``_sanitize`` is
        # imported at module top — see the module docstring's note on
        # the lack of circular-import risk.
        self.primary_error = _sanitize(primary_error) if primary_error is not None else None
        self.fallback_error = (
            _sanitize(fallback_error) if fallback_error is not None else None
        )

    def __str__(self) -> str:
        """Render a structured combined message when multi-backend context is set.

        Three rendering modes, selected explicitly so partial / unusual
        attribute combinations don't silently render misleading text:

        1. **Both backends present** → two-line backend breakdown.
        2. **Primary only** (primary_backend set, fallback_backend None) →
           one-line primary appendix. Used when the coordinator had no
           fallback configured and the primary failed.
        3. **Anything else** → bare message (legacy single-line form).
           This includes the symmetric "fallback only" case (no
           primary_backend); rather than render ``primary [None]: None``,
           we drop the structured form and surface only the message.

        Callers do not pass a mode flag — the four possible
        ``primary_backend``/``fallback_backend`` Truth combinations
        determine the rendering deterministically.
        """
        base = super().__str__()
        # Mode 1: both backends — render the full two-line breakdown.
        if self.primary_backend is not None and self.fallback_backend is not None:
            return (
                f"{base}\n"
                f"  primary [{self.primary_backend}]: {self.primary_error}\n"
                f"  fallback [{self.fallback_backend}]: {self.fallback_error}"
            )
        # Mode 2: primary only — explicit guard so the symmetric
        # fallback-only case falls through to mode 3 instead of
        # rendering ``primary [None]: None``.
        if self.primary_backend is not None and self.fallback_backend is None:
            return f"{base}\n  primary [{self.primary_backend}]: {self.primary_error}"
        # Mode 3: bare error or fallback-only — preserve the legacy
        # single-line rendering. The fallback-only case is unreachable
        # from the coordinator today but the mode-3 fallthrough is the
        # safe rendering if it ever happens.
        return base


def classify_retry(status_code: int) -> str:
    """Determine the retry action for a given HTTP status code.

    Args:
        status_code: The HTTP status code from the API response.

    Returns:
        One of:
        - "retry": the request should be retried with exponential backoff.
        - "no_retry": the request should NOT be retried (client error).
        - "timeout": the server timed out; one retry for idempotent reads only.
    """
    if status_code == 504:
        return "timeout"
    if status_code == 429 or 500 <= status_code <= 599:
        return "retry"
    return "no_retry"


def format_user_error(error: GeminiSkillError) -> str:
    """Format an error into a clean single-line message for stdout.

    Produces a message like: [ERROR] API key not set
    No stack traces, no internal details — just the user-facing message.

    Args:
        error: Any GeminiSkillError instance.

    Returns:
        A clean error string suitable for Claude Code to read.
    """
    return f"[ERROR] {error}"
