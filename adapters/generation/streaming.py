"""SSE streaming adapter — real-time text generation output.

Uses the streamGenerateContent endpoint with SSE. Yields text chunks
as they arrive. Text models only.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.adapter.helpers import build_base_parser
from core.infra.client import stream_generate_content
from core.infra.config import load_config
from core.infra.sanitize import safe_print, sanitize


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the streaming adapter."""
    parser = build_base_parser("Stream text generation via SSE")
    parser.add_argument("prompt", help="The text prompt.")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    **kwargs: object,
) -> None:
    """Execute streaming text generation."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("text")

    body: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }

    for chunk in stream_generate_content(resolved_model, body):
        candidates = chunk.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    print(sanitize(part["text"]), end="")

    safe_print("")  # Final newline
