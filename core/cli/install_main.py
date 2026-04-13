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
from core.cli.installer.settings_merge import (
    InstallAborted,
    SettingsFileCorrupted,
    merge_settings_env,
)
from core.cli.installer.venv import InstallError
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

# Operational files/dirs to copy from the source repo
_OPERATIONAL_FILES = ["SKILL.md", "VERSION"]
_OPERATIONAL_DIRS = ["core", "adapters", "reference", "registry", "scripts"]
# setup/requirements.txt is the pinned-dependency manifest the venv
# installer (Phase 5) reads to install google-genai. Must ship with the
# install so re-running install or update can re-resolve the same pin.
_SETUP_FILES = ["setup/update.py", "setup/requirements.txt"]


def _is_interactive_stdin() -> bool:
    """Return True iff stdin is a tty.

    Wrapped in a function (not inlined) so tests can patch it to
    simulate CI / non-tty environments without touching real stdin.
    """
    return sys.stdin.isatty()


def main(argv: list[str]) -> None:
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

    source_dir = _get_source_dir()
    install_dir = _get_install_dir()

    if install_dir.exists():
        safe_print(f"Skill already installed at {install_dir}")
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
        _clean_install_dir_preserve_venv(install_dir)

    _clean_install(source_dir, install_dir)
    # Phase 5: the skill-local .env file is deprecated. Env vars now
    # live in ~/.claude/settings.json (merged by the helpers below).
    # Legacy .env files at the install dir are picked up by the
    # migration step below and deleted.

    # Phase 5: create the skill-local venv + install pinned google-genai.
    # Failures here do NOT abort the install — the file copy succeeded
    # and the user can still use the raw HTTP backend, which is the
    # legacy single-backend path that's been working since v0.1.
    sdk_version = _setup_venv(install_dir)

    # Phase 5 follow-up: write the skill's env vars into
    # ~/.claude/settings.json. This block runs even when venv setup
    # failed above, because settings.json determines backend
    # selection for the raw HTTP path too.
    _setup_user_settings(install_dir, yes=yes_flag, interactive=interactive)

    safe_print(f"Installed to {install_dir}")
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
    install_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(install_dir), 0o700)
    except OSError:
        pass

    for fname in _OPERATIONAL_FILES:
        src = source_dir / fname
        if src.exists():
            shutil.copy2(src, install_dir / fname)

    for dname in _OPERATIONAL_DIRS:
        src = source_dir / dname
        if src.exists():
            dest = install_dir / dname
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    for rel_path in _SETUP_FILES:
        src = source_dir / rel_path
        if src.exists():
            dest = install_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def _prompt(message: str) -> str:
    """Prompt user for input (wrapped for testability)."""
    return input(message)
