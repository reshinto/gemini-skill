"""Deep Research adapter (preview) — uses the Interactions API.

NOT generateContent — uses the Interactions API with background=true.
Polls by interaction ID until completed/failed/cancelled. Server-side
state stored by default (store=true, 55d paid / 1d free tier).

Mutating and privacy-sensitive — requires --execute.
Preview with high churn risk.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import argparse
import time

from core.adapter.helpers import add_execute_flag, build_base_parser, check_dry_run, emit_output
from core.infra.client import api_call
from core.infra.config import Config, load_config
from core.infra.sanitize import safe_print


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the deep research adapter."""
    parser = build_base_parser("Run deep research via Interactions API (preview)")
    add_execute_flag(parser)
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
    **kwargs: object,
) -> None:
    """Execute deep research."""
    config = load_config()
    poll_timeout = max_wait or config.deep_research_timeout_seconds

    if resume:
        # Resume also touches privacy-sensitive server-side storage;
        # gate it behind --execute as defense-in-depth.
        if check_dry_run(execute, f"resume interaction {resume}"):
            return
        _poll_interaction(resume, poll_timeout, config)
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
    body: dict[str, object] = {
        "input": prompt,
        "agent": "deep-research-pro-preview-12-2025",
        "background": True,
    }
    interaction = api_call("interactions", body=body)
    interaction_id_value = interaction.get("id")
    if not isinstance(interaction_id_value, str) or not interaction_id_value:
        safe_print("[ERROR] Interactions API did not return an interaction id.")
        return
    interaction_id = interaction_id_value

    safe_print(f"Research started: {interaction_id}")

    _poll_interaction(interaction_id, poll_timeout, config)


def _poll_interaction(interaction_id: str, max_wait: int, config: Config) -> None:
    """Poll an interaction until terminal state or timeout."""
    start = time.time()
    while time.time() - start < max_wait:
        interaction = api_call(f"interactions/{interaction_id}", method="GET")
        status = interaction.get("status", "")

        if status == "completed":
            _emit_result(interaction, config)
            return
        if status in ("failed", "cancelled"):
            safe_print(f"[{status.upper()}] Research {status}: {interaction.get('error', 'unknown')}")
            return

        time.sleep(15)

    safe_print(
        f"[POLL TIMEOUT] Research still in progress after {max_wait}s.\n"
        f"Resume: /gemini deep_research --resume {interaction_id}"
    )


def _emit_result(interaction: dict[str, object], config: Config) -> None:
    """Extract and emit the research result."""
    outputs = interaction.get("outputs")
    if isinstance(outputs, list) and outputs:
        last_output = outputs[-1]
        if isinstance(last_output, dict):
            text = last_output.get("text")
            if isinstance(text, str) and text:
                emit_output(text, output_dir=config.output_dir)
                return
    safe_print("[WARNING] No text output in completed interaction.")
