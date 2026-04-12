"""Code execution adapter.

Sends a prompt with code execution enabled. Gemini runs Python code
in a sandboxed environment and returns results. Preserves tool state
(id, tool_type, thought_signature) for multi-turn loops.

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/routing/tool_state.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output, extract_parts
from core.infra.client import api_call
from core.infra.config import load_config
from core.routing.tool_state import extract_tool_state


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the code execution adapter."""
    parser = build_base_parser("Execute code via Gemini sandbox")
    parser.add_argument("prompt", help="The prompt (may include code to run).")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute code execution with Gemini's sandboxed Python."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("code_exec")

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"codeExecution": {}}],
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)
    parts = extract_parts(response)

    # Collect all output components
    output_lines: list[str] = []
    for part in parts:
        if "text" in part:
            output_lines.append(part["text"])
        elif "executableCode" in part:
            code = part["executableCode"].get("code", "")
            output_lines.append(f"```python\n{code}\n```")
        elif "codeExecutionResult" in part:
            outcome = part["codeExecutionResult"].get("outcome", "")
            result_output = part["codeExecutionResult"].get("output", "")
            output_lines.append(f"[{outcome}] {result_output}")

    # Preserve tool state for potential multi-turn
    tool_parts = extract_tool_state(parts)

    full_output = "\n".join(output_lines)
    emit_output(full_output, output_dir=config.output_dir)
