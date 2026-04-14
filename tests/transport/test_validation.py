"""Tests for core/transport/_validation.py — shared input validators.

These functions are the single source of truth for security-critical
input validation at the transport boundary. They are imported by both
``core/transport/raw_http/client.py`` and ``core/transport/sdk/transport.py``
so any drift in behavior would be a routing-bypass risk. The tests pin
every accepted and rejected character class so a future refactor cannot
accidentally widen the allow list.
"""

from __future__ import annotations

import pytest

from core.transport._validation import validate_mime_type, validate_no_crlf


class TestValidateMimeType:
    """RFC 2045 media-type allow list — anything outside the token charset
    or missing the type/subtype shape is rejected."""

    @pytest.mark.parametrize(
        "mime",
        [
            "text/plain",
            "image/png",
            "image/jpeg",
            "application/json",
            "application/octet-stream",
            "text/html",
            "audio/mpeg",
            "video/mp4",
            "application/vnd.api+json",
        ],
    )
    def test_accepts_common_safe_mime_types(self, mime: str) -> None:
        validate_mime_type(mime)  # must not raise

    @pytest.mark.parametrize(
        "mime",
        [
            "text/plain\r\nX-Injected: yes",  # CRLF header injection
            "text/plain\nbad",  # bare LF
            "text/plain\rbad",  # bare CR
            "text/plain\x00",  # null byte
            "text/ plain",  # internal space
            "text plain",  # missing slash
            "",  # empty string
            "/",  # missing both type and subtype
            "text/",  # missing subtype
            "/plain",  # missing type
            " text/plain",  # leading whitespace
            "text/plain ",  # trailing whitespace
            "text/plain;charset=utf-8",  # parameters not allowed by our regex
        ],
    )
    def test_rejects_unsafe_or_malformed_mime_types(self, mime: str) -> None:
        with pytest.raises(ValueError, match="Unsafe MIME type"):
            validate_mime_type(mime)


class TestValidateNoCrlf:
    """The CRLF guard for free-form fields (display names, descriptions)."""

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "simple",
            "with spaces",
            "punctuation!?.,;:",
            "unicode_café",
            "longer string with more characters and stuff",
        ],
    )
    def test_accepts_safe_strings(self, value: str) -> None:
        validate_no_crlf(value, field_name="test")

    @pytest.mark.parametrize(
        "value",
        [
            "with\rCR",
            "with\nLF",
            "with\r\nboth",
            "trailing\r",
            "trailing\n",
            "\rleading",
            "\nleading",
        ],
    )
    def test_rejects_strings_with_cr_or_lf(self, value: str) -> None:
        with pytest.raises(ValueError, match="test.*CR or LF"):
            validate_no_crlf(value, field_name="test")

    def test_field_name_appears_in_error(self) -> None:
        with pytest.raises(ValueError, match="my_custom_field"):
            validate_no_crlf("bad\rvalue", field_name="my_custom_field")
