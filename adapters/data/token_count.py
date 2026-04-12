"""Token counting adapter.

Counts the number of tokens in a prompt or conversation using
the countTokens endpoint. Does not generate content.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_json
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the token count adapter."""
    parser = build_base_parser("Count tokens in a prompt")
    parser.add_argument("text", help="The text to count tokens for.")
    return parser


def run(
    text: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute token counting."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("text")

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
    }

    response = api_call(f"models/{resolved_model}:countTokens", body=body)

    emit_json({
        "model": resolved_model,
        "totalTokens": response.get("totalTokens", 0),
    })
