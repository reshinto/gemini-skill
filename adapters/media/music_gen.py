"""Music generation adapter — Lyria 3.

API returns base64-encoded audio inline in JSON. Adapter decodes
and saves to file. 30s cap, SynthID watermark.
Mutating — requires --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
from typing import cast

from core.adapter.helpers import (
    add_execute_flag,
    build_base_parser,
    check_dry_run,
    create_media_output_file,
    emit_json,
    emit_output,
    extract_parts,
    mime_to_ext,
)
from core.infra.client import api_call
from core.infra.config import load_config
from core.transport.base import GeminiResponse

_AUDIO_MIME_MAP = {
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
}


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the music generation adapter."""
    parser = build_base_parser("Generate music using Lyria")
    add_execute_flag(parser)
    parser.add_argument("prompt", help="Music generation prompt.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for output files.",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    output_dir: str | None = None,
    execute: bool = False,
    **kwargs: object,
) -> None:
    """Execute music generation."""
    if check_dry_run(execute, f"generate music: {prompt}"):
        return

    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("music_gen")

    body: dict[str, object] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]},
    }

    response = cast(GeminiResponse, api_call(f"models/{resolved_model}:generateContent", body=body))
    parts = extract_parts(response)

    for part in parts:
        if "inlineData" not in part:
            continue

        audio_bytes = base64.b64decode(part["inlineData"]["data"])
        mime = part["inlineData"]["mimeType"]
        ext = mime_to_ext(mime, _AUDIO_MIME_MAP, default=".wav")

        out_dir = output_dir or config.output_dir
        output_path = create_media_output_file(ext, out_dir)
        Path(output_path).write_bytes(audio_bytes)

        emit_json(
            {
                "path": output_path,
                "mime_type": mime,
                "size_bytes": len(audio_bytes),
            }
        )
        return

    # No audio — emit text if available
    text_parts = [p["text"] for p in parts if "text" in p]
    if text_parts:
        emit_output("\n".join(text_parts))
