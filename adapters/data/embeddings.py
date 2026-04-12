"""Embedding generation adapter.

Generates vector embeddings for text content using the Gemini
embedding model. Returns the embedding values as JSON.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_json
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser():
    """Return the argument parser for the embeddings adapter."""
    parser = build_base_parser("Generate text embeddings")
    parser.add_argument("text", help="The text to embed.")
    parser.add_argument(
        "--task-type", default=None,
        help="Embedding task type (e.g., RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY).",
    )
    return parser


def run(
    text: str,
    task_type: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute embedding generation."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("embed")

    body: dict[str, Any] = {
        "content": {"parts": [{"text": text}]},
    }
    if task_type:
        body["taskType"] = task_type

    response = api_call(f"models/{resolved_model}:embedContent", body=body)

    embedding = response.get("embedding", {})
    emit_json({
        "model": resolved_model,
        "values": embedding.get("values", []),
        "dimensions": len(embedding.get("values", [])),
    })
