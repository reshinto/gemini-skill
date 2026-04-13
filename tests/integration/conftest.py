"""Shared fixtures and helpers for the live integration test suite.

The live integration tests (``tests/integration/test_*_live.py``) exercise
the real Gemini API via ``scripts/gemini_run.py``. Phase 8 adds the
dual-backend matrix: every live test must be runnable under both the SDK
primary path and the raw HTTP primary path so we catch drift between the
two transports.

This module centralizes three things every live test needs:

1. **Backend selection** — a fixture that reads the two priority flags
   from the environment and builds a ``env=`` dict for subprocess
   invocations so the spawned ``gemini_run.py`` inherits the same
   backend config the pytest process was started with. The matrix
   workflow flips ``GEMINI_IS_SDK_PRIORITY`` / ``GEMINI_IS_RAWHTTP_PRIORITY``
   across the two matrix cells.

2. **Runner interpreter resolution** — a constant that points at the
   Python interpreter the live tests should use to invoke
   ``gemini_run.py``. When the installed skill flavor runs (future
   work), this will resolve to ``~/.claude/skills/gemini/.venv/bin/python``;
   for local development it's simply ``sys.executable``.

3. **Backend marker reporting** — a helper that inspects the subprocess
   output + env to report which backend actually handled the call, for
   tests that want to assert ``primary=sdk`` or ``primary=raw_http``
   regardless of what was configured.

Gating is inherited from each live test file's ``pytestmark`` list;
this conftest does not re-gate. Tests that don't carry the
``GEMINI_LIVE_TESTS=1`` + ``GEMINI_API_KEY`` guards will not be
collected in normal pytest runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

import pytest

# The Python interpreter the live tests use to spawn ``gemini_run.py``.
# Today this is always ``sys.executable`` (the dev venv or whatever
# interpreter pytest is running under). When the Phase 5 installer
# eventually produces a skill-local ``.venv`` and the CI matrix runs the
# installed flavor, this resolves to
# ``~/.claude/skills/gemini/.venv/bin/python``. The constant is the
# single-source-of-truth so switching flavors is a one-line edit.
_RUNNER_PYTHON: str = sys.executable

# Repository root — used to compute the path to ``scripts/gemini_run.py``
# and to set the subprocess ``cwd``. ``parents[2]`` walks
# ``tests/integration/conftest.py`` → ``tests/integration`` →
# ``tests`` → ``<repo root>``.
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_RUNNER: Path = _REPO_ROOT / "scripts" / "gemini_run.py"


@pytest.fixture
def runner_python() -> str:
    """Return the interpreter path the live tests should use.

    Fixture-wrapped (not a bare constant) so a future test that needs
    to monkey-patch the interpreter for a single run can override it
    via a local fixture without reaching into the module globals.
    """
    return _RUNNER_PYTHON


@pytest.fixture
def runner_script() -> Path:
    """Return the absolute path to ``scripts/gemini_run.py``."""
    return _RUNNER


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path."""
    return _REPO_ROOT


@pytest.fixture
def backend_env() -> dict[str, str]:
    """Return an env dict for subprocess invocations.

    Copies the current environment and ensures both priority flags are
    set to explicit values so subprocesses see a deterministic backend
    configuration regardless of whether the parent shell happened to
    export them. The fixture does NOT force a specific backend — it
    preserves whatever the CI matrix cell set (or falls back to the
    SDK-primary default if nothing is set).

    The matrix workflow runs pytest twice per Python version:
        - GEMINI_IS_SDK_PRIORITY=true  GEMINI_IS_RAWHTTP_PRIORITY=false
        - GEMINI_IS_SDK_PRIORITY=false GEMINI_IS_RAWHTTP_PRIORITY=true
    Each cell inherits the same fixture and produces a dict the test
    can hand straight to ``subprocess.run(env=...)``.
    """
    env = os.environ.copy()
    env.setdefault("GEMINI_IS_SDK_PRIORITY", "true")
    env.setdefault("GEMINI_IS_RAWHTTP_PRIORITY", "false")
    return env


def run_gemini(
    args: list[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``gemini_run.py`` as a subprocess under the runner interpreter.

    Centralizes the subprocess invocation so every live test shares:
    - the same interpreter (``_RUNNER_PYTHON``),
    - the same cwd (``_REPO_ROOT``),
    - the same timeout default,
    - the same ``capture_output=True`` + ``text=True`` shape.

    Tests that need a non-standard flag (e.g. a longer timeout for a
    streaming call) override the kwargs directly.

    Args:
        args: CLI arguments after the runner script — e.g.
            ``["text", "Hello"]``.
        env: Environment dict for the subprocess. When ``None``, the
            parent environment is inherited unchanged.
        timeout: Subprocess timeout in seconds.

    Returns:
        The ``CompletedProcess`` result with ``stdout`` / ``stderr``
        captured as text.
    """
    cmd: list[str] = [_RUNNER_PYTHON, str(_RUNNER), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(_REPO_ROOT),
        env=dict(env) if env is not None else None,
    )


def current_primary_backend(env: Mapping[str, str] | None = None) -> str:
    """Return ``"sdk"`` or ``"raw_http"`` based on the priority flags.

    Mirrors the resolution rule in ``core/infra/config.py``:
    SDK wins whenever ``GEMINI_IS_SDK_PRIORITY`` is truthy; otherwise
    raw HTTP is primary. Unknown values are treated as False. Used by
    tests that want to assert against the matrix cell's configured
    primary without hard-coding the flag parsing.
    """
    source = env if env is not None else os.environ
    return (
        "sdk"
        if source.get("GEMINI_IS_SDK_PRIORITY", "").strip().lower() in ("true", "1", "yes")
        else "raw_http"
    )
