"""API key resolution.

Runtime launcher bootstrap is responsible for loading the current working
directory's ``.env`` / ``.claude/settings*.json`` sources into the process
environment before dispatch. This module then resolves ``GEMINI_API_KEY``
from ``os.environ``.

The optional ``env_dir`` parameter remains as a narrow test/local-dev helper:
when provided, it loads ``<env_dir>/.env`` without overriding already-set
process env values.

The skill deliberately does NOT honor ``GOOGLE_API_KEY``. ``GEMINI_API_KEY``
is the only canonical name.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.infra.errors import AuthError
from core.infra.runtime_env import parse_env_content
from core.infra.sanitize import sanitize


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
    """Resolve the Gemini API key from environment and optional ``env_dir``.

    Primary runtime precedence is established by launcher bootstrap before
    dispatch. When ``env_dir`` is passed, ``<env_dir>/.env`` is loaded as a
    backward-compatible helper without overriding already-set process env
    values.

    Args:
        env_dir: Optional directory containing a .env file to load. The
            launcher-driven runtime does not pass this argument.

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
            "Create .env in the current working directory, add GEMINI_API_KEY to "
            "./.claude/settings.local.json or ./.claude/settings.json, or set it "
            "in ~/.claude/settings.json."
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
