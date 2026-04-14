"""Live smoke test for `gemini imagen` — dry-run path.

Imagen generation is billable per image (same cost profile as
``image_gen``), so the smoke test verifies the DRY RUN path instead of
actually rendering an image. A real-render test exists under a separate
opt-in flag (not added in Phase 8 to keep the matrix cheap).

Gate: requires GEMINI_LIVE_TESTS=1 and GEMINI_API_KEY. Dual-backend
matrix-aware via the ``backend_env`` fixture from conftest — the same
test body runs under SDK-primary and raw-HTTP-primary configurations.

Note: Imagen is SDK-only (no raw HTTP counterpart in this skill). Under
raw HTTP primary, the command should still succeed in dry-run mode
because the dry-run short-circuit fires before any transport is
touched. That's the exact contract the test pins: dry-run works
regardless of backend configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.integration.conftest import run_gemini

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


def test_imagen_dry_run(backend_env: dict[str, str]) -> None:
    """Verify the Imagen adapter's dry-run path under the current backend.

    Runs without ``--execute`` so no API call is made. The assertion
    is that the dispatch + parse + dry-run gate path is intact and the
    process exits cleanly with the ``[DRY RUN]`` marker on stdout.
    """
    result = run_gemini(["imagen", "a red square"], env=backend_env, timeout=30)
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "[DRY RUN]" in result.stdout


def test_imagen_help_under_both_backends(backend_env: dict[str, str]) -> None:
    """``imagen --help`` must succeed under both backend configs.

    Parser construction doesn't touch the transport layer, so this
    test pins the contract that the adapter module imports cleanly
    even when the active backend is raw HTTP (which cannot serve
    Imagen). Imports that reach for ``google.genai`` must be lazy
    enough that a raw-HTTP-primary user who never invokes Imagen
    doesn't pay the SDK import cost.
    """
    result = run_gemini(["imagen", "--help"], env=backend_env, timeout=15)
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "prompt" in result.stdout.lower()
    assert "aspect-ratio" in result.stdout.lower() or "aspect_ratio" in result.stdout.lower()
