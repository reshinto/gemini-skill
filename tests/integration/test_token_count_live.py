"""Live smoke test for `gemini token_count` — one cheap real API call.

Token counting is free. Gate: requires GEMINI_LIVE_TESTS=1 and GEMINI_API_KEY.
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


def test_token_count_live() -> None:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "token_count", "hello world"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip(), "expected token count output"
