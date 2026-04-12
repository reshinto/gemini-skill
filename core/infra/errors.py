"""Error types and retry classification for the gemini-skill.

This module defines the error hierarchy used throughout the project.
All errors inherit from GeminiSkillError. The classify_retry() function
determines the appropriate retry action for a given HTTP status code.
format_user_error() produces clean, user-friendly messages without
stack traces, suitable for stdout consumption by Claude Code.

Dependency: none (leaf module — no imports from other core modules).
"""
from __future__ import annotations

from typing import Optional


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
    """Raised when the Gemini API returns an error response.

    Attributes:
        status_code: The HTTP status code from the API response, or None
            if the error did not originate from an HTTP response.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
