"""Install the gemini-skill to ~/.claude/skills/gemini/.

Copies operational files only (no docs, no tests). Phase 5 adds:
- Skill-local venv creation + pinned google-genai install
- Interactive GEMINI_API_KEY prompt (before the generic merge)
- Generic settings.json merge of the default env keys
- One-time legacy ~/.claude/skills/gemini/.env → settings.json
  migration

Dependencies: core/infra/sanitize.py, core/cli/installer/*.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from core.cli.installer.api_key_prompt import prompt_gemini_api_key
from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings
from core.cli.installer.payload import copy_install_payload
from core.cli.installer.settings_merge import (
    InstallAborted,
    SettingsFileCorrupted,
    merge_settings_env,
)
from core.cli.installer.venv import InstallError
from core.infra.checksums import (
    generate_checksums,
    read_checksums_file,
    verify_checksums,
    write_checksums_file,
)
from core.infra.sanitize import safe_print
from core.types import SettingsBuffer

# The canonical default env keys the installer writes into
# ~/.claude/settings.json. Iteration order is preserved in the
# resulting JSON so reviewers diffing a freshly-installed file see a
# deterministic key ordering. Kept at module top so tests and other
# installer submodules can import it without a circular risk.
_DEFAULT_ENV_KEYS: dict[str, str] = {
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0",
}

# The SHA-256 install-integrity manifest the installer writes into the
# install directory after copying files. ``health_main`` reads this file
# to detect drift (files hand-edited or tampered with after install),
# and a future ``update_main`` will verify it before applying updates.
# The filename uses a leading dot so ``shutil.ignore_patterns`` in the
# operational-file copy doesn't accidentally re-copy it from a dev tree
# during repeat installs.
_CHECKSUMS_FILENAME = ".checksums.json"

# Directories INSIDE the install tree that should NOT be included in
# the checksum manifest. ``.venv`` is a live user-owned artifact
# (pip mutates it on every upgrade), and ``__pycache__`` is byte-code
# cache that changes on every import. Including either would make
# every install "drift" from its own manifest the moment it ran.
_CHECKSUMS_EXCLUDED_DIRS: frozenset[str] = frozenset({".venv", "__pycache__"})


def _is_interactive_stdin() -> bool:
    """Return True iff stdin is a tty.

    Wrapped in a function (not inlined) so tests can patch it to
    simulate CI / non-tty environments without touching real stdin.
    """
    return sys.stdin.isatty()


def main(
    argv: list[str], *, source_dir: Path | None = None, install_dir: Path | None = None
) -> None:
    """Install the gemini-skill end-to-end.

    Order of operations:
    1. Resolve source + install directories.
    2. If the install dir already exists, prompt overwrite/skip.
    3. Copy operational files + setup the .env file.
    4. Create the skill-local venv at ``<install_dir>/.venv`` and pip-
       install the pinned ``setup/requirements.txt`` (Phase 5 — makes
       the SDK backend reachable). On venv failure, print a warning
       and continue — the file copy is still valid and the raw HTTP
       backend will work without google-genai.
    5. Phase 5 follow-up: migrate any legacy
       ``~/.claude/skills/gemini/.env`` into the in-memory settings
       buffer, prompt for ``GEMINI_API_KEY`` interactively, then
       merge the defaults into ``~/.claude/settings.json``.
    6. Print the install summary including the SDK version.
    """
    yes_flag = "--yes" in argv or "-y" in argv
    interactive = _is_interactive_stdin()

    resolved_source_dir = source_dir if source_dir is not None else _get_source_dir()
    resolved_install_dir = (
        install_dir if install_dir is not None else _get_install_dir()
    )

    if resolved_install_dir.exists():
        safe_print(f"Skill already installed at {resolved_install_dir}")
        choice = _prompt("[O]verwrite / [S]kip? ").strip().lower()
        if choice not in ("o", "overwrite"):
            safe_print("Skipped.")
            return
        # Preserve the existing .venv across overwrite — re-running
        # install (e.g. after a git pull) should be a fast no-op for
        # the venv step, not a multi-second rebuild. The pinned-
        # version contract in install_requirements means re-running
        # pip is itself a no-op when the version is already installed.
        # Delete every other entry under install_dir manually instead
        # of ``rmtree(install_dir)``.
        _clean_install_dir_preserve_venv(resolved_install_dir)

    _clean_install(resolved_source_dir, resolved_install_dir)
    # Phase 5: the skill-local .env file is deprecated. Env vars now
    # live in ~/.claude/settings.json (merged by the helpers below).
    # Legacy .env files at the install dir are picked up by the
    # migration step below and deleted.

    # Phase 11.6: write the SHA-256 integrity manifest. The manifest
    # covers every operational file just copied by ``_clean_install``.
    # ``.venv`` and ``__pycache__`` are intentionally excluded — both
    # are live user-owned artifacts that pip / the import system
    # mutates on every run, so including them would make the
    # manifest "drift" by definition on the first health-check.
    # Failures here are warned but do not abort the install.
    try:
        _write_install_manifest(resolved_install_dir)
    except OSError as manifest_error:
        safe_print(
            f"[WARN] Install manifest write failed: {manifest_error}. "
            "health_check will not be able to detect drift; re-run "
            "setup/install.py if this persists."
        )

    # Phase 5: create the skill-local venv + install pinned google-genai.
    # Failures here do NOT abort the install — the file copy succeeded
    # and the user can still use the raw HTTP backend, which is the
    # legacy single-backend path that's been working since v0.1.
    sdk_version = _setup_venv(resolved_install_dir)

    # Phase 5 follow-up: write the skill's env vars into
    # ~/.claude/settings.json. This block runs even when venv setup
    # failed above, because settings.json determines backend
    # selection for the raw HTTP path too.
    _setup_user_settings(resolved_install_dir, yes=yes_flag, interactive=interactive)

    safe_print(f"Installed to {resolved_install_dir}")
    if sdk_version is not None:
        safe_print(f"SDK installed: google-genai {sdk_version}")


def _setup_user_settings(install_dir: Path, *, yes: bool, interactive: bool) -> None:
    """Migrate legacy .env, prompt for API key, merge into settings.json.

    The three helpers are layered so each one contributes to an
    in-memory buffer that's handed to the merge step as a single
    atomic ``pre_resolved`` override:

    1. ``migrate_legacy_env_to_settings`` reads any legacy
       ``~/.claude/skills/gemini/.env`` and seeds the buffer with
       its values.
    2. ``prompt_gemini_api_key`` runs the special-case API-key
       interactive flow and adds the user-typed value to the
       buffer.
    3. ``merge_settings_env`` receives the buffer as ``pre_resolved``
       and writes the combined (legacy + prompt + defaults) result
       to ``~/.claude/settings.json`` in a single atomic operation.

    The single-write contract closes the partial-write window that
    an earlier two-step design had between the default merge and a
    separate overlay pass.

    Error handling is granular:
    - ``SettingsFileCorrupted``: re-raised so the install exits
      non-zero. The user must fix their settings.json by hand.
    - ``InstallAborted``: re-raised so a user-initiated quit
      actually exits the installer instead of being demoted to a
      warning.
    - Other ``InstallError``: warned and continued — the rest of
      the install is still usable.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    legacy_env = install_dir / ".env"

    # Build a pre-resolved override map from the two user-choice
    # sources (legacy migration + interactive API-key prompt). Both
    # helpers mutate this in-memory buffer, which we then hand to
    # ``merge_settings_env`` so the whole merge + write is ONE
    # atomic operation — no read-modify-write dance that would
    # open a partial-write window between the merge and an
    # overlay pass.
    settings_buffer: SettingsBuffer = {}

    try:
        migrate_legacy_env_to_settings(
            legacy_env, settings_buffer, yes=yes, interactive=interactive
        )
        prompt_gemini_api_key(settings_buffer, yes=yes, interactive=interactive)

        # Extract the env subdict to pass as pre_resolved. Filter to
        # string values only — the JSON settings format only allows
        # string env values anyway, and a non-string sneaking in
        # would trip the merge_settings_env type check.
        pre_resolved: dict[str, str] = {}
        buffer_env = settings_buffer.get("env")
        if isinstance(buffer_env, dict):
            for k, v in buffer_env.items():
                if isinstance(k, str) and isinstance(v, str):
                    pre_resolved[k] = v

        merge_settings_env(
            settings_path,
            _DEFAULT_ENV_KEYS,
            yes=yes,
            interactive=interactive,
            pre_resolved=pre_resolved,
        )
    except SettingsFileCorrupted as exc:
        # Hard abort: the user's settings.json is corrupted and the
        # installer deliberately refuses to overwrite it. Re-raise
        # so ``setup/install.py`` exits non-zero instead of
        # continuing with whatever partial state exists.
        safe_print(f"[ERROR] {exc}")
        raise
    except InstallAborted as exc:
        # User pressed ``q`` during a conflict prompt. Surface the
        # exact message and re-raise so the process exits non-zero —
        # a user-initiated abort should NOT be silently demoted to
        # a warning.
        safe_print(f"[ABORT] {exc}")
        raise
    except InstallError as exc:
        # Catch-all for other installer errors (e.g. the venv
        # module's errors bubbling through some unrelated path).
        # These are recoverable: the file copy succeeded and the
        # rest of the install is usable, so we warn and continue.
        safe_print(f"[WARN] settings.json merge failed: {exc}")


def _setup_venv(install_dir: Path) -> str | None:
    """Create the skill venv and install pinned dependencies.

    Returns the installed SDK version on success, ``None`` when the
    venv step is skipped (no requirements file in the install dir),
    or warns and returns ``None`` on failure (file copy stays intact;
    raw HTTP backend remains functional).
    """
    requirements = install_dir / "setup" / "requirements.txt"
    if not requirements.is_file():
        # No pinned-dependency manifest in the install — skip the
        # venv step entirely. This is the path that test fixtures
        # without setup/requirements.txt take, and also the path a
        # stripped-down release artifact (e.g. raw-HTTP-only) would
        # follow.
        return None

    venv_target = install_dir / ".venv"

    # Lazy imports so install_main keeps importing cleanly when the
    # installer subpackage is being refactored or the venv module
    # itself is the thing being tested.
    from core.cli.installer import venv as venv_helper
    from core.cli.installer.venv import InstallError

    try:
        # Preserve an existing venv across overwrite installs — only
        # create when the target doesn't already exist. This is the
        # other half of the venv-preservation contract: the file copy
        # leaves .venv untouched (see _clean_install_dir_preserve_venv)
        # AND the venv setup step doesn't blow it away by recreating.
        if not venv_target.exists():
            venv_helper.create_venv(venv_target)
        venv_helper.install_requirements(venv_target, requirements)
        return venv_helper.verify_sdk_importable(venv_target)
    except InstallError as exc:
        # Loud warning so users see exactly what failed AND that the
        # install is still usable via raw HTTP. Phase 5 explicitly
        # documents this fallback path so the SDK backend being broken
        # is never a blocker for the stdlib-only path.
        safe_print(
            f"[WARN] Skill venv setup failed: {exc}\n"
            "       The raw HTTP backend still works; rerun setup/install.py "
            "after fixing the venv issue to enable the SDK backend."
        )
        return None


def _get_source_dir() -> Path:
    """Get the source repo directory (parent of core/cli/)."""
    return Path(__file__).parent.parent.parent


def _get_install_dir() -> Path:
    """Get the install directory."""
    return Path.home() / ".claude" / "skills" / "gemini"


_PRESERVE_ON_OVERWRITE: frozenset[str] = frozenset({".venv", ".env"})


def _clean_install_dir_preserve_venv(install_dir: Path) -> None:
    """Empty ``install_dir`` of every entry EXCEPT preserved ones.

    Used on overwrite to preserve the skill-local virtual environment
    and the legacy .env file across re-installs:

    - ``.venv`` is preserved so re-running install is a fast no-op
      for the venv step (the pinned-version contract means pip is
      idempotent when the version is already installed).
    - ``.env`` is preserved so the Phase 5 follow-up's legacy
      migration can pick up any values the user set under the old
      skill-local .env model and merge them into settings.json.
      Without this, overwriting would delete the legacy file
      before the migration step ran.

    Args:
        install_dir: The skill install directory. Must exist.
    """
    for entry in install_dir.iterdir():
        if entry.name in _PRESERVE_ON_OVERWRITE:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _clean_install(source_dir: Path, install_dir: Path) -> None:
    """Copy operational files to the install directory."""
    copy_install_payload(source_dir, install_dir)


def _iter_manifest_files(install_dir: Path) -> list[Path]:
    """Walk ``install_dir`` and return every file eligible for the manifest.

    Excludes:
    - Directories listed in ``_CHECKSUMS_EXCLUDED_DIRS`` (``.venv``,
      ``__pycache__``) because they are live user-owned artifacts.
    - The manifest file itself (``.checksums.json``) — the manifest
      cannot meaningfully hash itself.
    - Hidden top-level files other than the manifest (future-proofing
      for dot-files like ``.env`` that may live in the install dir).
    - Symlinks — hashing the target bytes would drift whenever the
      target changes, and the install flow never creates symlinks
      intentionally. Unexpected symlinks are a sign the install tree
      was tampered with and should surface as drift, not be silently
      hashed.

    Args:
        install_dir: The install directory to walk.

    Returns:
        A sorted list of file paths, all under ``install_dir``. The
        sort order is purely cosmetic — ``generate_checksums`` stores
        the manifest as a dict so order doesn't affect verification.
    """
    candidates: list[Path] = []
    for entry in install_dir.rglob("*"):
        if not entry.is_file() or entry.is_symlink():
            continue
        # Exclude the manifest file itself and anything under an
        # excluded directory. ``entry.relative_to(install_dir).parts``
        # lets us check the top-level component AND any ancestor.
        relative_parts = entry.relative_to(install_dir).parts
        if relative_parts == (_CHECKSUMS_FILENAME,):
            continue
        if any(component in _CHECKSUMS_EXCLUDED_DIRS for component in relative_parts):
            continue
        candidates.append(entry)
    candidates.sort()
    return candidates


def _write_install_manifest(install_dir: Path) -> None:
    """Compute and write the SHA-256 install-integrity manifest.

    Called from ``main`` immediately after ``_clean_install``. The
    manifest covers every operational file but deliberately excludes
    ``.venv`` (pip mutates this on every upgrade) and ``__pycache__``
    (byte-code cache). The manifest is written to
    ``<install_dir>/.checksums.json`` atomically via the checksums
    module's own writer.

    Args:
        install_dir: The directory where the operational files were
            just copied. Must exist (``_clean_install`` guarantees
            this).

    Raises:
        OSError: If the manifest file cannot be written (e.g. disk
            full, permission denied). The caller in ``main`` catches
            this and surfaces a non-fatal warning — an install
            without a manifest is still usable, it just can't detect
            drift later.
    """
    manifest_path = install_dir / _CHECKSUMS_FILENAME
    files = _iter_manifest_files(install_dir)
    manifest = generate_checksums(install_dir, files)
    write_checksums_file(manifest, manifest_path)
    safe_print(
        f"Install manifest written: {len(manifest)} files in {_CHECKSUMS_FILENAME}"
    )


def verify_install_integrity(install_dir: Path) -> list[str]:
    """Verify the installed files against ``.checksums.json``.

    Public helper exported for use by ``health_main`` and any future
    ``update_main`` pre-flight check. Reads the manifest from
    ``<install_dir>/.checksums.json`` and compares every entry
    against the current bytes on disk.

    Args:
        install_dir: The directory to verify.

    Returns:
        A list of relative paths whose current hash does NOT match
        the manifest (missing files, hand-edited files, or bit-rot).
        An empty list means the install is byte-identical to what
        the installer wrote. Returns an empty list if the manifest
        file does not exist (installs predating Phase 11.6 don't
        ship one).

    Raises:
        ValueError: If the manifest file exists but is invalid JSON
            or has a non-string entry. The caller must decide whether
            to treat that as drift or abort.
    """
    manifest_path = install_dir / _CHECKSUMS_FILENAME
    if not manifest_path.is_file():
        return []
    expected = read_checksums_file(manifest_path)
    return verify_checksums(install_dir, expected)


def _prompt(message: str) -> str:
    """Prompt user for input (wrapped for testability)."""
    return input(message)
