"""API key resolution and .env file parsing.

Resolves the Gemini API key from environment variables and an optional
.env file in the local-development repo root. Precedence order:
    1. GEMINI_API_KEY (shell env, set by Claude Code from
       ~/.claude/settings.json or by the contributor's shell)
    2. Values loaded from .env file at the repo root (local-dev only;
       shell env always wins)

The skill deliberately does NOT honor GOOGLE_API_KEY. GEMINI_API_KEY is
the one canonical name to avoid confusion about which key is in use.
End users set GEMINI_API_KEY in ~/.claude/settings.json under the env
block; contributors running tests from a repo clone set it in a
gitignored .env file at the repo root.

The .env parser follows deliberately simple rules:
    - Split on first '=' only (values may contain '=')
    - Trim whitespace from key and value
    - Strip matching outer quotes (" or ') from value
    - Skip blank lines and lines starting with '#'
    - No inline comment support (# in value is literal)

Dependencies: core/infra/errors.py (AuthError), core/infra/sanitize.py
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.infra.errors import AuthError
from core.infra.sanitize import sanitize


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


def resolve_key(env_dir: str | Path | None = None) -> str:
    """Resolve the Gemini API key from environment and optional .env file.

    Precedence: GEMINI_API_KEY (process env) > GEMINI_API_KEY (in <env_dir>/.env).
    Shell environment variables always override .env file values. The skill
    does NOT honor GOOGLE_API_KEY.

    Args:
        env_dir: Optional directory containing a .env file to load. The
            installed skill does NOT pass this argument — it relies on
            Claude Code injecting GEMINI_API_KEY from ~/.claude/settings.json
            into the process env. Local-dev mode (running from a repo clone)
            passes the repo root so the gitignored .env file is read.

    Returns:
        The resolved API key string.

    Raises:
        AuthError: If no API key can be found.
    """
    # Load .env if directory provided (does not override existing env vars)
    if env_dir is not None:
        _load_env_file(Path(env_dir))

    key = os.environ.get("GEMINI_API_KEY")

    if not key:
        raise AuthError(
            "No GEMINI_API_KEY found.\n"
            "Installed skill: edit ~/.claude/settings.json and add "
            "GEMINI_API_KEY to the env block.\n"
            "Local dev: copy .env.example to .env at the repo root and fill "
            "in GEMINI_API_KEY."
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
    # Import here to avoid circular dependency (client imports auth)
    from core.infra.client import BASE_URL

    url = f"{BASE_URL}/v1beta/models"
    request = Request(url)
    request.add_header("x-goog-api-key", key)

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
            return True
    except HTTPError as http_error:
        if http_error.code == 401:
            raise AuthError("API key is invalid (401 Unauthorized)") from http_error
        raise AuthError(f"API key validation failed: HTTP {http_error.code}") from http_error
    except (URLError, socket.timeout, ssl.SSLError, OSError) as network_error:
        # Narrow to realistic network failures. A bare ``Exception`` here
        # would swallow programmer bugs (AttributeError, TypeError) and
        # silently re-wrap them as AuthError, which makes debugging hard.
        raise AuthError(
            f"API key validation failed: {sanitize(str(network_error))}"
        ) from network_error
