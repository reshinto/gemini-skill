"""Function/tool calling adapter.

Sends a prompt with tool declarations to Gemini and returns any
function calls the model wants to make. Supports multi-turn tool
loops with state preservation via core/routing/tool_state.py.

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/routing/tool_state.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_json, emit_output
from core.infra.client import api_call
from core.infra.config import load_config
from core.routing.tool_state import extract_tool_state


def get_parser():
    """Return the argument parser for the function calling adapter."""
    parser = build_base_parser("Execute function/tool calling")
    parser.add_argument("prompt", help="The text prompt.")
    parser.add_argument(
        "--tools", required=True,
        help="JSON string or file path containing tool declarations.",
    )
    return parser


def run(
    prompt: str,
    tools: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute function calling with tool declarations."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("function_calling")

    # Parse tools — inline JSON or file path
    tools_path = Path(tools)
    if tools_path.is_file():
        tools_obj = json.loads(tools_path.read_text(encoding="utf-8"))
    else:
        tools_obj = json.loads(tools)

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": tools_obj if isinstance(tools_obj, list) else [tools_obj],
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)

    # Extract response parts
    parts = response["candidates"][0]["content"]["parts"]

    # Check for function calls
    tool_parts = extract_tool_state(parts)
    if tool_parts:
        emit_json({
            "type": "function_calls",
            "calls": tool_parts,
        })
    else:
        # Model responded with text instead of function calls
        text_parts = [p["text"] for p in parts if "text" in p]
        emit_output("\n".join(text_parts), output_dir=config.output_dir)
