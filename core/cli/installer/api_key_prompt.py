"""Interactive GEMINI_API_KEY setup — runs BEFORE the generic settings merge.

The API key is the one env var the installer prompts for interactively
because it's the single piece of info that prevents the skill from
working out of the box. Every other key in ``_DEFAULT_ENV_KEYS`` has a
sensible default (``"true"``, ``"0"``, …); the API key is unique.

This module handles GEMINI_API_KEY specifically — the generic merge
in ``settings_merge.py`` sees the populated buffer afterwards and
treats the key as already-present, so it never prompts as a conflict.

Three flows:

1. **Key already in the buffer** (settings.json had a value):
   ``[u]pdate`` (replace), ``[k]eep`` (no change). Default on Enter
   is ``keep`` — never destroy data.
2. **Key absent**: prompt for a value via ``getpass.getpass`` so
   input is not echoed to the terminal. Empty input is accepted and
   stored as ``""``.
3. **Non-interactive / --yes**: skip the prompt entirely. A
   non-interactive install should never hang on an input() call.

Security contracts (enforced by tests):

- The existing value is NEVER echoed — the prompt shows only the
  [u/k] choices, not the current key material.
- After entry, the confirmation line reports only the LENGTH of the
  saved value (``saved (39 characters)``) — never the value.
- A value that doesn't start with ``AIzaSy`` triggers a WARN line
  but is saved anyway (Google could add new key formats and a
  heuristic reject would be worse than a warning).
- If ``getpass.getpass`` falls back to echoing input (rare terminal
  bugs), the installer aborts with ``InstallError`` so a key is
  never typed into scrollback without explicit user opt-in.

Dependencies: stdlib getpass, warnings, sys.
"""

from __future__ import annotations

import getpass
import sys
import warnings

from core.cli.installer.venv import InstallError
from core.types import SettingsBuffer

# Heuristic prefix for a "normal" Google API key. Not a reject
# filter — just a WARN signal. Google can and does rotate key
# formats, so a strict allow-list would lock users out of new key
# types. The warning is enough to surface typos without blocking
# legitimate new-format keys.
_EXPECTED_PREFIX: str = "AIzaSy"


def prompt_gemini_api_key(
    settings_buffer: SettingsBuffer,
    *,
    yes: bool,
    interactive: bool,
) -> None:
    """Populate ``settings_buffer['env']['GEMINI_API_KEY']``.

    Mutates the buffer in place. The generic ``merge_settings_env``
    call that runs downstream sees the populated buffer and treats
    the key as already-present, so it never fires a conflict prompt
    for this key.

    Args:
        settings_buffer: The in-memory JSON-decoded settings.json
            dict the installer is building. May or may not have an
            ``env`` block; the function creates it if missing.
        yes: True when ``--yes`` was passed — skip the prompt.
        interactive: True when stdin is a tty — prompt normally.
            False when piped (CI) — skip the prompt.
    """
    # Ensure the env block exists so subsequent writes are unconditional.
    env_value = settings_buffer.get("env")
    env: dict[str, str]
    if env_value is None or not isinstance(env_value, dict):
        env = {}
        settings_buffer["env"] = env
    else:
        env = env_value

    # Non-interactive paths leave the buffer alone. The generic merge
    # downstream handles the default.
    if yes or not interactive:
        if not yes and not interactive:
            print(
                "[WARN] non-interactive install: GEMINI_API_KEY prompt "
                "skipped. Edit ~/.claude/settings.json after install "
                "if the key is still empty.",
                file=sys.stderr,
            )
        return

    existing = env.get("GEMINI_API_KEY")
    if existing is not None:
        _flow_key_present(env)
    else:
        _flow_key_absent(env)


def _flow_key_present(env: dict[str, str]) -> None:
    """Handle the `key already set` branch: prompt Update vs Keep."""
    print(
        "Found existing GEMINI_API_KEY in ~/.claude/settings.json.\n"
        "What would you like to do?\n"
        "  [u] Update it — enter a new value now\n"
        "  [k] Keep it — leave the existing value untouched (recommended)"
    )
    while True:
        raw = input("Choice [u/k] (default k): ").strip().lower()
        if raw == "" or raw == "k":
            return
        if raw == "u":
            new_value = _read_api_key_value()
            env["GEMINI_API_KEY"] = new_value
            return
        print(f"  unrecognized input {raw!r}; please enter u or k.")


def _flow_key_absent(env: dict[str, str]) -> None:
    """Handle the `no key yet` branch: prompt for the value directly."""
    print(
        "GEMINI_API_KEY is not yet set in ~/.claude/settings.json.\n"
        "You can paste your key now and the installer will save it.\n"
        "You may also leave this empty and edit the file later by hand.\n"
        "Get a key at: https://aistudio.google.com/apikey"
    )
    value = _read_api_key_value()
    env["GEMINI_API_KEY"] = value


def _read_api_key_value() -> str:
    """Read a key via getpass.getpass with echo-fallback + prefix-warn guards.

    Returns the stripped key string (possibly empty). Raises
    ``InstallError`` if ``getpass`` reports a ``GetPassWarning``
    which signals it fell back to echoing input — a security
    regression we refuse to let slip through.
    """
    # catch_warnings with filterwarnings("always") so we can detect
    # GetPassWarning even if the host has upgraded it to an error
    # elsewhere in the stack.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        raw_value = getpass.getpass(
            "Enter your GEMINI_API_KEY (input is hidden, press Enter to leave empty): "
        )
        # Detect the echo fallback — getpass emits GetPassWarning when
        # it can't disable terminal echo and is about to print in
        # cleartext. Abort rather than accept a leaked key.
        for warning in caught:
            if issubclass(warning.category, getpass.GetPassWarning):
                raise InstallError(
                    "getpass fell back to echoing input — refusing to "
                    "accept an API key in cleartext. Rerun in a terminal "
                    "with proper stdin/stdout."
                )
    value = raw_value.strip()
    if value == "":
        print("GEMINI_API_KEY left empty — edit ~/.claude/settings.json " "before first use.")
        return ""

    # Report only the length — never the value itself.
    print(f"GEMINI_API_KEY saved ({len(value)} characters).")

    # Heuristic prefix check: warn but save anyway.
    if not value.startswith(_EXPECTED_PREFIX):
        print(
            f"[WARN] this doesn't look like a Google API key "
            f"(expected prefix {_EXPECTED_PREFIX!r}). Saved anyway — "
            f"verify it's correct."
        )
    return value
