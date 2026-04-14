"""Shared runtime env resolution for launcher-driven skill execution.

The launcher normalizes the skill's canonical env keys into ``os.environ``
before dispatch so downstream auth/config code can keep reading the process
environment only. Resolution is per-key and follows the current working
directory, not the installed skill directory:

1. ``./.env``
2. ``./.claude/settings.local.json``
3. ``./.claude/settings.json``
4. ``~/.claude/settings.json``
5. Existing process environment

Only canonical skill-owned keys are imported. Missing files are ignored.
Malformed Claude settings files raise ``EnvironmentResolutionError`` with the
offending path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from core.infra.errors import EnvironmentResolutionError
from core.types import SettingsBuffer

CANONICAL_ENV_DEFAULTS: dict[str, str] = {
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0",
}

CANONICAL_ENV_KEYS: tuple[str, ...] = (
    "GEMINI_API_KEY",
    "GEMINI_IS_SDK_PRIORITY",
    "GEMINI_IS_RAWHTTP_PRIORITY",
    "GEMINI_LIVE_TESTS",
)

_PROJECT_SETTINGS_LOCAL: str = ".claude/settings.local.json"
_PROJECT_SETTINGS_SHARED: str = ".claude/settings.json"
_USER_SETTINGS_RELATIVE_PATH: str = ".claude/settings.json"


def parse_env_content(content: str) -> dict[str, str]:
    """Parse ``.env`` content into key/value pairs.

    Rules:
    - Split on the first ``=``
    - Trim surrounding whitespace from key and value
    - Strip matching outer single or double quotes
    - Ignore blank lines and full-line comments
    - Preserve ``#`` inside values literally
    """
    parsed_values: dict[str, str] = {}

    raw_line: str
    for raw_line in content.splitlines():
        stripped_line: str = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if "=" not in stripped_line:
            continue

        key_text: str
        value_text: str
        key_text, _, value_text = stripped_line.partition("=")
        normalized_key: str = key_text.strip()
        normalized_value: str = value_text.strip()

        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in ('"', "'")
        ):
            normalized_value = normalized_value[1:-1]

        parsed_values[normalized_key] = normalized_value

    return parsed_values


def _filter_canonical_env(source_values: object) -> dict[str, str]:
    """Return only canonical string env values from an arbitrary mapping."""
    filtered_values: dict[str, str] = {}
    if not isinstance(source_values, dict):
        return filtered_values

    env_key: str
    for env_key in CANONICAL_ENV_KEYS:
        candidate_value: object = source_values.get(env_key)
        if isinstance(candidate_value, str):
            filtered_values[env_key] = candidate_value
    return filtered_values


def _read_env_file(env_path: Path) -> dict[str, str]:
    """Read ``env_path`` when present and return canonical keys only."""
    if not env_path.is_file():
        return {}

    try:
        env_text: str = env_path.read_text(encoding="utf-8")
    except OSError as env_error:
        raise EnvironmentResolutionError(
            f"Failed to read env file at {env_path}: {env_error}"
        ) from env_error

    parsed_values: dict[str, str] = parse_env_content(env_text)
    return _filter_canonical_env(parsed_values)


def _read_settings_env(settings_path: Path) -> dict[str, str]:
    """Read canonical env values from a Claude settings file."""
    if not settings_path.is_file():
        return {}

    try:
        settings_text: str = settings_path.read_text(encoding="utf-8")
    except OSError as settings_error:
        raise EnvironmentResolutionError(
            f"Failed to read Claude settings file at {settings_path}: {settings_error}"
        ) from settings_error

    try:
        parsed_settings: object = json.loads(settings_text)
    except json.JSONDecodeError as settings_error:
        raise EnvironmentResolutionError(
            f"Claude settings file is not valid JSON: {settings_path}"
        ) from settings_error

    if not isinstance(parsed_settings, dict):
        return {}

    settings_buffer: SettingsBuffer = cast(SettingsBuffer, parsed_settings)
    env_block: object = settings_buffer.get("env")
    return _filter_canonical_env(env_block)


def _read_process_env() -> dict[str, str]:
    """Collect canonical env keys from the current process environment."""
    process_values: dict[str, str] = {}

    env_key: str
    for env_key in CANONICAL_ENV_KEYS:
        env_value: str | None = os.environ.get(env_key)
        if env_value is not None:
            process_values[env_key] = env_value

    return process_values


def resolve_runtime_env(cwd: Path | None = None, home_dir: Path | None = None) -> dict[str, str]:
    """Resolve canonical env keys using the runtime precedence chain."""
    working_directory: Path = cwd if cwd is not None else Path.cwd()
    resolved_home_dir: Path = home_dir if home_dir is not None else Path.home()

    resolved_values: dict[str, str] = _read_process_env()

    source_values: tuple[dict[str, str], ...] = (
        _read_settings_env(resolved_home_dir / _USER_SETTINGS_RELATIVE_PATH),
        _read_settings_env(working_directory / _PROJECT_SETTINGS_SHARED),
        _read_settings_env(working_directory / _PROJECT_SETTINGS_LOCAL),
        _read_env_file(working_directory / ".env"),
    )

    current_source_values: dict[str, str]
    for current_source_values in source_values:
        resolved_values.update(current_source_values)

    return resolved_values


def bootstrap_runtime_env(cwd: Path | None = None, home_dir: Path | None = None) -> dict[str, str]:
    """Apply resolved runtime env values into ``os.environ`` and return them."""
    resolved_values: dict[str, str] = resolve_runtime_env(cwd=cwd, home_dir=home_dir)

    env_key: str
    env_value: str
    for env_key, env_value in resolved_values.items():
        os.environ[env_key] = env_value

    return resolved_values
