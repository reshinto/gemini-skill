"""Deep Research adapter (preview) — uses the Interactions API.

NOT generateContent — uses the Interactions API with background=true.
Polls by interaction ID until completed/failed/cancelled. Server-side
state stored by default (store=true, 55d paid / 1d free tier).

Mutating and privacy-sensitive — requires --execute.
Preview with high churn risk.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, check_dry_run, emit_output
from core.infra.client import api_call
from core.infra.config import load_config
from core.infra.sanitize import safe_print


def get_parser():
    """Return the argument parser for the deep research adapter."""
    parser = build_base_parser("Run deep research via Interactions API (preview)")
    parser.add_argument("prompt", help="Research query.")
    parser.add_argument(
        "--resume", default=None,
        help="Resume polling an existing interaction by ID.",
    )
    parser.add_argument(
        "--max-wait", type=int, default=None,
        help="Override max polling time in seconds.",
    )
    return parser


def run(
    prompt: str,
    resume: str | None = None,
    max_wait: int | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute deep research."""
    config = load_config()
    poll_timeout = max_wait or config.deep_research_timeout_seconds

    if resume:
        _poll_interaction(resume, poll_timeout)
        return

    if check_dry_run(execute, f"start deep research: {prompt}"):
        safe_print(
            "WARNING: Deep Research uses the Interactions API with background "
            "execution. Interaction data may be stored server-side."
        )
        return

    safe_print(
        "NOTE: Deep Research uses background Interactions "
        "(stored by default, 55d paid / 1d free tier)."
    )

    # Create interaction via Interactions API
    body: dict[str, Any] = {
        "input": prompt,
        "agent": "deep-research-pro-preview-12-2025",
        "background": True,
    }
    interaction = api_call("interactions", body=body)
    interaction_id = interaction.get("id", "")

    safe_print(f"Research started: {interaction_id}")

    _poll_interaction(interaction_id, poll_timeout)


def _poll_interaction(interaction_id: str, max_wait: int) -> None:
    """Poll an interaction until terminal state or timeout."""
    start = time.time()
    while time.time() - start < max_wait:
        interaction = api_call(f"interactions/{interaction_id}", method="GET")
        status = interaction.get("status", "")

        if status == "completed":
            _emit_result(interaction)
            return
        if status in ("failed", "cancelled"):
            safe_print(f"[{status.upper()}] Research {status}: {interaction.get('error', 'unknown')}")
            return

        time.sleep(15)

    safe_print(
        f"[POLL TIMEOUT] Research still in progress after {max_wait}s.\n"
        f"Resume: /gemini deep_research --resume {interaction_id}"
    )


def _emit_result(interaction: dict[str, Any]) -> None:
    """Extract and emit the research result."""
    config = load_config()
    outputs = interaction.get("outputs", [])
    if outputs:
        text = outputs[-1].get("text", "")
        if text:
            emit_output(text, output_dir=config.output_dir)
            return
    safe_print("[WARNING] No text output in completed interaction.")
