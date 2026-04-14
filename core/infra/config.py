"""JSON configuration management with secure file permissions.

Loads and saves the user configuration from ~/.config/gemini-skill/config.json.
Provides a Config dataclass with sensible defaults for all settings, plus the
dual-backend transport priority flags (GEMINI_IS_SDK_PRIORITY /
GEMINI_IS_RAWHTTP_PRIORITY) which are sourced from the process environment
(populated by Claude Code from ~/.claude/settings.json `env` block).

Config directories are created with 0o700 and files with 0o600 permissions
(best-effort on Windows).

Dependencies: core/infra/atomic_write.py
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from core.infra.atomic_write import atomic_write_json

# Maximum allowed deep research timeout (documented 60-minute ceiling)
_MAX_DEEP_RESEARCH_TIMEOUT = 3600

# Config file name within the config directory
_CONFIG_FILENAME = "config.json"

# Recognized truthy spellings for boolean env vars stored in settings.json.
# settings.json holds string values, so we parse case-insensitively and accept
# a small whitelist. Anything outside the whitelist (including the empty
# string) is treated as False so a stray value never silently flips a backend.
_TRUTHY_BOOL_VALUES = frozenset({"true", "1", "yes"})


class ConfigError(ValueError):
    """Raised when the configuration is internally inconsistent.

    Distinct from generic ValueError so callers (the coordinator factory in
    particular) can catch ConfigError without swallowing unrelated value
    errors raised inside the load path.
    """


def _parse_bool_env(name: str, *, default: bool) -> bool:
    """Parse an env var as a boolean using settings.json semantics.

    settings.json stores every value as a string (JSON has no shell-style
    booleans), so the skill must coerce them. This helper accepts the same
    truthy spellings the documentation promises: ``true``/``True``/``TRUE``,
    ``1``, ``yes``/``Yes`` — case-insensitive, with leading/trailing
    whitespace stripped. Everything else is False, including the empty
    string. Missing env vars fall back to the supplied default.

    The ``default`` argument applies ONLY when the variable is unset. Once
    the variable is present, an unrecognized value is treated as False
    regardless of ``default`` — that's deliberate: a typo like
    ``GEMINI_IS_SDK_PRIORITY=ture`` should disable SDK priority loudly via
    a downstream ConfigError, not silently fall back to the default.

    Args:
        name: Environment variable name to read (e.g. ``GEMINI_IS_SDK_PRIORITY``).
        default: Value returned only when the variable is unset.

    Returns:
        - ``default`` if the env var is unset.
        - True if the env var holds a recognized truthy spelling.
        - False for every other set value (including empty string and typos).
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY_BOOL_VALUES


@dataclass
class Config:
    """Application configuration with defaults.

    All fields have sensible defaults so the skill works out of the box.
    Users can override any field via config.json (for the JSON-backed fields)
    or via environment variables (for the dual-backend priority flags).

    Attributes:
        default_model: The default Gemini model for text generation.
        prefer_preview_models: If True, router prefers preview (3.1) models.
        cost_limit_daily_usd: Maximum daily spend before blocking operations.
        dry_run_default: If True, mutating operations require --execute flag.
        output_dir: Directory for generated media files. None = OS temp dir.
        deep_research_timeout_seconds: Max polling time for Deep Research (capped at 3600).
        is_sdk_priority: True when the google-genai SDK backend is enabled.
            Sourced from the GEMINI_IS_SDK_PRIORITY env var. Default True so
            the SDK runs first in fresh installs.
        is_rawhttp_priority: True when the raw HTTP backend is enabled.
            Sourced from GEMINI_IS_RAWHTTP_PRIORITY. Default False — raw HTTP
            is still always *available*, this flag only controls priority
            ordering (see ``primary_backend`` / ``fallback_backend``).

    Note for direct construction:
        ``Config(is_sdk_priority=False, is_rawhttp_priority=False)`` is
        deliberately disallowed and raises ``ConfigError`` from
        ``__post_init__``. At least one backend must be enabled or the
        coordinator has nothing to dispatch to. Tests that need a minimal
        Config should leave both flags at their defaults or pass at least
        one as True.
    """

    default_model: str = "gemini-2.5-flash"
    prefer_preview_models: bool = False
    cost_limit_daily_usd: float = 5.00
    dry_run_default: bool = True
    output_dir: str | None = None
    deep_research_timeout_seconds: int = 3600
    is_sdk_priority: bool = True
    is_rawhttp_priority: bool = False

    def __post_init__(self) -> None:
        """Validate cross-field invariants after dataclass construction.

        The transport layer always has two available backends conceptually:
        SDK and raw HTTP. The priority flags control ordering preference, not
        enable/disable semantics. Therefore no boolean combination is invalid.
        """
        return

    @property
    def primary_backend(self) -> Literal["sdk", "raw_http"]:
        """Name of the backend the coordinator must try first.

        Ordering rules:
        - sdk=true,  raw=false -> sdk
        - sdk=true,  raw=true  -> sdk
        - sdk=false, raw=true  -> raw_http
        - sdk=false, raw=false -> sdk
        """
        if self.is_sdk_priority:
            return "sdk"
        if self.is_rawhttp_priority:
            return "raw_http"
        return "sdk"

    @property
    def fallback_backend(self) -> Literal["raw_http"] | None:
        """Name of the backend used when the primary fails.

        Ordering rules:
        - sdk=true,  raw=false -> raw_http
        - sdk=true,  raw=true  -> raw_http
        - sdk=false, raw=true  -> sdk
        - sdk=false, raw=false -> raw_http
        """
        return "raw_http" if self.primary_backend == "sdk" else "sdk"


def load_config(config_dir: Path | None = None) -> Config:
    """Load configuration from JSON file, merging with defaults.

    If the config file does not exist or contains invalid JSON,
    returns a Config with all defaults. Unknown fields in the JSON
    are silently ignored.

    Args:
        config_dir: Directory containing config.json. If None, uses
            the default ~/.config/gemini-skill/ location.

    Returns:
        A Config instance with loaded values merged over defaults.
    """
    if config_dir is None:
        config_dir = Path.home() / ".config" / "gemini-skill"

    config_dir = Path(config_dir)
    config_file = config_dir / _CONFIG_FILENAME

    # Resolve the dual-backend priority flags BEFORE constructing Config so
    # __post_init__ sees the user's actual choice and not the dataclass
    # defaults. The flags live in the process environment (Claude Code
    # exports them from ~/.claude/settings.json) — they are intentionally
    # NOT read from config.json so users have a single source of truth for
    # backend selection.
    is_sdk_priority = _parse_bool_env("GEMINI_IS_SDK_PRIORITY", default=True)
    is_rawhttp_priority = _parse_bool_env("GEMINI_IS_RAWHTTP_PRIORITY", default=False)

    # Construct with the resolved flags. ConfigError raised here propagates
    # to the caller — that's intentional: a both-flags-false misconfiguration
    # must surface loudly at the earliest possible moment, not on the first
    # API call when the coordinator tries to pick a backend.
    cfg = Config(
        is_sdk_priority=is_sdk_priority,
        is_rawhttp_priority=is_rawhttp_priority,
    )

    if config_file.is_file():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Only the JSON-backed fields are loaded from disk. Backend
                # priority is env-only so we never let stale config.json
                # contradict the user's settings.json env block.
                json_backed_fields = {
                    field.name for field in dataclasses.fields(cfg)
                } - {
                    "is_sdk_priority",
                    "is_rawhttp_priority",
                }
                for field_name in json_backed_fields:
                    if field_name in data:
                        setattr(cfg, field_name, data[field_name])
        except (json.JSONDecodeError, OSError):
            pass  # Return defaults on any read/parse error

    # Enforce cap on deep research timeout
    cfg.deep_research_timeout_seconds = min(
        cfg.deep_research_timeout_seconds, _MAX_DEEP_RESEARCH_TIMEOUT
    )

    return cfg


def save_config(config: Config, config_dir: Path | None = None) -> None:
    """Save configuration to JSON file with secure permissions.

    Creates the config directory (0o700) and file (0o600) if they
    do not exist. Uses atomic write via temp file + os.replace().

    The backend priority flags (``is_sdk_priority`` / ``is_rawhttp_priority``)
    are deliberately stripped from the serialized output. Those values
    live in the process environment (Claude Code injects them from
    ``~/.claude/settings.json``) and ``load_config`` always re-reads them
    from there, so writing them to ``config.json`` would only invite
    confusion if a user hand-edited the file expecting their change to
    take effect.

    Args:
        config: The Config instance to save.
        config_dir: Directory for config.json. If None, uses default location.
    """
    if config_dir is None:
        config_dir = Path.home() / ".config" / "gemini-skill"

    config_dir = Path(config_dir)
    config_file = config_dir / _CONFIG_FILENAME
    payload = asdict(config)
    # Strip env-only fields so config.json on disk matches the contract
    # of load_config() (which never reads these keys from the file).
    payload.pop("is_sdk_priority", None)
    payload.pop("is_rawhttp_priority", None)
    data = json.dumps(payload, indent=2)

    atomic_write_json(config_file, data)
