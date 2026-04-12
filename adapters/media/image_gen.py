"""Image generation adapter — Nano Banana family.

API returns base64-encoded image data inline in JSON. The adapter
decodes and saves to a file, returning only the file path + metadata.
Never outputs raw base64 to stdout (prevents Claude Code token overflow).

Output directory: user-configured output_dir or OS temp dir.
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
    """Return the argument parser for the image generation adapter."""
    parser = build_base_parser("Generate images using Gemini")
    parser.add_argument("prompt", help="Image generation prompt.")
    parser.add_argument(
        "--output-dir", default=None,
        help="Directory for output files (default: OS temp dir).",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    output_dir: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute image generation."""
    if check_dry_run(execute, f"generate image: {prompt}"):
        return

    from core.routing.router import Router
    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("image_gen")

    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }

    response = api_call(
        f"models/{resolved_model}:generateContent",
        body=body,
    )

    parts = response["candidates"][0]["content"]["parts"]
    for part in parts:
        if "inlineData" not in part:
            continue

        image_bytes = base64.b64decode(part["inlineData"]["data"])
        mime = part["inlineData"]["mimeType"]
        ext = _mime_to_ext(mime)

        out_dir = output_dir or config.output_dir
        output_path = _create_output_file(ext, out_dir)
        Path(output_path).write_bytes(image_bytes)

        emit_json({
            "path": str(Path(output_path).resolve()),
            "mime_type": mime,
            "size_bytes": len(image_bytes),
        })
        return

    # No image in response — emit text if available
    from core.adapter.helpers import emit_output
    text_parts = [p["text"] for p in parts if "text" in p]
    if text_parts:
        emit_output("\n".join(text_parts))


def _mime_to_ext(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(mime_type, ".png")


def _create_output_file(suffix: str, output_dir: str | None = None) -> str:
    """Create a unique output file path."""
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="gemini-skill-", suffix=suffix, dir=str(directory))
    os.close(fd)
    return str(Path(path).resolve())
