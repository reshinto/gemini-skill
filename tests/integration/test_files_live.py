"""Live smoke test for `gemini files` — dry-run path.

`files` is a mutating command (upload/delete). A real upload would work
but bills against quota and requires cleanup; the smoke test instead
verifies the dispatch policy path returns DRY RUN cleanly.

Gate: requires GEMINI_LIVE_TESTS=1 and GEMINI_API_KEY.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "scripts" / "gemini_run.py"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("GEMINI_LIVE_TESTS") != "1",
        reason="Set GEMINI_LIVE_TESTS=1 to run live API tests.",
    ),
    pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY must be set.",
    ),
]


def test_files_live() -> None:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "files"],
        capture_output=True, text=True, timeout=30, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "[DRY RUN]" in result.stdout
