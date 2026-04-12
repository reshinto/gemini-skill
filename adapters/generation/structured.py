"""Structured output adapter — JSON schema-constrained generation.

Sends a prompt with a JSON schema and returns structured output
matching the schema. Uses responseSchema in generationConfig.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_json, emit_output
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser():
    """Return the argument parser for the structured adapter."""
    parser = build_base_parser("Generate structured JSON output")
    parser.add_argument("prompt", help="The text prompt.")
    parser.add_argument(
        "--schema", required=True,
        help="JSON schema string or path to schema file.",
    )
    return parser


def run(
    prompt: str,
    schema: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute structured generation with JSON schema constraint."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("structured")

    # Parse schema — could be inline JSON or a file path
    schema_path = Path(schema)
    if schema_path.is_file():
        schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        schema_obj = json.loads(schema)

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema_obj,
        },
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)
    text = response["candidates"][0]["content"]["parts"][0]["text"]
    emit_output(text, output_dir=config.output_dir)
