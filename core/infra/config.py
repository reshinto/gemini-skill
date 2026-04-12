"""JSON configuration management with secure file permissions.

Loads and saves the user configuration from ~/.config/gemini-skill/config.json.
Provides a Config dataclass with sensible defaults for all settings.
Config directories are created with 0o700 and files with 0o600 permissions
(best-effort on Windows).

Dependencies: none (leaf module, stdlib only).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

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
    output_dir: Optional[str] = None
    deep_research_timeout_seconds: int = 3600


def load_config(config_dir: Optional[Path] = None) -> Config:
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
                # Only apply known fields
                for fld in cfg.__dataclass_fields__:
                    if fld in data:
                        setattr(cfg, fld, data[fld])
        except (json.JSONDecodeError, OSError):
            pass  # Return defaults on any read/parse error

    # Enforce cap on deep research timeout
    cfg.deep_research_timeout_seconds = min(
        cfg.deep_research_timeout_seconds, _MAX_DEEP_RESEARCH_TIMEOUT
    )

    return cfg


def save_config(config: Config, config_dir: Optional[Path] = None) -> None:
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
    config_dir.mkdir(parents=True, exist_ok=True)

    # Set directory permissions (best-effort on Windows)
    try:
        os.chmod(str(config_dir), 0o700)
    except OSError:
        pass

    config_file = config_dir / _CONFIG_FILENAME
    data = json.dumps(asdict(config), indent=2)

    # Atomic write: write to temp file in same directory, then replace
    fd, tmp_path = tempfile.mkstemp(
        dir=str(config_dir), prefix=".config-", suffix=".tmp"
    )
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        fd = -1  # Mark as closed

        # Set file permissions before moving into place
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass

        os.replace(tmp_path, str(config_file))
    except Exception:
        if fd >= 0:
            os.close(fd)
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
