"""Install the gemini-skill to ~/.claude/skills/gemini/.

Copies operational files only (no docs, no tests). Merges .env on
subsequent installs (non-destructive). Sets secure permissions
(0o700 on dirs, 0o600 on files).

Dependencies: core/infra/sanitize.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.infra.sanitize import safe_print

# Operational files/dirs to copy from the source repo
_OPERATIONAL_FILES = ["SKILL.md", "VERSION"]
_OPERATIONAL_DIRS = ["core", "adapters", "reference", "registry", "scripts"]
_SETUP_FILES = ["setup/update.py"]


def main(argv: list[str]) -> None:
    """Install the gemini-skill."""
    source_dir = _get_source_dir()
    install_dir = _get_install_dir()

    if install_dir.exists():
        safe_print(f"Skill already installed at {install_dir}")
        choice = _prompt("[O]verwrite / [S]kip? ").strip().lower()
        if choice not in ("o", "overwrite"):
            safe_print("Skipped.")
            return
        shutil.rmtree(install_dir)

    _clean_install(source_dir, install_dir)
    _setup_env_file(source_dir, install_dir)
    safe_print(f"Installed to {install_dir}")


def _get_source_dir() -> Path:
    """Get the source repo directory (parent of core/cli/)."""
    return Path(__file__).parent.parent.parent


def _get_install_dir() -> Path:
    """Get the install directory."""
    return Path.home() / ".claude" / "skills" / "gemini"


def _clean_install(source_dir: Path, install_dir: Path) -> None:
    """Copy operational files to the install directory."""
    install_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(install_dir), 0o700)
    except OSError:
        pass

    for fname in _OPERATIONAL_FILES:
        src = source_dir / fname
        if src.exists():
            shutil.copy2(src, install_dir / fname)

    for dname in _OPERATIONAL_DIRS:
        src = source_dir / dname
        if src.exists():
            dest = install_dir / dname
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    for rel_path in _SETUP_FILES:
        src = source_dir / rel_path
        if src.exists():
            dest = install_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def _setup_env_file(source_dir: Path, install_dir: Path) -> None:
    """Create or merge the .env file in the install directory."""
    env_example = source_dir / ".env.example"
    env_file = install_dir / ".env"

    if not env_example.exists():
        return

    if not env_file.exists():
        shutil.copy2(env_example, env_file)
    else:
        _merge_env(env_file, env_example)

    try:
        os.chmod(str(env_file), 0o600)
    except OSError:
        pass


def _merge_env(env_file: Path, env_example: Path) -> None:
    """Non-destructive merge: append new keys from example, never touch existing."""
    existing_content = env_file.read_text(encoding="utf-8")
    example_content = env_example.read_text(encoding="utf-8")

    existing_keys = _extract_keys(existing_content)
    example_keys = _extract_keys(example_content)

    new_keys = example_keys - existing_keys
    if not new_keys:
        return

    with env_file.open("a", encoding="utf-8") as f:
        f.write("\n# Added by gemini-skill install\n")
        for line in example_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in new_keys:
                f.write(f"{line}\n")


def _extract_keys(content: str) -> set[str]:
    """Extract env var keys from .env content."""
    keys: set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _prompt(message: str) -> str:
    """Prompt user for input (wrapped for testability)."""
    return input(message)
