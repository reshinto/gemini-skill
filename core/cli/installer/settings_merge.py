"""Merge the skill's default env keys into ``~/.claude/settings.json``.

This module is the part of Phase 5 that teaches the installer to store
its env vars in the user-global Claude Code settings file instead of a
skill-local .env file. The merge contract is deliberately conservative:

1. **File doesn't exist** → create it with ``{"env": <defaults>}``.
   Parent directory is created if needed. No prompts.
2. **File exists but is malformed JSON** → abort with ``InstallError``.
   The caller must fix the file manually; the installer refuses to
   overwrite a file it can't parse.
3. **File exists and ``env`` is missing** → add the ``env`` block
   with every default. Every other top-level key (``model``, ``hooks``,
   ``permissions``, ``mcp``, …) is preserved byte-identical. No prompts.
4. **File exists and ``env`` already has the key** → interactive
   per-key conflict resolution. The prompt NEVER echoes the existing
   value (it might be a secret); callers see the literal token
   ``<REDACTED — see settings.json>`` and can open the file themselves
   if they need to compare. The default action on ``Enter`` is
   ``skip`` — never destroy user data without an explicit ``r``.
5. **Special case** (CR-14 from the canonical plan): if the existing
   value is ``""`` AND the installer's default is also ``""``, skip
   the prompt entirely. Empty-vs-empty is unambiguously a no-op.

A one-time **backup** of the original settings.json is written next to
the file as ``settings.json.pre-gemini-skill.bak`` the first time the
installer touches it (never overwritten on subsequent runs) so users
have a clean recovery path.

The atomic write goes through ``core/infra/atomic_write.py`` so a
crash mid-write cannot corrupt the user's real settings.json.

Dependencies: core/infra/atomic_write.py (atomic write), stdlib json,
pathlib, sys. The InstallError class is re-exported from
``core/cli/installer/venv.py`` so every installer module shares one
exception type.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

from core.cli.installer.venv import InstallError
from core.infra.atomic_write import atomic_write_json

# Tokens used in prompts + the per-key return summary. Kept as
# module-level constants so tests can import them for exact-match
# assertions and a future rename is a single-point edit.
_REDACTED: str = "<REDACTED — see settings.json>"
_BACKUP_SUFFIX: str = ".pre-gemini-skill.bak"

# Return-summary states. Exported as string literals (not an enum)
# because callers serialize these into install-summary stdout and a
# plain string is friendlier than ``MergeState.ADDED``.
_STATE_ADDED: str = "added"
_STATE_KEPT: str = "kept"
_STATE_REPLACED: str = "replaced"

# Keys whose default value is known to carry a secret and must never
# be echoed to the terminal, even when the value came from an
# installer-constructed defaults dict. Phase 5's ``_DEFAULT_ENV_KEYS``
# only contains GEMINI_API_KEY as an empty string today, but the
# ``pre_resolved`` override added below lets callers inject the
# user's actual key — we redact it at the prompt surface so a future
# caller-side mistake cannot regress the "never print the key"
# contract.
_SECRET_KEYS: frozenset[str] = frozenset({"GEMINI_API_KEY"})


class InstallAborted(InstallError):
    """User explicitly chose to quit during an interactive prompt.

    Subclass of ``InstallError`` so existing catch-all ``except
    InstallError`` call sites still handle it, but the type lets
    orchestrators distinguish a user abort from a corrupted-file
    error and re-raise it up the stack instead of demoting to a
    warning.
    """


class SettingsFileCorrupted(InstallError):
    """The existing ``settings.json`` couldn't be parsed as JSON.

    Subclass of ``InstallError`` so existing catch-all sites handle
    it, but the type lets orchestrators treat a corrupted file as a
    hard abort (rather than a warning) since every downstream step
    depends on a readable settings file.
    """


def merge_settings_env(
    settings_path: Path,
    defaults: Mapping[str, str],
    *,
    yes: bool,
    interactive: bool,
    pre_resolved: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Merge ``defaults`` into ``settings_path``'s ``env`` block.

    Args:
        settings_path: Path to the user-global Claude Code settings
            file, typically ``~/.claude/settings.json``.
        defaults: The env keys the skill wants in the file. Iteration
            order is preserved in the output file so reviewers
            diffing a freshly-installed settings.json see a
            deterministic key ordering.
        yes: When True, every conflict is auto-resolved as ``skip``.
            This is the ``--yes`` flag behavior and the non-
            interactive-stdin behavior.
        interactive: When True, conflicts prompt the user via
            ``input()``. When False (non-tty stdin or ``--yes``),
            every conflict is silently skipped.
        pre_resolved: Optional override map of values the orchestrator
            already decided on via legacy migration or an interactive
            API-key prompt. When a key appears here with a non-empty
            value, it wins over both the default AND the on-disk
            value, writes are done in a single atomic operation,
            and no conflict prompt fires. Empty strings are ignored
            (they would clobber real values with nothing useful).

    Returns:
        A ``{key: state}`` dict where each state is one of:
        - ``"added"``: the key was absent; the default was written.
        - ``"kept"``: the key was present; the existing value stays.
        - ``"replaced"``: the key was present; the user chose ``r``.

    Raises:
        SettingsFileCorrupted: If the file exists but is not valid
            JSON, or if the top-level value isn't a JSON object, or
            if the existing ``env`` value isn't a dict.
        InstallAborted: If the user chose ``q`` during an
            interactive conflict prompt.
    """
    # --- Step 1: load the existing file (if any) ---
    existing_raw: str | None = None
    data: dict[str, object]
    if settings_path.exists():
        existing_raw = settings_path.read_text()
        try:
            loaded = json.loads(existing_raw)
        except json.JSONDecodeError as exc:
            raise SettingsFileCorrupted(
                f"{settings_path} is not valid JSON. "
                f"Please fix it manually and re-run setup/install.py. "
                f"The installer will not overwrite a malformed settings file. "
                f"({exc})"
            ) from None
        if not isinstance(loaded, dict):
            raise SettingsFileCorrupted(
                f"{settings_path} must be a JSON object at the top level, "
                f"got {type(loaded).__name__}"
            )
        data = loaded
    else:
        data = {}

    # --- Step 2: one-time backup (only when the file pre-existed) ---
    if existing_raw is not None:
        _maybe_write_backup(settings_path, existing_raw)

    # --- Step 3: resolve the env block ---
    env_raw = data.get("env")
    if env_raw is None:
        env: dict[str, str] = {}
    elif isinstance(env_raw, dict):
        # Defensive copy so the merge doesn't mutate the original
        # dict object (which we still need to preserve other keys
        # from if something fails mid-merge).
        env = {str(k): str(v) for k, v in env_raw.items()}
    else:
        raise SettingsFileCorrupted(
            f"{settings_path}: expected env to be a JSON object, " f"got {type(env_raw).__name__}"
        )

    # Pre-resolved overrides from the orchestrator (legacy-migration
    # values, interactive API-key prompt values). Applied BEFORE the
    # default-key merge so every user-chosen value is already in the
    # env dict and the merge loop treats those keys as "already set".
    pre_resolved_keys: set[str] = set()
    if pre_resolved:
        for key, value in pre_resolved.items():
            if value == "":
                # Empty overrides are ignored — they would clobber
                # existing values with nothing useful.
                continue
            env[key] = value
            pre_resolved_keys.add(key)

    # --- Step 4: per-key merge ---
    summary: dict[str, str] = {}
    # Thread a local flag through the merge loop instead of using a
    # module-level global. Fires at most once per merge call so the
    # user sees one warning line even when multiple keys conflict.
    non_interactive_warning_shown = False
    for key, default_value in defaults.items():
        if key not in env:
            env[key] = default_value
            summary[key] = _STATE_ADDED
            continue

        # Pre-resolved keys were handled above. Report them as
        # "added" if the on-disk env didn't already have them, or
        # "replaced" if the user-chosen value overwrote an existing
        # entry. A key is "pre-resolved replaced" if the original
        # env had a different value for it before the overrides
        # were applied — which we reconstruct by checking the on-
        # disk env_raw dict.
        if key in pre_resolved_keys:
            original_env = env_raw if isinstance(env_raw, dict) else {}
            if key in original_env and original_env[key] != env[key]:
                summary[key] = _STATE_REPLACED
            else:
                summary[key] = _STATE_ADDED
            continue

        existing_value = env[key]
        # CR-14: empty-vs-empty is a silent no-op.
        if existing_value == "" and default_value == "":
            summary[key] = _STATE_KEPT
            continue

        # Non-interactive modes always skip conflicts so --yes /
        # piped stdin / CI never block on a prompt that nobody can
        # answer.
        if yes or not interactive:
            if not yes and not interactive and not non_interactive_warning_shown:
                # First non-interactive skip emits a one-line stderr
                # warning so the user knows a conflict happened.
                non_interactive_warning_shown = True
                print(
                    f"[WARN] non-interactive install: conflicts in {settings_path} "
                    f"were auto-skipped. Edit the file manually to replace any "
                    f"stale values.",
                    file=sys.stderr,
                )
            summary[key] = _STATE_KEPT
            continue

        # Interactive conflict: prompt the user. Default is skip.
        choice = _prompt_conflict(key, default_value)
        if choice == "r":
            env[key] = default_value
            summary[key] = _STATE_REPLACED
        elif choice == "q":
            raise InstallAborted(
                f"Install aborted by user at key '{key}'. " f"{settings_path} was not modified."
            )
        else:  # "s" or "" (Enter = default skip)
            summary[key] = _STATE_KEPT

    # --- Step 5: write the merged result atomically ---
    data["env"] = env
    atomic_write_json(settings_path, json.dumps(data, indent=2, sort_keys=False) + "\n")
    return summary


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _prompt_conflict(key: str, default_value: str) -> str:
    """Prompt the user to resolve a single conflict.

    The existing value is NEVER echoed — it could be a secret. The
    installer's default is echoed ONLY when the key is not in
    ``_SECRET_KEYS``; for secret keys (e.g. GEMINI_API_KEY) the
    default is redacted too so a future caller-side mistake that
    injects a real credential as the "default" can't leak it to
    the terminal.

    Loops until the user enters a valid choice (``r``, ``s``, ``q``,
    or empty for the default skip). Invalid input re-prompts.

    Returns:
        One of ``"r"``, ``"s"``, ``"q"``. An empty response (``Enter``)
        is normalized to ``"s"`` — the safest default that never
        destroys user data.
    """
    default_display = _REDACTED if key in _SECRET_KEYS else repr(default_value)
    print(
        f"CONFLICT: settings.json already has env.{key} set.\n"
        f"  Existing value: {_REDACTED}\n"
        f"  Installer's default: {default_display}\n"
        f"What would you like to do?\n"
        f"  [r] Replace with the installer's default\n"
        f"  [s] Skip — keep your existing value (recommended)\n"
        f"  [q] Quit installation"
    )
    while True:
        raw = input("Choice [r/s/q] (default s): ").strip().lower()
        if raw == "":
            return "s"
        if raw in ("r", "s", "q"):
            return raw
        print(f"  unrecognized input {raw!r}; please enter r, s, or q.")


def _maybe_write_backup(settings_path: Path, original_content: str) -> None:
    """Write a one-time backup of the pre-merge settings.json.

    If the backup file already exists (a previous install touched
    this settings.json), it is NOT overwritten — the first backup is
    always the one users want to recover from.
    """
    backup = settings_path.with_name(settings_path.name + _BACKUP_SUFFIX)
    if backup.exists():
        return
    atomic_write_json(backup, original_content)
