"""Computer use adapter (preview).

Enables Gemini to interact with a computer environment via screenshots
and actions. Privacy-sensitive, with dispatcher-managed opt-in.
Preview with high churn risk.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Mapping
from typing import cast

from core.adapter.helpers import build_base_parser, emit_json, emit_output, extract_parts
from core.infra.client import api_call
from core.infra.config import load_config
from core.transport.base import GeminiResponse


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the computer use adapter."""
    parser = build_base_parser("Use Gemini for computer interaction (preview)")
    parser.add_argument("prompt", help="Task description for the model.")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    **kwargs: object,
) -> None:
    """Execute computer use interaction."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("computer_use")

    body: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"computerUse": {}}],
    }

    response = cast(
        GeminiResponse,
        api_call(
            f"models/{resolved_model}:generateContent",
            body=body,
        ),
    )

    parts = extract_parts(response)

    # Collect actions and text
    actions: list[Mapping[str, object]] = []
    text_parts: list[str] = []
    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
        elif "computerUseAction" in part:
            actions.append(part["computerUseAction"])

    if actions:
        emit_json({
            "type": "computer_actions",
            "actions": actions,
            "text": "\n".join(text_parts) if text_parts else None,
        })
    else:
        emit_output("\n".join(text_parts), output_dir=config.output_dir)
