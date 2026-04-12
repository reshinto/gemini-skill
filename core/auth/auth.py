"""API key resolution and .env file parsing.

Resolves the Gemini API key from environment variables and an optional
.env file in the skill's install directory. Precedence order:
    1. GOOGLE_API_KEY (shell env)
    2. GEMINI_API_KEY (shell env)
    3. Values loaded from .env file (shell env always wins)

The .env parser follows deliberately simple rules:
    - Split on first '=' only (values may contain '=')
    - Trim whitespace from key and value
    - Strip matching outer quotes (" or ') from value
    - Skip blank lines and lines starting with '#'
    - No inline comment support (# in value is literal)

Dependencies: core/infra/errors.py (AuthError)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.infra.errors import AuthError

# Base URL for the Gemini API
BASE_URL = "https://generativelanguage.googleapis.com"


def parse_env_content(content: str) -> dict[str, str]:
    """Parse .env file content into a key-value dictionary.

    Args:
        content: Raw text content of a .env file.

    Returns:
        Dictionary mapping environment variable names to their values.
    """
    result: dict[str, str] = {}

    for line in content.splitlines():
        line = line.strip()

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        # Must contain '=' to be a valid entry
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip matching outer quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        result[key] = value

    return result


def _load_env_file(env_dir: Path) -> None:
    """Load .env file from the given directory into os.environ.

    Only sets variables that are not already present in the environment
    (shell env always takes precedence over .env values).

    Args:
        env_dir: Directory containing the .env file.
    """
    env_path = env_dir / ".env"
    if not env_path.is_file():
        return

    parsed = parse_env_content(env_path.read_text(encoding="utf-8"))
    for key, value in parsed.items():
        if key not in os.environ:
            os.environ[key] = value


def resolve_key(env_dir: Optional[Union[str, Path]] = None) -> str:
    """Resolve the Gemini API key from environment and optional .env file.

    Precedence: GOOGLE_API_KEY > GEMINI_API_KEY > .env file values.
    Shell environment variables always override .env file values.

    Args:
        env_dir: Optional directory containing a .env file to load.

    Returns:
        The resolved API key string.

    Raises:
        AuthError: If no API key can be found.
    """
    # Load .env if directory provided (does not override existing env vars)
    if env_dir is not None:
        _load_env_file(Path(env_dir))

    # Check environment in precedence order
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    if not key:
        raise AuthError(
            "No API key found. Set GEMINI_API_KEY in your shell environment "
            "or in ~/.claude/skills/gemini/.env"
        )

    return key


def validate_key(key: str) -> bool:
    """Validate an API key by calling the models list endpoint.

    Uses the x-goog-api-key header for authentication (never query string).

    Args:
        key: The API key to validate.

    Returns:
        True if the key is valid.

    Raises:
        AuthError: If the key is invalid (401) or the request fails.
    """
    url = f"{BASE_URL}/v1beta/models"
    request = Request(url)
    request.add_header("x-goog-api-key", key)

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
            return True
    except HTTPError as e:
        if e.code == 401:
            raise AuthError("API key is invalid (401 Unauthorized)") from e
        raise AuthError(f"API key validation failed: HTTP {e.code}") from e
    except Exception as e:
        raise AuthError(f"API key validation failed: {e}") from e
