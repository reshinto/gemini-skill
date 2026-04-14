"""Shared manifest and copy helpers for the installable skill payload.

The repository now has two ways to drive installation:

1. Running ``python3 setup/install.py`` from a source checkout.
2. Running the packaged bootstrap CLI via ``pipx`` / ``uvx``.

Both paths need the same payload copied into
``~/.claude/skills/gemini``. Keeping the payload manifest in one place
prevents drift between the repo installer, the packaging build, and
release artifacts.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

INSTALL_ROOT_FILES: tuple[str, ...] = ("SKILL.md", "VERSION")
INSTALL_DIRS: tuple[str, ...] = ("core", "adapters", "reference", "registry", "scripts")
INSTALL_SETUP_FILES: tuple[str, ...] = ("setup/update.py", "setup/requirements.txt")
INSTALL_COPY_IGNORE_PATTERNS: tuple[str, ...] = ("__pycache__", "*.pyc")


def iter_install_payload_paths() -> tuple[str, ...]:
    """Return every repo-relative path required by the installer."""
    return INSTALL_ROOT_FILES + INSTALL_DIRS + INSTALL_SETUP_FILES


def copy_install_payload(source_dir: Path, install_dir: Path) -> None:
    """Copy the install payload from ``source_dir`` into ``install_dir``."""
    install_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(install_dir), 0o700)
    except OSError:
        pass

    for relative_file in INSTALL_ROOT_FILES:
        source_path = source_dir / relative_file
        if source_path.exists():
            shutil.copy2(source_path, install_dir / relative_file)

    for relative_dir in INSTALL_DIRS:
        source_path = source_dir / relative_dir
        if not source_path.exists():
            continue
        destination_path = install_dir / relative_dir
        if destination_path.exists():
            shutil.rmtree(destination_path)
        shutil.copytree(
            source_path,
            destination_path,
            ignore=shutil.ignore_patterns(*INSTALL_COPY_IGNORE_PATTERNS),
        )

    for relative_file in INSTALL_SETUP_FILES:
        source_path = source_dir / relative_file
        if not source_path.exists():
            continue
        destination_path = install_dir / relative_file
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
