"""Shared input-validation primitives for the transport layer.

This module exists to provide a **single source of truth** for security-
critical validators that both transport backends (raw HTTP and SDK) must
apply identically. Previously the MIME-type guard lived inside
``core/transport/raw_http/client.py`` as an underscore-prefixed private
function and was imported across package boundaries by the SDK transport;
the Phase 2 slice 2c reviewers correctly flagged that as a maintainability
hazard (private-symbol leak) and asked for a shared home.

Why a shared module instead of duplicating the regex in each backend:
    - The MIME regex is the only thing standing between adapter input and
      a CRLF header injection on the wire. Drift between two copies is a
      latent security bug.
    - Moving the function here costs one import line on each backend and
      makes the dependency direction explicit (``raw_http`` and ``sdk``
      both depend on this module; this module depends on nothing in the
      transport layer).
    - The regex is small and unlikely to need backend-specific tweaks.

What you'll learn from this file:
    - **Defense in depth**: the SDK already does its own request building,
      but we still validate the mime type at our transport boundary so a
      future SDK regression cannot reach the wire with an unsafe value.
    - **Module-level compiled regex**: ``re.compile`` at import time means
      the pattern is parsed once and reused on every call — cheaper than
      a function-local compile, and easier to audit because the pattern
      lives at module top.

Dependencies: stdlib only.
"""

from __future__ import annotations

import re

# RFC 2045 media-type pattern — type "/" subtype, each starting with an
# alphanumeric and made up of the restricted token characters from the
# RFC. The character class deliberately excludes whitespace, control
# characters, ``\r``, ``\n``, and ``\x00`` so a malicious adapter input
# cannot inject a header line. ``fullmatch`` is required to reject any
# leading/trailing junk.
_SAFE_MIME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*/[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*$")


def validate_mime_type(mime_type: str) -> None:
    """Reject a MIME type that contains unsafe characters.

    Used by both transport backends before any HTTP write that puts the
    mime type into a header (multipart upload boundaries, content-type
    declarations). The check is intentionally strict: anything outside
    the RFC 2045 token character set raises ``ValueError`` immediately,
    no allow-list overrides.

    Args:
        mime_type: The MIME type string to validate. Must match the
            pattern ``type/subtype`` with token characters only.

    Raises:
        ValueError: If the mime type contains any character outside the
            allow-list, including CRLF (``\\r\\n``), null bytes
            (``\\x00``), spaces, or any other control character.

    Example:
        >>> validate_mime_type("text/plain")
        >>> validate_mime_type("image/png")
        >>> validate_mime_type("text/plain\\r\\nX-Injected: yes")
        Traceback (most recent call last):
            ...
        ValueError: Unsafe MIME type: 'text/plain\\r\\nX-Injected: yes'
    """
    if not _SAFE_MIME_RE.fullmatch(mime_type):
        raise ValueError(f"Unsafe MIME type: {mime_type!r}")


def validate_no_crlf(value: str, *, field_name: str) -> None:
    """Reject a free-form string field that contains CR or LF.

    Used as a lightweight defense-in-depth check for free-form fields
    (display names, descriptions) that might end up in HTTP headers
    downstream. The function is deliberately narrow — it only rejects
    ``\\r`` and ``\\n``; it does NOT enforce a character allow-list,
    because legitimate display names contain spaces, punctuation, and
    Unicode that an allow-list would have to enumerate.

    Args:
        value: The string to check. Empty strings are accepted.
        field_name: Logical name of the field being validated, used in
            the raised exception message so callers can tell which
            field tripped the guard.

    Raises:
        ValueError: If ``value`` contains ``\\r`` or ``\\n``.
    """
    if "\r" in value or "\n" in value:
        raise ValueError(f"Unsafe {field_name}: must not contain CR or LF characters")
