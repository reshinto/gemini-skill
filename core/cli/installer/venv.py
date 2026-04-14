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

import subprocess
import sys
import venv
from pathlib import Path

from core.infra.errors import GeminiSkillError


class InstallError(GeminiSkillError):
    """Raised when a Phase 5 install / venv operation cannot complete.

    The Phase 5 installer wraps every venv / pip / probe failure in
    this class so the calling installer logic has a single exception
    type to catch and surface to the user. Inherits from
    ``GeminiSkillError`` so existing ``format_user_error`` machinery
    handles it without special-casing.
    """


def venv_python_path(venv_dir: Path) -> Path:
    """Return the path to the python interpreter inside ``venv_dir``.

    A venv created by ``venv.EnvBuilder`` places its python binary
    at one of two well-known locations depending on host OS:

    - POSIX (Linux, macOS): ``<venv>/bin/python``
    - Windows:              ``<venv>/Scripts/python.exe``

    Centralizing this here means callers never branch on
    ``sys.platform`` themselves, and a future Windows-only fix only
    has to land in one place.

    Args:
        venv_dir: The directory passed to ``create_venv``.

    Returns:
        Absolute path to the venv's python binary. The function does
        NOT verify the path exists — that's the caller's job (the
        ``verify_sdk_importable`` probe will surface a missing-binary
        error on its first subprocess call).
    """
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def create_venv(target: Path) -> None:
    """Create a Python venv at ``target`` with pip enabled.

    Uses ``venv.EnvBuilder(with_pip=True)`` so the resulting venv has
    pip preinstalled and can install the runtime requirements without
    a separate bootstrap step. Creates the parent directory if it
    doesn't exist — a fresh install on a new machine has no parent.

    Args:
        target: Absolute path where the venv should live, typically
            ``~/.claude/skills/gemini/.venv``.
    """
    # Create the parent directory (the install dir) if it doesn't yet
    # exist. ``mkdir(parents=True, exist_ok=True)`` is idempotent —
    # safe to call when the directory already exists.
    target.parent.mkdir(parents=True, exist_ok=True)

    # ``with_pip=True`` is the load-bearing kwarg here: without it,
    # the venv ships with no pip and ``install_requirements`` would
    # immediately fail. ``upgrade_deps=True`` is a follow-up
    # consideration for ensuring pip itself is current; we leave the
    # default for now to keep the venv build deterministic.
    builder = venv.EnvBuilder(with_pip=True)
    # ``EnvBuilder.create`` accepts a string, not a Path, so coerce.
    builder.create(str(target))


def install_requirements(venv_dir: Path, requirements_path: Path) -> None:
    """Install pinned requirements into the venv via ``pip install -r``.

    Two contract notes:

    1. **The venv's own python is invoked**, not ``sys.executable``.
       Running the venv interpreter is equivalent to "activating" the
       venv for pip's purposes — pip writes packages into the venv's
       ``site-packages`` directory rather than wherever
       ``sys.executable`` happens to point. This is the canonical
       Python idiom for installing into an arbitrary venv from a
       parent process; see PEP 405 / the venv docs.

    2. **No --upgrade flag**. The pinned-version contract means
       re-running install on an existing venv is a no-op when the
       pinned version is already present and only acts when the user
       explicitly bumps the pin in ``setup/requirements.txt``. Adding
       ``--upgrade`` would silently bump packages every install run,
       defeating the reproducibility guarantee.

    Args:
        venv_dir: The directory passed to ``create_venv``.
        requirements_path: Path to a pip-format requirements file.

    Raises:
        InstallError: If the requirements file does not exist, or if
            pip exits with a non-zero return code. The error message
            includes pip's stderr so the user can see the actual
            failure (network, dependency conflict, missing wheel).
    """
    if not requirements_path.is_file():
        raise InstallError(f"requirements file not found: {requirements_path}")

    python_bin = venv_python_path(venv_dir)
    cmd = [str(python_bin), "-m", "pip", "install", "-r", str(requirements_path)]

    # ``capture_output=True`` so pip's stdout / stderr are available
    # for the error message instead of streaming to the parent
    # terminal. ``text=True`` decodes both as UTF-8 strings.
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Surface the actual pip failure in the exception so users see
        # "couldn't resolve X" instead of a generic "install failed".
        raise InstallError(
            f"pip install failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )


def verify_sdk_importable(venv_dir: Path) -> str:
    """Verify ``google.genai`` is importable from inside the venv.

    Runs a small probe script via the venv's python that:

    1. Imports ``google.genai``.
    2. Asserts ``sys.executable`` (which inside the subprocess points
       at the venv's python) lives under the venv path. This catches
       the failure mode where pip silently installed into system
       Python while we thought we were installing into the venv.
    3. Prints ``google.genai.__version__`` so the caller can record
       the installed version (and surface drift in
       ``health_main.py``).

    Args:
        venv_dir: The directory passed to ``create_venv``.

    Returns:
        The installed ``google-genai`` version string (e.g.
        ``"1.33.0"``).

    Raises:
        InstallError: If the probe exits non-zero. The exception
            message includes the probe's stderr so the user sees
            why the import failed (missing module, version mismatch,
            permissions, …).
    """
    python_bin = venv_python_path(venv_dir)
    # Embed a string literal of the venv path so the assert message
    # includes the value the probe expected. Using ``str(venv_dir)``
    # keeps the path normalized to whatever the host OS uses (forward
    # slashes on POSIX, backslashes on Windows after Path round-trip).
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
            f"SDK not importable from venv (exit {result.returncode}):\n" f"{result.stderr.strip()}"
        )
    return result.stdout.strip()
