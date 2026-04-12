"""Tests for core/state/identity.py — canonical document identity.

Verifies SHA-256 hashing, MIME detection, path resolution, URI handling,
and equality/hashing of DocumentIdentity instances.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestDocumentIdentity:
    """DocumentIdentity must be a frozen, hashable data container."""

    def test_create_from_fields(self):
        from core.state.identity import DocumentIdentity

        ident = DocumentIdentity(
            content_sha256="abc123",
            mime_type="application/pdf",
            source_path="/tmp/doc.pdf",
            source_uri=None,
        )
        assert ident.content_sha256 == "abc123"
        assert ident.mime_type == "application/pdf"
        assert ident.source_path == "/tmp/doc.pdf"
        assert ident.source_uri is None

    def test_is_frozen(self):
        from core.state.identity import DocumentIdentity

        ident = DocumentIdentity(
            content_sha256="abc",
            mime_type="text/plain",
            source_path="/tmp/a.txt",
            source_uri=None,
        )
        with pytest.raises(AttributeError):
            ident.content_sha256 = "changed"

    def test_is_hashable(self):
        from core.state.identity import DocumentIdentity

        ident = DocumentIdentity(
            content_sha256="abc",
            mime_type="text/plain",
            source_path="/tmp/a.txt",
            source_uri=None,
        )
        # Must be usable as dict key / set member
        s = {ident}
        assert ident in s

    def test_equality(self):
        from core.state.identity import DocumentIdentity

        a = DocumentIdentity("hash1", "text/plain", "/tmp/a.txt", None)
        b = DocumentIdentity("hash1", "text/plain", "/tmp/a.txt", None)
        assert a == b

    def test_inequality(self):
        from core.state.identity import DocumentIdentity

        a = DocumentIdentity("hash1", "text/plain", "/tmp/a.txt", None)
        b = DocumentIdentity("hash2", "text/plain", "/tmp/a.txt", None)
        assert a != b

    def test_to_dict(self):
        from core.state.identity import DocumentIdentity

        ident = DocumentIdentity("abc", "application/pdf", "/tmp/doc.pdf", None)
        d = ident.to_dict()
        assert d == {
            "content_sha256": "abc",
            "mime_type": "application/pdf",
            "source_path": "/tmp/doc.pdf",
            "source_uri": None,
        }

    def test_from_dict(self):
        from core.state.identity import DocumentIdentity

        data = {
            "content_sha256": "abc",
            "mime_type": "application/pdf",
            "source_path": "/tmp/doc.pdf",
            "source_uri": None,
        }
        ident = DocumentIdentity.from_dict(data)
        assert ident.content_sha256 == "abc"
        assert ident.source_uri is None

    def test_round_trip_dict(self):
        from core.state.identity import DocumentIdentity

        original = DocumentIdentity("abc", "text/plain", None, "https://example.com/file.txt")
        restored = DocumentIdentity.from_dict(original.to_dict())
        assert original == restored


class TestComputeIdentity:
    """compute_identity() must hash file contents and detect MIME type."""

    def test_computes_sha256(self, tmp_path):
        from core.state.identity import compute_identity
        import hashlib

        f = tmp_path / "test.txt"
        f.write_text("hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()

        ident = compute_identity(f)
        assert ident.content_sha256 == expected

    def test_detects_mime_type(self, tmp_path):
        from core.state.identity import compute_identity

        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n")

        ident = compute_identity(f)
        assert ident.mime_type == "image/png"

    def test_resolves_path_to_absolute(self, tmp_path):
        from core.state.identity import compute_identity

        f = tmp_path / "doc.pdf"
        f.write_bytes(b"fake pdf")

        ident = compute_identity(f)
        assert Path(ident.source_path).is_absolute()

    def test_source_uri_is_none_for_local(self, tmp_path):
        from core.state.identity import compute_identity

        f = tmp_path / "data.json"
        f.write_text("{}")

        ident = compute_identity(f)
        assert ident.source_uri is None

    def test_accepts_string_path(self, tmp_path):
        from core.state.identity import compute_identity

        f = tmp_path / "test.txt"
        f.write_text("content")

        ident = compute_identity(str(f))
        assert ident.content_sha256 is not None

    def test_mime_override(self, tmp_path):
        from core.state.identity import compute_identity

        f = tmp_path / "data.bin"
        f.write_bytes(b"binary")

        ident = compute_identity(f, mime_type="application/custom")
        assert ident.mime_type == "application/custom"

    def test_resolves_symlinks(self, tmp_path):
        from core.state.identity import compute_identity

        real = tmp_path / "real.txt"
        real.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(real)

        ident = compute_identity(link)
        assert ident.source_path == str(real.resolve())


class TestComputeIdentityForUri:
    """compute_identity_for_uri() must set source_uri and leave source_path None."""

    def test_creates_identity_with_uri(self):
        from core.state.identity import compute_identity_for_uri

        ident = compute_identity_for_uri(
            content_sha256="abc123",
            mime_type="application/pdf",
            uri="https://example.com/doc.pdf",
        )
        assert ident.source_uri == "https://example.com/doc.pdf"
        assert ident.source_path is None

    def test_all_fields_set(self):
        from core.state.identity import compute_identity_for_uri

        ident = compute_identity_for_uri("hash", "text/plain", "gs://bucket/file")
        assert ident.content_sha256 == "hash"
        assert ident.mime_type == "text/plain"
