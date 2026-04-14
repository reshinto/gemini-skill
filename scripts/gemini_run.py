#!/usr/bin/env python
"""Skill launcher invoked from SKILL.md.

Two responsibilities, in order:

1. **Python version guard**: refuses to run on Python < 3.9 with a
   clear message instead of a downstream SyntaxError or ImportError.
2. **Venv re-exec**: if the installed-skill venv exists at
   ``~/.claude/skills/gemini/.venv`` AND the launcher was invoked with
   a different Python interpreter, ``os.execv`` into the venv's
   python so dependency isolation is preserved. Local-dev runs (no
   installed venv) skip the re-exec and use whichever Python the
   user invoked.

Then dispatches to ``core.cli.dispatch.main`` with the original argv.

The version-guard block uses Python 2.7-compatible syntax so that
even an extremely old Python invoking this file gets a readable
error rather than a SyntaxError on the f-string in the body. (This
matters because Claude Code can shell out to ``python``,
``python3``, or whatever is on PATH; the launcher is the firewall.)
"""
import os
import sys
from collections.abc import Sequence
from pathlib import Path

_MIN_PYTHON = (3, 9)
_INSTALL_DIR = Path.home() / ".claude" / "skills" / "gemini"


def _check_python_version() -> None:
    """Exit with a clear message if the host Python is too old."""
    if sys.version_info < _MIN_PYTHON:
        sys.exit(
            "gemini-skill requires Python 3.9+. Found: {}.{}".format(
                sys.version_info[0], sys.version_info[1]
            )
        )


def _repo_root() -> str:
    """Return the absolute repository root containing ``core/``."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_repo_root_on_syspath() -> str:
    """Prepend the repository root to ``sys.path`` exactly once."""
    repo_root_path: str = _repo_root()
    if repo_root_path not in sys.path:
        sys.path.insert(0, repo_root_path)
    return repo_root_path


def _skill_venv_python() -> Path:
    """Return the expected path to the installed-skill venv python.

    The path differs by host OS:
    - POSIX: ``~/.claude/skills/gemini/.venv/bin/python``
    - Windows: ``~/.claude/skills/gemini/.venv/Scripts/python.exe``

    The function does NOT check whether the file exists — that's the
    caller's job. Returning the path unconditionally keeps the
    function pure and easy to unit-test.
    """
    if sys.platform == "win32":
        return _INSTALL_DIR / ".venv" / "Scripts" / "python.exe"
    return _INSTALL_DIR / ".venv" / "bin" / "python"


def _maybe_reexec_under_venv() -> None:
    """Re-exec the current process under the skill venv python if needed.

    Three branches:

    1. **Venv missing** — local-dev mode (running from a repo clone
       with no installed skill). Continue without re-exec; the caller's
       repo-root .venv or system Python handles dependencies.
    2. **Already running under the venv** — no-op. Re-exec'ing into
       the same interpreter would create an infinite loop.
    3. **Venv exists but a different python is in use** — call
       ``os.execv`` to swap the current process for the venv python.
       The new process inherits our argv (with the script path
       replaced by the venv python at index 0, per execv contract).

    Why ``os.execv`` instead of ``subprocess.run``? Because execv
    REPLACES the current process — there is no parent / child split,
    no exit code marshaling, no double-buffering of stdout. The
    re-exec'd interpreter IS the launcher from the OS's perspective,
    so signals, terminal control, and exit codes all work exactly as
    if the user had invoked the venv python directly.
    """
    venv_python = _skill_venv_python()
    if not venv_python.exists():
        # Branch 1: no installed venv. Local-dev mode.
        return
    if Path(sys.executable).resolve() == venv_python.resolve():
        # Branch 2: already in the venv.
        return
    # Branch 3: re-exec. The first element of argv must be the
    # interpreter path (execv contract); the rest is our original argv.
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)


def _bootstrap_runtime_environment() -> None:
    """Normalize canonical env keys into ``os.environ`` before dispatch."""
    _ensure_repo_root_on_syspath()

    from core.infra.errors import EnvironmentResolutionError
    from core.infra.runtime_env import bootstrap_runtime_env

    try:
        bootstrap_runtime_env()
    except EnvironmentResolutionError as environment_error:
        sys.exit(str(environment_error))


def main(argv: Sequence[str]) -> None:
    """End-to-end launcher entry point — dispatch to core.cli.dispatch."""
    _check_python_version()
    _bootstrap_runtime_environment()
    _maybe_reexec_under_venv()

    # Ensure the repo root is importable after the no-reexec path.
    _ensure_repo_root_on_syspath()

    from core.cli.dispatch import main as dispatch_main  # noqa: E402

    dispatch_main(list(argv))


if __name__ == "__main__":
    main(sys.argv[1:])
