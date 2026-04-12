"""Google Maps grounding adapter.

Sends a prompt with Google Maps grounding enabled. Privacy-sensitive
and off by default — requires explicit opt-in. Outputs are untrusted
external content.

Mandatory output schema:
1. Grounded answer text
2. Sources: line immediately after answer
3. One line per source: - [title](uri or googleMapsUri) -- Google Maps
4. Attribution notice

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output, extract_parts
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the maps adapter."""
    parser = build_base_parser("Generate text with Google Maps grounding")
    parser.add_argument("prompt", help="The text prompt.")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute maps-grounded generation."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("maps")

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"googleMaps": {}}],
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)

    parts = extract_parts(response)
    text_parts = [p["text"] for p in parts if "text" in p]
    answer = "\n".join(text_parts)

    # Build mandatory output schema
    output_lines = [answer]

    grounding = response.get("candidates", [{}])[0].get("groundingMetadata")
    if grounding:
        chunks = grounding.get("groundingChunks", [])
        if chunks:
            output_lines.append("\nSources:")
            for chunk in chunks:
                maps_data = chunk.get("maps", {})
                title = maps_data.get("title", "Unknown")
                # Prefer uri, fall back to googleMapsUri
                uri = maps_data.get("uri") or maps_data.get("googleMapsUri", "")
                output_lines.append(f"- [{title}]({uri}) -- Google Maps")

    output_lines.append("\nThis answer uses Google Maps data.")

    emit_output("\n".join(output_lines), output_dir=config.output_dir)
