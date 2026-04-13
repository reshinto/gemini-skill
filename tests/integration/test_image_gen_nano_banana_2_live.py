"""Live real-API test for `gemini image_gen` — Nano Banana 2.

Unlike test_image_gen_live.py (which only exercises the DRY RUN path),
this test passes --execute and makes a **billable** call to Nano Banana 2
(`gemini-3.1-flash-image-preview`). It is gated on the same single
``GEMINI_LIVE_TESTS=1`` opt-in as every other live test:

    GEMINI_LIVE_TESTS=1         # opt in to live suite (master switch)
    GEMINI_API_KEY=...          # real key with preview-model access

Run explicitly:

    GEMINI_LIVE_TESTS=1 GEMINI_API_KEY=... \\
        pytest tests/integration/test_image_gen_nano_banana_2_live.py -v

If you want to run the broader live suite without burning image-gen
credits, filter this test out with pytest's -k flag:

    GEMINI_LIVE_TESTS=1 pytest tests/integration/ -k "not nano_banana"

The test writes the generated image to a pytest tmp_path (auto-cleaned),
parses the JSON metadata the adapter prints, and verifies a non-empty
image file with an image/* MIME type landed on disk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "scripts" / "gemini_run.py"
_MODEL = "gemini-3.1-flash-image-preview"

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


def test_image_gen_nano_banana_2_live(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_RUNNER),
            "image_gen",
            "a single small red square centered on a white background",
            "--model",
            _MODEL,
            "--output-dir",
            str(tmp_path),
            "--execute",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr={result.stderr}\nstdout={result.stdout}"
    assert "[DRY RUN]" not in result.stdout, "expected real execution, got dry-run"

    stdout = result.stdout.strip()
    try:
        # emit_json() pretty-prints across multiple lines, so parse the
        # whole stdout rather than just the last line.
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"expected JSON metadata on stdout, got: {stdout!r} ({exc})")

    assert "path" in payload, f"missing path in payload: {payload}"
    assert payload.get("mime_type", "").startswith("image/"), payload
    assert payload.get("size_bytes", 0) > 0, payload

    image_path = Path(payload["path"])
    assert image_path.exists(), f"image file not written: {image_path}"
    assert image_path.stat().st_size == payload["size_bytes"]
    assert image_path.stat().st_size > 100, "suspiciously small image file"
