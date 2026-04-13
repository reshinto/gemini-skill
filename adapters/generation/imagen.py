"""Imagen text-to-image generation adapter.

Dedicated photoreal image model surface — distinct from the existing
``adapters/media/image_gen.py`` adapter (which uses Gemini-native image
generation via ``generateContent`` with ``responseModalities=["IMAGE"]``).
Imagen lives on the SDK's ``client.models.generate_images`` method and
is SDK-only: there is no raw HTTP REST endpoint this skill supports for
it, so the adapter bypasses the dual-backend coordinator and calls
``get_client()`` directly.

Why not route through the transport facade? Two reasons:

1. The Imagen response carries raw image bytes on each generated image
   object (``response.generated_images[i].image.image_bytes``), not the
   ``{"candidates": [...]}`` REST envelope the normalize layer is built
   around. Plumbing a new envelope shape through the coordinator for
   one SDK-only capability is disproportionate to the value.
2. Imagen is a new capability the raw HTTP backend cannot serve, so
   there's no fallback to coordinate. The direct-SDK call is the
   simplest thing that works and keeps the adapter self-contained.

Mutating — requires ``--execute`` (enforced at dispatch + defense in
depth via ``check_dry_run``). Output bytes always land on disk; stdout
only ever carries a JSON summary with paths + sizes so Claude Code's
tokenizer is never asked to ingest a large base64 blob.

Dependencies: core/transport/sdk/client_factory.py (get_client),
core/adapter/helpers.py, core/infra/config.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from core.adapter.helpers import (
    add_execute_flag,
    build_base_parser,
    check_dry_run,
    create_media_output_file,
    emit_json,
    emit_output,
    mime_to_ext,
)
from core.infra.config import load_config
from core.infra.sanitize import safe_print
from core.transport.sdk.client_factory import get_client

# Aspect ratios Imagen 3 accepts. Same list as the Gemini 3 Pro Image
# flags on ``adapters/media/image_gen.py`` — kept duplicated (rather
# than imported across adapter modules) because the two surfaces are
# independent code paths and one changing shouldn't force the other.
_IMAGEN_ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "3:4",
    "4:3",
    "9:16",
    "16:9",
)

# MIME-to-extension map. Imagen currently returns PNG by default; other
# MIMEs appear only if the caller overrides output_mime_type. Fallback
# to ``.png`` is the safe choice for any unknown value.
_IMAGEN_MIME_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _positive_int(value: str) -> int:
    """argparse helper: reject ``0`` and negatives as hard errors.

    ``type=int`` alone would accept ``--num-images 0`` and the SDK
    would return an empty list downstream. Rejecting at parse time
    surfaces the mistake earlier.
    """
    try:
        n = int(value)
    except ValueError as exc:
        raise ValueError(f"invalid int value: {value!r}") from exc
    if n < 1:
        raise ValueError(f"must be >= 1, got {n}")
    return n


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the imagen adapter."""
    parser = build_base_parser("Generate photoreal images with Imagen")
    add_execute_flag(parser)
    parser.add_argument("prompt", help="Image generation prompt.")
    parser.add_argument(
        "--num-images",
        type=_positive_int,
        default=1,
        help="Number of images to generate (>=1).",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=None,
        choices=_IMAGEN_ASPECT_RATIOS,
        help="Image aspect ratio.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for output files (default: OS temp dir).",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    num_images: int = 1,
    aspect_ratio: str | None = None,
    output_dir: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute Imagen text-to-image generation.

    The SDK's ``client.models.generate_images`` takes a prompt and a
    ``GenerateImagesConfig`` carrying the shape knobs. Each returned
    generated image exposes ``image.image_bytes`` as raw bytes, which
    the adapter writes directly to disk. The stdout summary is a
    single JSON object with the count and a list of per-image
    ``{path, mime_type, size_bytes}`` records.
    """
    if check_dry_run(execute, f"generate Imagen image: {prompt}"):
        return

    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    # Router picks the best model for "imagen" from the registry;
    # caller-supplied ``model=`` always wins so advanced users can
    # pin a specific Imagen version.
    resolved_model = model or router.select_model("imagen")

    # Lazy import of the SDK types so the adapter module still
    # imports cleanly when google-genai isn't installed (the
    # dry-run path above and parser surface remain reachable).
    from google.genai import types

    cfg_kwargs: dict[str, Any] = {"number_of_images": num_images}
    if aspect_ratio is not None:
        cfg_kwargs["aspect_ratio"] = aspect_ratio
    config_obj = types.GenerateImagesConfig(**cfg_kwargs)

    client = get_client()
    response = client.models.generate_images(
        model=resolved_model,
        prompt=prompt,
        config=config_obj,
    )

    generated = getattr(response, "generated_images", None) or []
    if not generated:
        # Safety filters / model refusal — print a clear message so the
        # user knows why no files landed on disk instead of seeing a
        # silent success.
        emit_output("No images were generated (safety filter or model refusal).")
        return

    out_dir = output_dir or config.output_dir
    saved: list[dict[str, Any]] = []
    for item in generated:
        image_obj = getattr(item, "image", None)
        if image_obj is None:
            continue
        image_bytes = getattr(image_obj, "image_bytes", None)
        if image_bytes is None:
            continue
        mime = getattr(image_obj, "mime_type", None) or "image/png"
        ext = mime_to_ext(mime, _IMAGEN_MIME_MAP, default=".png")
        out_path = create_media_output_file(ext, out_dir)
        Path(out_path).write_bytes(image_bytes)
        saved.append(
            {
                "path": out_path,
                "mime_type": mime,
                "size_bytes": len(image_bytes),
            }
        )

    if not saved:
        safe_print("[WARN] Imagen response carried no image bytes.")
        return

    emit_json({"count": len(saved), "images": saved})
