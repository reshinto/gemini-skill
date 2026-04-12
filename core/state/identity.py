"""Canonical document identity for deduplication across state stores.

Provides a frozen, hashable identity based on content hash (SHA-256),
MIME type, and source location (local path or remote URI). Used by both
the Files API state (48hr expiry) and File Search store state (persistent)
to prevent redundant uploads of identical content.

Dependencies: core/infra/mime.py (guess_mime_for_path)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentIdentity:
    """Immutable identity for a document based on content and source.

    Two documents with the same content_sha256 and mime_type represent
    the same logical content, regardless of filename.

    Attributes:
        content_sha256: SHA-256 hex digest of the file contents.
        mime_type: MIME type of the document.
        source_path: Absolute resolved path for local files, or None.
        source_uri: Original URI for remote files, or None.
    """

    content_sha256: str
    mime_type: str
    source_path: str | None
    source_uri: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "content_sha256": self.content_sha256,
            "mime_type": self.mime_type,
            "source_path": self.source_path,
            "source_uri": self.source_uri,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentIdentity:
        """Deserialize from a dictionary."""
        return cls(
            content_sha256=data["content_sha256"],
            mime_type=data["mime_type"],
            source_path=data.get("source_path"),
            source_uri=data.get("source_uri"),
        )


def compute_identity(
    file_path: str | Path,
    mime_type: str | None = None,
) -> DocumentIdentity:
    """Compute canonical identity for a local file.

    Reads the file to compute SHA-256. Detects MIME type from extension
    unless overridden. Resolves the path to an absolute real path
    (following symlinks).

    Args:
        file_path: Path to the local file.
        mime_type: Optional MIME type override. If None, detected from extension.

    Returns:
        A DocumentIdentity with source_path set and source_uri as None.
    """
    from core.infra.mime import guess_mime_for_path

    path = Path(file_path).resolve()
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    if mime_type is None:
        mime_type = guess_mime_for_path(path)

    return DocumentIdentity(
        content_sha256=sha256,
        mime_type=mime_type,
        source_path=str(path),
        source_uri=None,
    )


def compute_identity_for_uri(
    content_sha256: str,
    mime_type: str,
    uri: str,
) -> DocumentIdentity:
    """Create a document identity for a remote file.

    For remote files, the caller provides the hash and MIME type
    (computed from the downloaded content or provided by the server).

    Args:
        content_sha256: SHA-256 hex digest of the content.
        mime_type: MIME type of the content.
        uri: Original URI of the remote file.

    Returns:
        A DocumentIdentity with source_uri set and source_path as None.
    """
    return DocumentIdentity(
        content_sha256=content_sha256,
        mime_type=mime_type,
        source_path=None,
        source_uri=uri,
    )
