"""Music generation adapter — Lyria 3.

API returns base64-encoded audio inline in JSON. Adapter decodes
and saves to file. 30s cap, SynthID watermark.
Mutating — requires --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, check_dry_run, emit_json
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser():
    """Return the argument parser for the music generation adapter."""
    parser = build_base_parser("Generate music using Lyria")
    parser.add_argument("prompt", help="Music generation prompt.")
    parser.add_argument(
        "--output-dir", default=None,
        help="Directory for output files.",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    output_dir: str | None = None,
    execute: bool = False,
    **kwargs: Any,
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

    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]},
    }

    response = api_call(
        f"models/{resolved_model}:generateContent",
        body=body,
    )

    parts = response["candidates"][0]["content"]["parts"]
    for part in parts:
        if "inlineData" not in part:
            continue

        audio_bytes = base64.b64decode(part["inlineData"]["data"])
        mime = part["inlineData"]["mimeType"]
        ext = _mime_to_ext(mime)

        out_dir = output_dir or config.output_dir
        output_path = _create_output_file(ext, out_dir)
        Path(output_path).write_bytes(audio_bytes)

        emit_json({
            "path": str(Path(output_path).resolve()),
            "mime_type": mime,
            "size_bytes": len(audio_bytes),
        })
        return

    # No audio — emit text if available
    from core.adapter.helpers import emit_output
    text_parts = [p["text"] for p in parts if "text" in p]
    if text_parts:
        emit_output("\n".join(text_parts))


def _mime_to_ext(mime_type: str) -> str:
    """Convert audio MIME type to file extension."""
    mapping = {
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
    }
    return mapping.get(mime_type, ".wav")


def _create_output_file(suffix: str, output_dir: str | None = None) -> str:
    """Create a unique output file path."""
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="gemini-skill-", suffix=suffix, dir=str(directory))
    os.close(fd)
    return str(Path(path).resolve())
