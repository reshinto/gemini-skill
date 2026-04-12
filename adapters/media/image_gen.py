"""Image generation adapter — Nano Banana family.

API returns base64-encoded image data inline in JSON. The adapter
decodes and saves to a file, returning only the file path + metadata.
Never outputs raw base64 to stdout (prevents Claude Code token overflow).

Output directory: user-configured output_dir or OS temp dir.
Mutating — requires --execute (enforced at dispatch + defense-in-depth here).

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from core.adapter.helpers import (
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

_IMAGE_MIME_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def get_parser() -> argparse.ArgumentParser:
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

    response = api_call(f"models/{resolved_model}:generateContent", body=body)
    parts = extract_parts(response)

    for part in parts:
        if "inlineData" not in part:
            continue

        image_bytes = base64.b64decode(part["inlineData"]["data"])
        mime = part["inlineData"]["mimeType"]
        ext = mime_to_ext(mime, _IMAGE_MIME_MAP, default=".png")

        out_dir = output_dir or config.output_dir
        output_path = create_media_output_file(ext, out_dir)
        Path(output_path).write_bytes(image_bytes)

        emit_json({
            "path": output_path,
            "mime_type": mime,
            "size_bytes": len(image_bytes),
        })
        return

    # No image in response — emit text if available
    text_parts = [p["text"] for p in parts if "text" in p]
    if text_parts:
        emit_output("\n".join(text_parts))
