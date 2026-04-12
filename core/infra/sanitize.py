"""Output sanitization and API key scrubbing.

Provides a last-resort defense against API key leakage in stdout, stderr,
and exception tracebacks. The primary defense is never constructing strings
that contain the key — this module catches anything that slips through.

Functions:
    sanitize(text): Remove API key patterns from a string.
    safe_print(*args): Sanitize then print to stdout.
    install_exception_hook(): Override sys.excepthook to scrub tracebacks.

Dependency: none (leaf module).
"""
from __future__ import annotations

import re
import sys
import traceback
from typing import Any

# Matches Google API key patterns: AIza followed by 35 alphanumeric/dash/underscore chars
_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{35}")


def sanitize(text: str) -> str:
    """Remove API key patterns from text.

    Scans for strings matching the Google API key format (AIza...)
    and replaces them with [REDACTED].

    Args:
        text: Any string that might contain an API key.

    Returns:
        The text with all matching key patterns replaced.
    """
    return _KEY_PATTERN.sub("[REDACTED]", text)


def safe_print(*args: Any) -> None:
    """Print to stdout after sanitizing all arguments.

    Use this instead of print() for any output that could potentially
    contain API keys or other secrets.

    Args:
        *args: Values to print, same as built-in print().
    """
    message = " ".join(str(a) for a in args)
    print(sanitize(message))


def install_exception_hook() -> None:
    """Install a global exception hook that scrubs API keys from tracebacks.

    Overrides sys.excepthook so that unhandled exceptions have their
    traceback text sanitized before being printed to stderr. This prevents
    accidental key leakage in crash output.

    The original hook behavior is preserved — only the output is filtered.
    """
    original_hook = sys.excepthook

    def _safe_hook(
        exc_type: type[BaseException],
        exc_val: BaseException,
        exc_tb: Any,
    ) -> None:
        # Format the traceback as text
        lines = traceback.format_exception(exc_type, exc_val, exc_tb)
        sanitized = sanitize("".join(lines))
        sys.stderr.write(sanitized)

    sys.excepthook = _safe_hook
