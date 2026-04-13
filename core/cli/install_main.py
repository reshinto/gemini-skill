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
# setup/requirements.txt is the pinned-dependency manifest the venv
# installer (Phase 5) reads to install google-genai. Must ship with the
# install so re-running install or update can re-resolve the same pin.
_SETUP_FILES = ["setup/update.py", "setup/requirements.txt"]


def main(argv: list[str]) -> None:
    """Install the gemini-skill end-to-end.

    Order of operations:
    1. Resolve source + install directories.
    2. If the install dir already exists, prompt overwrite/skip.
    3. Copy operational files + setup the .env file.
    4. Create the skill-local venv at ``<install_dir>/.venv`` and pip-
       install the pinned ``setup/requirements.txt`` (Phase 5 — makes
       the SDK backend reachable). On venv failure, print a warning
       and continue — the file copy is still valid and the raw HTTP
       backend will work without google-genai.
    5. Print the install summary including the SDK version.
    """
    source_dir = _get_source_dir()
    install_dir = _get_install_dir()

    if install_dir.exists():
        safe_print(f"Skill already installed at {install_dir}")
        choice = _prompt("[O]verwrite / [S]kip? ").strip().lower()
        if choice not in ("o", "overwrite"):
            safe_print("Skipped.")
            return
        # Preserve the existing .venv across overwrite — re-running
        # install (e.g. after a git pull) should be a fast no-op for
        # the venv step, not a multi-second rebuild. The pinned-
        # version contract in install_requirements means re-running
        # pip is itself a no-op when the version is already installed.
        # Delete every other entry under install_dir manually instead
        # of ``rmtree(install_dir)``.
        _clean_install_dir_preserve_venv(install_dir)

    _clean_install(source_dir, install_dir)
    _setup_env_file(source_dir, install_dir)

    # Phase 5: create the skill-local venv + install pinned google-genai.
    # Failures here do NOT abort the install — the file copy succeeded
    # and the user can still use the raw HTTP backend, which is the
    # legacy single-backend path that's been working since v0.1.
    sdk_version = _setup_venv(install_dir)

    safe_print(f"Installed to {install_dir}")
    if sdk_version is not None:
        safe_print(f"SDK installed: google-genai {sdk_version}")


def _setup_venv(install_dir: Path) -> str | None:
    """Create the skill venv and install pinned dependencies.

    Returns the installed SDK version on success, ``None`` when the
    venv step is skipped (no requirements file in the install dir),
    or warns and returns ``None`` on failure (file copy stays intact;
    raw HTTP backend remains functional).
    """
    requirements = install_dir / "setup" / "requirements.txt"
    if not requirements.is_file():
        # No pinned-dependency manifest in the install — skip the
        # venv step entirely. This is the path that test fixtures
        # without setup/requirements.txt take, and also the path a
        # stripped-down release artifact (e.g. raw-HTTP-only) would
        # follow.
        return None

    venv_target = install_dir / ".venv"

    # Lazy imports so install_main keeps importing cleanly when the
    # installer subpackage is being refactored or the venv module
    # itself is the thing being tested.
    from core.cli.installer import venv as venv_helper
    from core.cli.installer.venv import InstallError

    try:
        # Preserve an existing venv across overwrite installs — only
        # create when the target doesn't already exist. This is the
        # other half of the venv-preservation contract: the file copy
        # leaves .venv untouched (see _clean_install_dir_preserve_venv)
        # AND the venv setup step doesn't blow it away by recreating.
        if not venv_target.exists():
            venv_helper.create_venv(venv_target)
        venv_helper.install_requirements(venv_target, requirements)
        return venv_helper.verify_sdk_importable(venv_target)
    except InstallError as exc:
        # Loud warning so users see exactly what failed AND that the
        # install is still usable via raw HTTP. Phase 5 explicitly
        # documents this fallback path so the SDK backend being broken
        # is never a blocker for the stdlib-only path.
        safe_print(
            f"[WARN] Skill venv setup failed: {exc}\n"
            "       The raw HTTP backend still works; rerun setup/install.py "
            "after fixing the venv issue to enable the SDK backend."
        )
        return None


def _get_source_dir() -> Path:
    """Get the source repo directory (parent of core/cli/)."""
    return Path(__file__).parent.parent.parent


def _get_install_dir() -> Path:
    """Get the install directory."""
    return Path.home() / ".claude" / "skills" / "gemini"


def _clean_install_dir_preserve_venv(install_dir: Path) -> None:
    """Empty ``install_dir`` of every entry EXCEPT ``.venv``.

    Used on overwrite to preserve the skill-local virtual environment
    across re-installs. The contract: after this function returns,
    ``install_dir`` exists, ``install_dir/.venv`` is untouched, and
    every other top-level entry has been removed (recursively for
    subdirectories).

    Args:
        install_dir: The skill install directory. Must exist.
    """
    for entry in install_dir.iterdir():
        if entry.name == ".venv":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


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
