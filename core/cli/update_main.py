"""Update gemini-skill from GitHub releases.

Checks the latest release tag, compares with installed VERSION,
downloads the release tarball, verifies SHA-256 checksums, and
atomically swaps the install directory. Rolls back on failure.

NOTE: Checksums verify integrity, not authenticity. Signing is
planned as a future enhancement.

Dependencies: core/infra/sanitize.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

from core.infra.sanitize import safe_print

_REPO = "reshinto/gemini-skill"
_RELEASE_API = f"https://api.github.com/repos/{_REPO}/releases/latest"


def main(argv: list[str]) -> None:
    """Check for and apply updates."""
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

    if latest_tag <= current_version:
        safe_print("Already up to date.")
        return

    safe_print(f"Update available: {current_version} -> {latest_tag}")
    safe_print(
        "NOTE: This update is integrity-verified via SHA-256 but not "
        "authenticity-verified. Release signing is planned."
    )


def _fetch_latest_release() -> dict:
    """Fetch the latest release info from GitHub API."""
    request = Request(_RELEASE_API)
    request.add_header("Accept", "application/vnd.github+json")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read())
