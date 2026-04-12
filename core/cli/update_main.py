"""Update gemini-skill from GitHub releases.

Checks the latest release tag and compares with installed VERSION.
Download/checksum-verify/atomic-swap implementation is planned;
this module currently reports update availability only.

NOTE: Integrity verification via SHA-256 is planned. Signing for
authenticity is a future enhancement.

Dependencies: core/infra/sanitize.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from core.infra.sanitize import safe_print

_REPO = "reshinto/gemini-skill"
_RELEASE_API = f"https://api.github.com/repos/{_REPO}/releases/latest"


def main(argv: list[str]) -> None:
    """Check for available updates.

    Args:
        argv: Command-line arguments (unused, kept for launcher contract).
    """
    del argv  # Unused — kept for launcher contract consistency

    install_dir = Path.home() / ".claude" / "skills" / "gemini"
    version_file = install_dir / "VERSION"

    if not version_file.is_file():
        safe_print(f"[ERROR] Not installed at {install_dir}. Run install first.")
        return

    current_version = version_file.read_text(encoding="utf-8").strip()
    safe_print(f"Current version: {current_version}")

    try:
        latest = _fetch_latest_release()
    except Exception as e:
        safe_print(f"[ERROR] Could not fetch release info: {e}")
        return

    latest_tag = latest.get("tag_name", "").lstrip("v")
    if not latest_tag:
        safe_print("[ERROR] No latest release found.")
        return

    safe_print(f"Latest version: {latest_tag}")

    if _parse_version(latest_tag) <= _parse_version(current_version):
        safe_print("Already up to date.")
        return

    safe_print(f"Update available: {current_version} -> {latest_tag}")
    safe_print(
        "NOTE: Download/checksum/atomic-swap is not yet implemented. "
        "For now, pull the new release manually from GitHub."
    )


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a semver-like version string into a comparable tuple.

    Handles common formats: "1.2.3", "1.2.3-beta", "v1.2.3".
    Non-numeric suffix segments are ignored.

    Args:
        version: Version string (with or without leading 'v').

    Returns:
        Tuple of integer components, e.g., (1, 2, 3).
    """
    clean = version.lstrip("v").split("-")[0].split("+")[0]
    parts: list[int] = []
    for segment in clean.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _fetch_latest_release() -> dict[str, Any]:
    """Fetch the latest release info from GitHub API."""
    request = Request(_RELEASE_API)
    request.add_header("Accept", "application/vnd.github+json")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read())
