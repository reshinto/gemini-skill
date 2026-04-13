"""Raw HTTP REST client for the Gemini API using urllib (stdlib only).

This module is the **raw HTTP backend** in the dual-backend transport layer.
It was originally the only transport (when the skill was stdlib-only) and now
sits behind ``core/transport/raw_http/transport.py`` (the Transport-protocol
adapter) and ``core/transport/coordinator.py`` (the primary/fallback router).

The functions exported here remain importable via the legacy
``core/infra/client.py`` shim so existing adapters keep working without edits.

All requests use the x-goog-api-key HTTP header for authentication.
The API key is never placed in the URL query string.

Features:
    - JSON request/response with configurable timeout
    - Exponential backoff retry for transient errors (429, 5xx, network)
    - 504 timeout: one retry for idempotent GET requests only
    - SSE streaming for generateContent
    - File upload with multipart body and MIME validation
    - macOS SSL certificate error detection with actionable message

Dependencies: core/auth/auth.py (resolve_key), core/infra/errors.py (APIError)

What you'll learn from this file:
    - ``resolve_key()`` is now called with no arguments. The installed skill
      reads the API key from the process environment, which Claude Code
      injects from ``~/.claude/settings.json`` on session start. Local-dev
      mode (running from a repo clone) loads the same env var from a
      gitignored repo-root ``.env`` via ``scripts/gemini_run.py``. The old
      ``_SKILL_ROOT`` constant has been deleted entirely.
"""

from __future__ import annotations

import json
import re
import secrets
import socket
import ssl
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.auth.auth import resolve_key
from core.infra.errors import APIError
from core.infra.sanitize import sanitize

# Gemini API base URL — all requests are relative to this
BASE_URL = "https://generativelanguage.googleapis.com"

# Retry configuration
_MAX_RETRIES = 3
_BACKOFF_BASE = 1  # seconds — backoff sequence: 1, 2, 4

# MIME type validation: RFC 2045 media-type (no CRLF injection)
_SAFE_MIME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*/[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*$")


def _validate_mime_type(mime_type: str) -> None:
    """Validate MIME type to prevent header injection via CRLF.

    Raises:
        ValueError: If the MIME type contains unsafe characters.
    """
    if not _SAFE_MIME_RE.fullmatch(mime_type):
        raise ValueError(f"Unsafe MIME type: {mime_type!r}")


def api_call(
    endpoint: str,
    body: dict[str, Any] | None = None,
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Gemini API.

    Args:
        endpoint: API endpoint path (e.g., "models" or "models/gemini:generateContent").
        body: JSON request body. None for GET requests.
        method: HTTP method (GET or POST).
        api_version: API version prefix (v1 or v1beta).
        timeout: Request timeout in seconds.
        api_key: Explicit API key. If None, resolved via resolve_key().

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        APIError: On HTTP errors, network failures, or SSL issues.
    """
    key = api_key if api_key is not None else resolve_key()
    url = f"{BASE_URL}/{api_version}/{endpoint}"

    headers = {"x-goog-api-key": key}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    request = Request(url, data=data, headers=headers, method=method)

    return _execute_with_retry(request, timeout=timeout, method=method)


def stream_generate_content(
    model: str,
    body: dict[str, Any],
    api_version: str = "v1beta",
    timeout: int = 30,
) -> Generator[dict[str, Any], None, None]:
    """Stream generateContent responses via SSE.

    Yields parsed JSON chunks from the SSE stream. Skips non-data lines
    and malformed JSON. Uses alt=sse query parameter.

    Args:
        model: Model name (e.g., "gemini-2.5-flash").
        body: Request body with contents and generationConfig.
        api_version: API version prefix.
        timeout: Request timeout in seconds.

    Yields:
        Parsed JSON response chunks.
    """
    key = resolve_key()
    url = f"{BASE_URL}/{api_version}/models/{model}:streamGenerateContent?alt=sse"

    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST")

    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")

    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        json_str = line[6:]  # Strip "data: " prefix
        try:
            yield json.loads(json_str)
        except json.JSONDecodeError:
            continue


def upload_file(
    file_path: Path,
    mime_type: str,
    display_name: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Upload a file to the Gemini Files API.

    Uses the upload/v1beta/files endpoint with multipart body containing
    JSON metadata and file content. MIME type is validated to prevent
    header injection.

    Args:
        file_path: Path to the file to upload.
        mime_type: MIME type of the file (validated for safety).
        display_name: Optional display name for the uploaded file.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response with file metadata.

    Raises:
        ValueError: If mime_type contains unsafe characters.
    """
    _validate_mime_type(mime_type)

    key = resolve_key()
    url = f"{BASE_URL}/upload/v1beta/files"

    file_path = Path(file_path)
    file_data = file_path.read_bytes()

    # Random boundary per upload (RFC 2046 compliance)
    boundary = f"gemini-skill-{secrets.token_hex(16)}"
    parts: list[bytes] = []

    # Metadata part
    metadata: dict[str, Any] = {"file": {}}
    if display_name:
        metadata["file"]["displayName"] = display_name

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b"Content-Type: application/json; charset=UTF-8\r\n\r\n")
    parts.append(json.dumps(metadata).encode("utf-8"))
    parts.append(b"\r\n")

    # File content part
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
    parts.append(file_data)
    parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)

    headers = {
        "x-goog-api-key": key,
        "Content-Type": f"multipart/related; boundary={boundary}",
    }

    request = Request(url, data=body, headers=headers, method="POST")

    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _execute_with_retry(
    request: Request,
    timeout: int,
    method: str,
) -> dict[str, Any]:
    """Execute a request with retry logic for transient errors.

    Retry policy:
        - 429, 5xx (except 504): retry with exponential backoff, max 3 retries
        - 504: one retry for GET only (idempotent reads)
        - 4xx (except 429): no retry
        - Network errors (URLError, socket.timeout): retry with backoff
        - SSLCertVerificationError: no retry, actionable error message
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())

        except ssl.SSLCertVerificationError as e:
            raise APIError(
                f"SSL certificate verification failed: {e}. "
                "On macOS, run: /Applications/Python\\ 3.x/Install\\ Certificates.command",
                status_code=None,
            ) from e

        except HTTPError as e:
            status = e.code
            error_msg = _extract_error_message(e)

            if status == 504 and method.upper() == "GET" and attempt == 0:
                time.sleep(_BACKOFF_BASE)
                continue

            if status == 429 or (500 <= status <= 599 and status != 504):
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF_BASE * (2**attempt))
                    continue

            raise APIError(error_msg, status_code=status) from e

        except (URLError, socket.timeout, ConnectionError) as e:
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE * (2**attempt))
                continue
            raise APIError(f"Network error: {e}") from e


def _extract_error_message(error: HTTPError) -> str:
    """Extract a human-readable error message from an HTTP error response.

    The returned string is passed through ``sanitize()`` so that any API
    key or other secret the upstream may have echoed back into the error
    payload is redacted before the string surfaces in an ``APIError``,
    log line, or traceback. This mirrors the same defense already applied
    in ``core/auth/auth.py::validate_key``.
    """
    try:
        body = error.read()
        data = json.loads(body)
        if "error" in data and "message" in data["error"]:
            return sanitize(f"Gemini API error ({error.code}): {data['error']['message']}")
    except (json.JSONDecodeError, OSError):
        pass
    return sanitize(f"Gemini API error: HTTP {error.code} {error.reason}")
