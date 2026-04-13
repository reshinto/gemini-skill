"""Live smoke test for `gemini file_search` — dry-run path.

`file_search` mixes read-only and mutating subcommands. This smoke test
targets a mutating subcommand and verifies the DRY RUN path rather than
leaving state behind.

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


def test_file_search_live() -> None:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "file_search", "delete", "fileSearchStores/smoke"],
        capture_output=True, text=True, timeout=30, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "[DRY RUN]" in result.stdout
