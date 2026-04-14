"""One-time migration from legacy skill-local .env → ~/.claude/settings.json.

Pre-Phase 5 installs wrote the skill's env vars into a file at
``~/.claude/skills/gemini/.env``. Phase 5 moves them into the
user-global ``~/.claude/settings.json`` env block instead so Claude
Code injects them on session start without the skill needing its
own file.

This module is the bridge: when an upgrading user runs install, any
values still in the legacy .env are merged into the settings buffer
(without clobbering any values settings.json already has) and the
legacy file is offered for deletion.

Algorithm:
1. If the legacy file doesn't exist, no-op.
2. Parse the file as ``KEY=VALUE`` lines (blank + ``#`` comment
   lines skipped; malformed lines skipped).
3. For each parsed key, add to the settings buffer ONLY when
   missing — never overwrite a newer value the user has already
   set in settings.json.
4. Ask the user (via ``input()``) whether to delete the legacy
   file. Default is ``no`` (keep it). With ``--yes`` or non-tty
   stdin, auto-delete so CI runs don't leave stale files.

Dependencies: stdlib pathlib, sys.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.types import SettingsBuffer


def migrate_legacy_env_to_settings(
    legacy_env_path: Path,
    settings_buffer: SettingsBuffer,
    *,
    yes: bool,
    interactive: bool,
) -> None:
    """One-time migration of legacy .env values into the settings buffer.

    Args:
        legacy_env_path: Path to the legacy
            ``~/.claude/skills/gemini/.env`` file.
        settings_buffer: In-memory JSON-decoded settings.json dict.
            Mutated in place — legacy values are added to
            ``settings_buffer["env"]`` when the key is missing.
        yes: When True, auto-confirm legacy-file deletion.
        interactive: When True, prompt the user to decide deletion.
            When False (non-tty stdin or ``--yes``), auto-delete.
    """
    if not legacy_env_path.is_file():
        return

    # Parse the legacy file into a dict.
    legacy_values = _parse_env_file(legacy_env_path)
    if not legacy_values:
        # Nothing to migrate — still offer deletion so the stale file
        # doesn't linger.
        _maybe_delete_legacy(legacy_env_path, yes=yes, interactive=interactive)
        return

    # Ensure the env block exists.
    if "env" not in settings_buffer or not isinstance(settings_buffer["env"], dict):
        settings_buffer["env"] = {}
    env = settings_buffer["env"]

    # Merge: only add keys the buffer doesn't already have. Never
    # overwrite — the settings.json value is always newer / more
    # authoritative than a legacy .env file the user might have
    # forgotten about.
    for key, value in legacy_values.items():
        if key not in env:
            env[key] = value

    _maybe_delete_legacy(legacy_env_path, yes=yes, interactive=interactive)


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` env file into a dict.

    Blank lines and lines starting with ``#`` are skipped. Lines
    without an ``=`` are skipped silently (a malformed entry is
    surfacing as missing is better than a parse error blocking the
    whole migration).
    """
    result: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _maybe_delete_legacy(path: Path, *, yes: bool, interactive: bool) -> None:
    """Prompt (or auto-decide) whether to delete the legacy file.

    - ``--yes`` / non-tty stdin → auto-delete.
    - Interactive → prompt ``[y/N]``; default is keep.
    """
    if yes or not interactive:
        path.unlink(missing_ok=True)
        print(
            f"[migration] Deleted legacy env file at {path} " "(non-interactive).",
            file=sys.stderr,
        )
        return

    print(f"Legacy env file migrated into ~/.claude/settings.json.\n" f"Delete {path}? [y/N]")
    raw = input("Choice [y/N]: ").strip().lower()
    if raw == "y":
        path.unlink(missing_ok=True)
        print(f"[migration] Deleted {path}")
    else:
        print(f"[migration] Kept {path}")
