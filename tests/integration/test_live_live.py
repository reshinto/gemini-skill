"""Live smoke test for `gemini live` — parser + help path.

The Live API opens a persistent bidirectional session, which is not
a good fit for the "tiny cheap smoke test" pattern the other live
tests use: the session needs an event loop, eats more budget per run
than a one-shot ``generateContent``, and its streaming output is
harder to assert deterministically in a subprocess. Phase 8 therefore
only pins the parser + async-dispatch-entry path as a live smoke;
a full realtime session round-trip is a separate opt-in test that's
out of scope for the matrix.

Gate: requires GEMINI_LIVE_TESTS=1 and GEMINI_API_KEY. Because Live is
SDK-only, it cannot be served by the raw HTTP backend at all — under
raw-HTTP-primary the command would fail at transport time with
BackendUnavailableError. The help path tested here never reaches the
transport (argparse short-circuits before dispatch), so it still
passes under both matrix cells — that's the exact contract the test
pins.
"""

from __future__ import annotations

import os

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


def test_live_help_under_both_backends(backend_env: dict[str, str]) -> None:
    """``live --help`` must succeed under both backend configurations.

    The help path exits argparse before dispatch ever calls into the
    transport, so it's reachable even under raw-HTTP-primary (where
    Live would otherwise be unreachable). This test pins the contract
    that the adapter module imports cleanly and parser construction
    doesn't require the SDK to be usable at runtime — a bare import
    of ``google.genai`` is OK because the SDK is always pinned in
    the test venv; what matters is that parser construction doesn't
    trigger the Live connect path.
    """
    result = run_gemini(["live", "--help"], env=backend_env, timeout=15)
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "prompt" in result.stdout.lower()
    assert "modality" in result.stdout.lower()


def test_live_adapter_declares_is_async() -> None:
    """Phase 6 + Phase 7 contract: the live adapter must carry
    ``IS_ASYNC = True`` so the dispatch layer runs it via
    ``asyncio.run(run_async(...))`` instead of the sync path.

    Imported directly rather than via subprocess because the marker
    check is a pure Python-level assertion — no transport, no network.
    """
    from adapters.generation import live as live_adapter

    assert live_adapter.IS_ASYNC is True
    assert callable(live_adapter.run_async)
