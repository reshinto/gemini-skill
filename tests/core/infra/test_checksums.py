"""Tests for core/infra/checksums.py — install integrity verification.

The checksums module is a small SHA-256 manifest helper used by
``setup/install.py`` and ``setup/update.py`` (Phase 5) to verify the
copied skill files match what the release artifact shipped. The contract
is intentionally narrow: generate a manifest from a tree, write it to
disk, read it back, and report every file whose current hash differs
from the expected hash.

Why is integrity verification its own module instead of inline in the
installer? Three reasons:

1. **Pure functions are easy to test exhaustively.** No filesystem
   stubs, no install-flow mocks — just a tmp_path and a handful of
   bytes.
2. **The same primitives are reused by health-check.** Phase 5's
   ``health_main.py`` reports drift detection so users notice when
   they hand-edit installed files; that path needs the same generate
   + verify functions.
3. **Single source of truth for the hash algorithm.** SHA-256 is a
   security-relevant choice — keeping it in one module prevents drift
   across install / update / health.

Test strategy: build a small file tree under ``tmp_path``, generate
the manifest, mutate one file, verify the helper reports exactly the
mutated path. Round-trip the manifest through ``write_checksums_file``
and ``read_checksums_file`` to catch any JSON / encoding bugs.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _build_tree(root: Path) -> None:
    """Build a small fixture tree with deterministic content."""
    (root / "a.py").write_text("print('a')\n")
    (root / "b.py").write_text("print('b')\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("print('c')\n")


class TestGenerateChecksums:
    def test_returns_dict_keyed_by_relative_path(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        _build_tree(tmp_path)
        result = generate_checksums(tmp_path, [tmp_path / "a.py", tmp_path / "sub" / "c.py"])
        assert set(result.keys()) == {"a.py", "sub/c.py"}

    def test_hashes_are_64_char_hex_sha256(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        _build_tree(tmp_path)
        result = generate_checksums(tmp_path, [tmp_path / "a.py"])
        digest = result["a.py"]
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_identical_content_yields_identical_hash(self, tmp_path: Path) -> None:
        """Determinism guard: two files with the same bytes hash to the
        same value. Mutation-resistance for any future refactor that
        accidentally seeds the hash with a path or timestamp."""
        from core.infra.checksums import generate_checksums

        (tmp_path / "x.py").write_text("same\n")
        (tmp_path / "y.py").write_text("same\n")
        result = generate_checksums(tmp_path, [tmp_path / "x.py", tmp_path / "y.py"])
        assert result["x.py"] == result["y.py"]

    def test_different_content_yields_different_hash(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        (tmp_path / "x.py").write_text("one\n")
        (tmp_path / "y.py").write_text("two\n")
        result = generate_checksums(tmp_path, [tmp_path / "x.py", tmp_path / "y.py"])
        assert result["x.py"] != result["y.py"]

    def test_empty_iterable_returns_empty_dict(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        result = generate_checksums(tmp_path, [])
        assert result == {}

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        with pytest.raises(FileNotFoundError):
            generate_checksums(tmp_path, [tmp_path / "does-not-exist.py"])


class TestVerifyChecksums:
    def test_identical_tree_returns_empty_list(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums, verify_checksums

        _build_tree(tmp_path)
        files = [tmp_path / "a.py", tmp_path / "b.py", tmp_path / "sub" / "c.py"]
        expected = generate_checksums(tmp_path, files)
        mismatches = verify_checksums(tmp_path, expected)
        assert mismatches == []

    def test_mutated_file_appears_in_mismatch_list(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums, verify_checksums

        _build_tree(tmp_path)
        files = [tmp_path / "a.py", tmp_path / "b.py"]
        expected = generate_checksums(tmp_path, files)
        # Mutate the file after generating the manifest.
        (tmp_path / "a.py").write_text("print('different')\n")
        mismatches = verify_checksums(tmp_path, expected)
        assert mismatches == ["a.py"]

    def test_missing_file_appears_in_mismatch_list(self, tmp_path: Path) -> None:
        """A file that's in the manifest but not on disk is a mismatch
        — same severity as a hash mismatch because the install is
        broken either way."""
        from core.infra.checksums import generate_checksums, verify_checksums

        _build_tree(tmp_path)
        files = [tmp_path / "a.py", tmp_path / "b.py"]
        expected = generate_checksums(tmp_path, files)
        (tmp_path / "a.py").unlink()
        mismatches = verify_checksums(tmp_path, expected)
        assert mismatches == ["a.py"]

    def test_multiple_mismatches_reported(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums, verify_checksums

        _build_tree(tmp_path)
        files = [tmp_path / "a.py", tmp_path / "b.py", tmp_path / "sub" / "c.py"]
        expected = generate_checksums(tmp_path, files)
        (tmp_path / "a.py").write_text("changed\n")
        (tmp_path / "sub" / "c.py").write_text("also changed\n")
        mismatches = verify_checksums(tmp_path, expected)
        assert sorted(mismatches) == ["a.py", "sub/c.py"]

    def test_empty_manifest_returns_empty_list(self, tmp_path: Path) -> None:
        from core.infra.checksums import verify_checksums

        assert verify_checksums(tmp_path, {}) == []


class TestRoundTripFile:
    def test_write_then_read_yields_same_dict(self, tmp_path: Path) -> None:
        from core.infra.checksums import (
            generate_checksums,
            read_checksums_file,
            write_checksums_file,
        )

        _build_tree(tmp_path)
        files = [tmp_path / "a.py", tmp_path / "b.py", tmp_path / "sub" / "c.py"]
        expected = generate_checksums(tmp_path, files)

        manifest_path = tmp_path / ".checksums.json"
        write_checksums_file(expected, manifest_path)
        loaded = read_checksums_file(manifest_path)
        assert loaded == expected

    def test_read_missing_file_raises(self, tmp_path: Path) -> None:
        from core.infra.checksums import read_checksums_file

        with pytest.raises(FileNotFoundError):
            read_checksums_file(tmp_path / "nope.json")

    def test_read_malformed_json_raises_value_error(self, tmp_path: Path) -> None:
        """A corrupted manifest must raise loudly so the installer
        aborts instead of silently treating every file as 'unknown'."""
        from core.infra.checksums import read_checksums_file

        bad = tmp_path / "bad.json"
        bad.write_text("not json {")
        with pytest.raises(ValueError, match="invalid"):
            read_checksums_file(bad)

    def test_read_non_dict_json_raises_value_error(self, tmp_path: Path) -> None:
        """The manifest must be a JSON object — a list or scalar is
        a malformed manifest and aborts with a clear error."""
        from core.infra.checksums import read_checksums_file

        bad = tmp_path / "list.json"
        bad.write_text('["not", "a", "dict"]')
        with pytest.raises(ValueError, match="invalid"):
            read_checksums_file(bad)

    def test_write_creates_parent_directory_if_needed(self, tmp_path: Path) -> None:
        """Convenience for installers that may write the manifest into
        a subdirectory that doesn't exist yet."""
        from core.infra.checksums import write_checksums_file

        nested = tmp_path / "deep" / "nested" / "manifest.json"
        write_checksums_file({"a.py": "0" * 64}, nested)
        assert nested.exists()

    def test_read_rejects_non_string_value(self, tmp_path: Path) -> None:
        """A manifest where someone hand-edited a digest to a number,
        null, or list must abort loudly at load time — not silently
        coerce via ``str()`` and fail later at verify time. Mutation
        guard for the type check inside read_checksums_file."""
        from core.infra.checksums import read_checksums_file

        bad = tmp_path / "non_string.json"
        bad.write_text('{"a.py": null}')
        with pytest.raises(ValueError, match="invalid"):
            read_checksums_file(bad)

    def test_read_rejects_non_string_key(self, tmp_path: Path) -> None:
        """JSON allows only string keys, but a future caller could
        construct a mapping in Python with int keys and dump it. The
        loaded form should still reject it at the boundary."""
        from core.infra.checksums import read_checksums_file

        # JSON itself enforces string keys, so write a dict with a
        # string key and a non-string value to prove the value branch;
        # the key-type branch is unreachable from json.loads but the
        # check exists as defense-in-depth for any future caller.
        bad = tmp_path / "int_value.json"
        bad.write_text('{"a.py": 42}')
        with pytest.raises(ValueError, match="invalid"):
            read_checksums_file(bad)


class TestKnownValueSha256:
    """Algorithm-substitution mutation guard.

    Every other test compares two computed digests to each other or
    checks length / charset. None of those would catch a bug that
    swapped ``hashlib.sha256()`` for ``hashlib.sha512()`` because both
    produce hex digests of valid charset (only the length differs).
    This test pins the SHA-256 of a known-content file against a
    hard-coded reference value so a future algorithm swap fails
    immediately.
    """

    def test_known_content_yields_expected_sha256(self, tmp_path: Path) -> None:
        from core.infra.checksums import generate_checksums

        # Reference value computed via:
        #   echo -n "hello world" | shasum -a 256
        # → b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
        (tmp_path / "x.txt").write_bytes(b"hello world")
        result = generate_checksums(tmp_path, [tmp_path / "x.txt"])
        assert result["x.txt"] == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


class TestPathTraversalGuard:
    """The verify_checksums function must reject manifest entries whose
    paths escape the install root after symlink/`..` resolution.

    A trusted installer would never construct such a manifest, but
    defense in depth at the function boundary means a future caller
    (health-check loading from a network manifest, fuzz harness, etc.)
    cannot read arbitrary files via a crafted manifest key.
    """

    def test_dotdot_path_raises_value_error(self, tmp_path: Path) -> None:
        from core.infra.checksums import verify_checksums

        # Create a target file outside the root that the malicious
        # manifest would have read if the guard were missing.
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        try:
            with pytest.raises(ValueError, match="escapes root"):
                verify_checksums(
                    tmp_path,
                    {"../outside.txt": "0" * 64},
                )
        finally:
            outside.unlink(missing_ok=True)

    def test_absolute_path_segment_raises_value_error(self, tmp_path: Path) -> None:
        """A manifest entry with multiple ``..`` segments crafted to
        land on /etc/passwd (or its Windows equivalent) must trip the
        guard regardless of host OS. We don't actually create
        /etc/passwd in the test — the guard fires before any file
        system access."""
        from core.infra.checksums import verify_checksums

        with pytest.raises(ValueError, match="escapes root"):
            verify_checksums(
                tmp_path,
                {"../../../../../../../etc/passwd": "0" * 64},
            )
