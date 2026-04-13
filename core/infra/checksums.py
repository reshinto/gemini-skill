"""SHA-256 install-integrity manifest helpers.

This module is the single source of truth for how the skill verifies that
its installed copy matches the release artifact. Three primitives:

- ``generate_checksums(root, files)`` — compute a SHA-256 digest for every
  file in ``files`` and return a ``{relative_path: hex_digest}`` dict.
- ``verify_checksums(root, expected)`` — recompute the digests for every
  file in ``expected`` and return a list of paths whose current bytes
  don't match the expected hash (or that are missing entirely).
- ``write_checksums_file`` / ``read_checksums_file`` — serialize the
  manifest to/from JSON on disk.

Why a hand-written wrapper around ``hashlib.sha256`` instead of inlining
the calls in the installer? Three reasons:

1. **Pure functions are easy to test.** The Phase 4 unit tests cover
   every branch with nothing but ``tmp_path`` — no install-flow stubs.
2. **Phase 5's health-check needs the same primitives.** Drift detection
   ("files have been hand-edited since install") is exactly
   ``verify_checksums(install_dir, read_checksums_file(...))``.
3. **The hash algorithm is a security-relevant choice.** Keeping it in
   one module prevents a future installer refactor from accidentally
   downgrading to MD5 or SHA-1 because they happened to be more
   convenient on the call site.

What you'll learn from this file:
    - **Streaming hashes for large files**: ``hashlib`` exposes
      ``.update()`` so we can hash a 100MB file without loading it all
      into memory at once. The pattern generalizes to checksums,
      compression, encryption — any byte-stream transformation.
    - **POSIX-style relative paths in the manifest**: the manifest
      always stores forward-slash paths regardless of host OS so a
      release artifact built on Linux verifies cleanly on Windows.

Dependencies: stdlib only (hashlib, json, pathlib).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

# Read this many bytes per ``hashlib.update()`` call. 64 KB is the
# canonical Python convention — large enough to amortize the function
# call overhead, small enough not to bloat memory on tiny embedded
# environments. The value is module-level so a future test can import
# it for boundary checks if needed.
_CHUNK_SIZE: int = 64 * 1024


def _hash_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a single file.

    Streams the file in 64 KB chunks so a multi-megabyte file does not
    have to fit in memory all at once. The function never closes the
    caller's file handle — it opens its own.

    Args:
        path: Filesystem path to the file. Must exist and be readable;
            ``FileNotFoundError`` propagates from ``open()`` if not.

    Returns:
        The 64-character lowercase-hex SHA-256 digest of the file's
        bytes.
    """
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def _to_relative_posix(root: Path, path: Path) -> str:
    """Return ``path`` relative to ``root`` with POSIX (``/``) separators.

    Manifests are cross-OS portable: a release artifact built on Linux
    must verify cleanly when installed on Windows, so we never store
    backslashes. ``Path.as_posix()`` is the canonical way to enforce
    this regardless of the host OS.

    Args:
        root: The directory the relative path is computed against.
        path: An absolute or root-relative path inside ``root``.

    Returns:
        The relative path string with forward-slash separators.
    """
    return path.relative_to(root).as_posix()


def generate_checksums(root: Path, files: Iterable[Path]) -> dict[str, str]:
    """Compute a SHA-256 manifest for every file in ``files``.

    Args:
        root: Directory that the returned dict's keys are relative to.
            Every entry in ``files`` must be inside this directory or
            ``Path.relative_to`` will raise.
        files: Iterable of file paths to hash. Order is not preserved
            in the returned dict — use the manifest as a set, not a
            sequence.

    Returns:
        A ``{relative_posix_path: hex_digest}`` dict. Empty when
        ``files`` is empty.

    Raises:
        FileNotFoundError: If any path in ``files`` does not exist.
        ValueError: If a path in ``files`` is not under ``root``.
    """
    manifest: dict[str, str] = {}
    for file_path in files:
        manifest[_to_relative_posix(root, file_path)] = _hash_file(file_path)
    return manifest


def verify_checksums(root: Path, expected: Mapping[str, str]) -> list[str]:
    """Return the list of relative paths whose current hash differs from expected.

    A path is reported as a mismatch in any of these cases:

    1. The file no longer exists on disk under ``root``.
    2. The file exists but its current SHA-256 differs from the
       expected hex digest.

    Both failure modes return the same shape (a relative path string)
    because the installer treats them identically — either way the
    install is broken and the user must re-run setup/install.py.

    Args:
        root: Directory the manifest paths are relative to.
        expected: ``{relative_path: expected_digest}`` mapping (the
            output of a prior ``generate_checksums`` call, typically
            loaded from disk via ``read_checksums_file``).

    Returns:
        A list of relative path strings that failed verification. An
        empty list means every file in the manifest is present and
        unmodified.
    """
    mismatches: list[str] = []
    # Resolve the root once for the path-traversal guard below. Resolving
    # the root (and every candidate path) means a manifest containing
    # ``../../etc/passwd`` cannot escape into the real filesystem — the
    # guard raises immediately rather than silently reading whatever
    # file the relative path happened to land on. Defense in depth:
    # even though the manifest is loaded from disk by the trusted
    # installer, we want the boundary to be enforced at the function
    # surface so a future caller (e.g. health-check, network-loaded
    # manifest, fuzz harness) cannot bypass it.
    resolved_root = root.resolve()
    for relative_path, expected_digest in expected.items():
        # Build the absolute path on the host — split on POSIX ``/``
        # because that's what the manifest stores, then join with the
        # native separator via ``Path``. This is the inverse of
        # ``_to_relative_posix`` and works regardless of host OS.
        abs_path = root.joinpath(*relative_path.split("/"))
        # Path-traversal guard: after resolving symlinks and ``..``,
        # the candidate must still live under the root. Use
        # ``is_relative_to`` (Python 3.9+) for the explicit predicate.
        if not abs_path.resolve().is_relative_to(resolved_root):
            raise ValueError(f"Checksums manifest path escapes root: {relative_path!r}")
        if not abs_path.exists():
            mismatches.append(relative_path)
            continue
        if _hash_file(abs_path) != expected_digest:
            mismatches.append(relative_path)
    return mismatches


def write_checksums_file(manifest: Mapping[str, str], path: Path) -> None:
    """Serialize a manifest to JSON on disk.

    Creates parent directories if they don't exist so installers can
    write into a subdirectory of the install root without a separate
    ``mkdir`` step.

    Args:
        manifest: The ``{relative_path: digest}`` mapping to write.
        path: The destination file path. Will be overwritten if it
            already exists.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort keys so the on-disk manifest is byte-deterministic across
    # runs — essential for the CI gate that asserts "the manifest in
    # the release artifact matches the manifest a fresh build produces"
    # and for human reviewers diffing manifest changes between PRs.
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def read_checksums_file(path: Path) -> dict[str, str]:
    """Load a manifest from disk, returning the same shape as ``generate_checksums``.

    Args:
        path: Path to the JSON manifest file.

    Returns:
        A ``{relative_path: digest}`` dict.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file does not contain a valid JSON object
            (e.g. the file is corrupted, or the top-level value is a
            list or scalar). The ``valid JSON object`` check is a
            defense-in-depth guard so a truncated or hand-edited
            manifest aborts the installer with a clear error rather
            than silently appearing to validate every file.
    """
    raw = path.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Checksums file is invalid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"Checksums file is invalid: expected JSON object, got {type(data).__name__}"
        )
    # Validate every key AND value is a string — defense in depth against
    # a manifest where someone hand-edited a digest to a number, a null,
    # or a list. A previous implementation silently coerced via ``str(v)``
    # which would turn ``None`` into the literal string ``"none"`` and
    # silently fail at verify time; raising here means the installer
    # aborts loudly at the load boundary instead of pretending the
    # corrupted manifest is valid.
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError(
                f"Checksums file is invalid: every entry must be a string-keyed "
                f"string-valued mapping, got {type(k).__name__}={type(v).__name__}"
            )
    return dict(data)
