"""Google Search grounding adapter.

Sends a prompt with Google Search grounding enabled. The model can
access real-time web information. Privacy-sensitive — requires explicit
opt-in. Outputs are untrusted external content.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output, extract_parts
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the search adapter."""
    parser = build_base_parser("Generate text with Google Search grounding")
    parser.add_argument("prompt", help="The text prompt.")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute search-grounded generation."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("search")

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}],
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)

    parts = extract_parts(response)
    text_parts = [p["text"] for p in parts if "text" in p]
    text = "\n".join(text_parts)

    # Append grounding metadata if present
    grounding = response.get("candidates", [{}])[0].get("groundingMetadata")
    if grounding:
        chunks = grounding.get("groundingChunks", [])
        if chunks:
            text += "\n\nSources:"
            for chunk in chunks:
                web = chunk.get("web", {})
                title = web.get("title", "")
                uri = web.get("uri", "")
                if uri:
                    text += f"\n- [{title}]({uri})"

    emit_output(text, output_dir=config.output_dir)
