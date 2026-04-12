"""Multimodal input adapter — image/audio/video/PDF/URL input.

Sends files or URLs as inline content parts alongside a text prompt.
Handles file reading and MIME detection for local files.

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/infra/mime.py, core/state/identity.py
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output, extract_text
from core.infra.client import api_call
from core.infra.config import load_config
from core.infra.mime import guess_mime_for_path


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the multimodal adapter."""
    parser = build_base_parser("Send multimodal content to Gemini")
    parser.add_argument("prompt", help="Text prompt accompanying the media.")
    parser.add_argument(
        "--file", action="append", default=[],
        help="Path to a local file to include (can be repeated).",
    )
    parser.add_argument(
        "--mime", default=None,
        help="Override MIME type for the file.",
    )
    return parser


def run(
    prompt: str,
    file: list[str] | None = None,
    mime: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute multimodal generation with file inputs."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("multimodal")

    parts: list[dict[str, Any]] = []

    # Add file parts
    for file_path in (file or []):
        path = Path(file_path)
        mime_type = mime or guess_mime_for_path(path)
        data = base64.b64encode(path.read_bytes()).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": data,
            }
        })

    # Add text prompt
    parts.append({"text": prompt})

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)
    text = extract_text(response)
    emit_output(text, output_dir=config.output_dir)
