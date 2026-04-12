"""Live smoke test for `gemini multimodal` — one cheap real API call.

Gate: requires GEMINI_LIVE_TESTS=1 and GEMINI_API_KEY.
Sends a 1x1 PNG inline with a short prompt.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "scripts" / "gemini_run.py"

# Smallest valid PNG: 1x1 transparent pixel.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
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


def test_multimodal_live(tmp_path: Path) -> None:
    img = tmp_path / "pixel.png"
    img.write_bytes(_PNG_1X1)
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "multimodal",
         "Reply with one word describing this image.", "--file", str(img)],
        capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip(), "expected non-empty response"
