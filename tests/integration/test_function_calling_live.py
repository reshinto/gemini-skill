"""Live smoke test for `gemini function_calling` — one cheap real API call.

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

_TOOLS = (
    '[{"functionDeclarations":[{"name":"get_time",'
    '"description":"Return the current time.",'
    '"parameters":{"type":"object","properties":{}}}]}]'
)

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


def test_function_calling_live() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_RUNNER),
            "function_calling",
            "What time is it? Use the tool.",
            "--tools",
            _TOOLS,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip(), "expected non-empty response"
