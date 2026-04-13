"""Text generation adapter for the Gemini API.

Supports single-turn and multi-turn (session) conversations.
Uses core/infra/client.py for API access and core/state/session_state.py
for conversation history management.

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/routing/router.py, core/state/session_state.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output, extract_text
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the text adapter."""
    parser = build_base_parser("Generate text using Gemini models")
    parser.add_argument("prompt", help="The text prompt to send.")
    parser.add_argument(
        "--system", default=None,
        help="System instruction for the model.",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=8192,
        help="Maximum output tokens.",
    )
    parser.add_argument(
        "--temperature", type=float, default=1.0,
        help="Sampling temperature (0.0-2.0).",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 1.0,
    session: str | None = None,
    continue_session: bool = False,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute text generation.

    Builds the request, calls the API, and emits the response.
    Supports multi-turn sessions via --session/--continue flags.
    """
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("text")

    # Build contents array
    contents: list[dict[str, Any]] = []

    if session or continue_session:
        from core.state.session_state import SessionState
        config_dir = Path.home() / ".config" / "gemini-skill"
        sessions = SessionState(sessions_dir=config_dir / "sessions")
        session_id = session
        if continue_session and not session_id:
            session_id = sessions.most_recent()
        if session_id and sessions.exists(session_id):
            contents = sessions.get_history(session_id)
        elif session_id:
            sessions.create(session_id)

    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    response = api_call(
        f"models/{resolved_model}:generateContent",
        body=body,
    )

    # Extract text from response (raises ValueError on safety blocks)
    text = extract_text(response)

    # Save session if active
    if session or continue_session:
        session_id_final = session_id or session
        if session_id_final:
            response_content = response["candidates"][0]["content"]
            sessions.append_message(session_id_final, {"role": "user", "parts": [{"text": prompt}]})
            sessions.append_message(session_id_final, response_content)

    emit_output(text, output_dir=config.output_dir)
