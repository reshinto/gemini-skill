"""Skill-local venv creation + pinned-dependency install + SDK probe.

This module is the part of Phase 5's installer that turns "files copied
to ``~/.claude/skills/gemini``" into "a working installation that can
``import google.genai``". Three pieces:

1. ``create_venv(path)`` — build a Python venv at ``path`` via stdlib
   ``venv.EnvBuilder(with_pip=True)``. We use the stdlib API, not a
   subprocess to ``python -m venv``, so the path-quoting and PATH
   environment edge cases are handled by Python instead of by us.
2. ``install_requirements(venv_dir, requirements_path)`` — run the
   venv's ``python -m pip install -r requirements.txt`` to install the
   pinned google-genai. Crucially, the call uses the venv's own
   interpreter (not ``sys.executable``) so pip writes packages into
   the venv's ``site-packages``, not system Python. The
   ``--upgrade`` flag is deliberately omitted — pinned-version contract
   means re-running install is idempotent and never silently bumps the
   pin behind the user's back.
3. ``verify_sdk_importable(venv_dir)`` — invoke the venv python with a
   small probe script that imports google.genai AND asserts the import
   resolved from inside the venv. Defense in depth: a buggy venv setup
   that silently fell back to system Python would otherwise pass the
   import-only check while leaving the actual installation broken.

Why is this its own module? Two reasons:

1. **Testability.** ``install_main.py`` was a 135-line procedural file
   with file copies, env merges, prompts, and venv creation all
   intertwined. Splitting venv work into pure functions with clear
   inputs/outputs gives each piece a focused unit test scope.
2. **Reuse.** Phase 5's ``health_main.py`` extension reads the venv's
   pinned vs. installed SDK version to detect drift; it imports
   ``venv_python_path`` from this module so the path resolution stays
   consistent across install / update / health.

What you'll learn from this file:
    - **Stdlib ``venv`` module, not ``virtualenv``**: Python ships venv
      since 3.3 and it produces lighter, faster venvs than the
      third-party ``virtualenv`` package. We use it via
      ``venv.EnvBuilder`` rather than the ``python -m venv`` CLI so
      our parent process can configure ``with_pip``, ``upgrade_deps``,
      and other knobs programmatically.
    - **Cross-OS interpreter path resolution**: a venv places the
      python binary at ``bin/python`` on POSIX and
      ``Scripts/python.exe`` on Windows. The ``venv_python_path``
      helper centralizes this so callers never branch on
      ``sys.platform`` themselves.
    - **Subprocess invocation pattern**: ``subprocess.run`` with
      ``capture_output=True`` and an explicit return-code check, so
      pip stderr surfaces in the raised ``InstallError`` message
      instead of disappearing into the void.

Dependencies: stdlib only (venv, subprocess, sys, pathlib).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

from core.infra.errors import GeminiSkillError


class InstallError(GeminiSkillError):
    """Raised when a Phase 5 install / venv operation cannot complete."""


def venv_python_path(venv_dir: Path) -> Path:
    """Return the path to the python interpreter inside ``venv_dir``."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _looks_like_uv_managed_python(executable: str) -> bool:
    """Best-effort detection for uv-managed Python installs."""
    normalized = executable.replace("\\", "/")
    return "/.local/share/uv/python/" in normalized or "/uv/python/" in normalized


def _preferred_bootstrap_python() -> list[str]:
    """Return interpreter candidates for creating the runtime venv.

    On macOS, uv-managed Python 3.14 has known failures when stdlib venv
    bootstraps pip via ensurepip. Prefer a stable local interpreter such as
    python3.13/python3.12 when available, then fall back to the current
    interpreter.
    """
    candidates: list[str] = []

    if (
        sys.platform == "darwin"
        and sys.version_info >= (3, 14)
        and _looks_like_uv_managed_python(sys.executable)
    ):
        for name in ("python3.13", "python3.12", "python3.11"):
            path = shutil.which(name)
            if path is not None:
                candidates.append(path)

    candidates.append(sys.executable)

    # de-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _create_venv_with_interpreter(interpreter: str, target: Path) -> None:
    """Create a venv using a specific interpreter."""
    cmd = [interpreter, "-m", "venv", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout
        raise InstallError(
            f"virtualenv creation failed using {interpreter!r} (exit {result.returncode})"
            + (f":\n{detail}" if detail else "")
        )


def create_venv(target: Path) -> None:
    """Create a Python venv at ``target`` with pip enabled."""
    target.parent.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None
    for interpreter in _preferred_bootstrap_python():
        try:
            # Use an explicit interpreter subprocess rather than EnvBuilder.
            # This lets us avoid problematic uv-managed 3.14 installs on macOS
            # by selecting a stable interpreter when available.
            _create_venv_with_interpreter(interpreter, target)
            return
        except Exception as exc:
            last_error = exc
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            continue

    if last_error is not None:
        raise InstallError(f"virtualenv creation failed: {last_error}") from last_error

    raise InstallError("virtualenv creation failed: no usable interpreter found")


def install_requirements(venv_dir: Path, requirements_path: Path) -> None:
    """Install pinned requirements into the venv via ``pip install -r``."""
    if not requirements_path.is_file():
        raise InstallError(f"requirements file not found: {requirements_path}")

    python_bin = venv_python_path(venv_dir)
    cmd = [str(python_bin), "-m", "pip", "install", "-r", str(requirements_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise InstallError(
            f"pip install failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )


def verify_sdk_importable(venv_dir: Path) -> str:
    """Verify ``google.genai`` is importable from inside the venv."""
    python_bin = venv_python_path(venv_dir)
    venv_str = str(venv_dir)
    probe = (
        "import sys, google.genai; "
        f"assert {venv_str!r} in sys.executable, "
        f"f'SDK not in venv: '+sys.executable; "
        "print(google.genai.__version__)"
    )

    cmd = [str(python_bin), "-c", probe]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise InstallError(
            f"SDK not importable from venv (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result.stdout.strip()
