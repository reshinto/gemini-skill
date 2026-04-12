"""JSON configuration management with secure file permissions.

Loads and saves the user configuration from ~/.config/gemini-skill/config.json.
Provides a Config dataclass with sensible defaults for all settings.
Config directories are created with 0o700 and files with 0o600 permissions
(best-effort on Windows).

Dependencies: core/infra/atomic_write.py
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from core.infra.atomic_write import atomic_write_json

# Maximum allowed deep research timeout (documented 60-minute ceiling)
_MAX_DEEP_RESEARCH_TIMEOUT = 3600

# Config file name within the config directory
_CONFIG_FILENAME = "config.json"


@dataclass
class Config:
    """Application configuration with defaults.

    All fields have sensible defaults so the skill works out of the box.
    Users can override any field via config.json.

    Attributes:
        default_model: The default Gemini model for text generation.
        prefer_preview_models: If True, router prefers preview (3.1) models.
        cost_limit_daily_usd: Maximum daily spend before blocking operations.
        dry_run_default: If True, mutating operations require --execute flag.
        output_dir: Directory for generated media files. None = OS temp dir.
        deep_research_timeout_seconds: Max polling time for Deep Research (capped at 3600).
    """

    default_model: str = "gemini-2.5-flash"
    prefer_preview_models: bool = False
    cost_limit_daily_usd: float = 5.00
    dry_run_default: bool = True
    output_dir: str | None = None
    deep_research_timeout_seconds: int = 3600


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

    cfg = Config()

    if config_file.is_file():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                known_fields = {f.name for f in dataclasses.fields(cfg)}
                for fld in known_fields:
                    if fld in data:
                        setattr(cfg, fld, data[fld])
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

    Args:
        config: The Config instance to save.
        config_dir: Directory for config.json. If None, uses default location.
    """
    if config_dir is None:
        config_dir = Path.home() / ".config" / "gemini-skill"

    config_dir = Path(config_dir)
    config_file = config_dir / _CONFIG_FILENAME
    data = json.dumps(asdict(config), indent=2)

    atomic_write_json(config_file, data)
