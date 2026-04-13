"""Image generation adapter — Nano Banana family.

API returns base64-encoded image data inline in JSON. The adapter
decodes and saves to a file, returning only the file path + metadata.
Never outputs raw base64 to stdout (prevents Claude Code token overflow).

Output directory: user-configured output_dir or OS temp dir.
Mutating — requires --execute (enforced at dispatch + defense-in-depth here).

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
from typing import Any

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

_IMAGE_MIME_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Aspect ratios supported by Gemini 3 Pro Image. Kept as a module-level
# tuple so the parser's choices= list and the validation call site share
# one source of truth — add a new value to the tuple and both update.
_ALLOWED_ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)

# Image sizes supported by Gemini 3 Pro Image. ``"1K"`` is the default;
# higher resolutions cost more. Values match the SDK's GenerateImagesConfig
# image_size field at pinned google-genai 1.33.0.
_ALLOWED_IMAGE_SIZES: tuple[str, ...] = ("1K", "2K", "4K")


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the image generation adapter."""
    parser = build_base_parser("Generate images using Gemini")
    add_execute_flag(parser)
    parser.add_argument("prompt", help="Image generation prompt.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for output files (default: OS temp dir).",
    )
    # Phase 7 additions — Gemini 3 Pro Image / Imagen-style controls.
    # Both flags are optional; omitting them preserves the legacy body
    # shape (no imageConfig key at all) so older request paths are
    # byte-identical.
    parser.add_argument(
        "--aspect-ratio",
        default=None,
        choices=_ALLOWED_ASPECT_RATIOS,
        help="Image aspect ratio (Gemini 3 Pro Image).",
    )
    parser.add_argument(
        "--image-size",
        default=None,
        choices=_ALLOWED_IMAGE_SIZES,
        help="Image output resolution (Gemini 3 Pro Image).",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    output_dir: str | None = None,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
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

    generation_config: dict[str, Any] = {"responseModalities": ["IMAGE", "TEXT"]}
    # Only attach imageConfig when at least one flag is set. Omitting
    # the key entirely (instead of sending an empty dict) keeps the
    # legacy request shape byte-identical for the 99% path.
    image_config: dict[str, Any] = {}
    if aspect_ratio is not None:
        image_config["aspectRatio"] = aspect_ratio
    if image_size is not None:
        image_config["imageSize"] = image_size
    if image_config:
        generation_config["imageConfig"] = image_config

    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
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

        emit_json(
            {
                "path": output_path,
                "mime_type": mime,
                "size_bytes": len(image_bytes),
            }
        )
        return

    # No image in response — emit text if available
    text_parts = [p["text"] for p in parts if "text" in p]
    if text_parts:
        emit_output("\n".join(text_parts))
