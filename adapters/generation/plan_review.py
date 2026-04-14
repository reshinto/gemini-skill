"""Plan review adapter for iterative planning conversations with Gemini."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from core.adapter.helpers import build_base_parser, emit_output, extract_text
from core.infra.client import api_call
from core.infra.config import load_config
from core.infra.errors import CapabilityUnavailableError, ModelNotFoundError
from core.infra.sanitize import safe_print
from core.routing.registry import Registry
from core.state.session_state import SessionState
from core.transport.base import Content, GeminiResponse

_DEFAULT_PLAN_REVIEW_MODEL: str = "gemini-3.1-pro-preview"
_DEFAULT_PLAN_REVIEW_MODELS: tuple[str, ...] = (
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
_THINKING_ON: str = "on"
_THINKING_OFF: str = "off"
_PLAN_REVIEW_SESSION_DIRNAME: str = "plan-review-sessions"
_THINKING_OFF_FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
_PLAN_REVIEW_SYSTEM_PROMPT: str = ""


@dataclass
class SessionContext:
    """Mutable plan-review session state for one CLI invocation."""

    session_state: SessionState | None
    session_id: str | None
    contents: list[Content]
    created_session: bool


@dataclass(frozen=True)
class ResolvedPlanReviewModel:
    """Selected plan-review model after thinking-mode normalization."""

    requested_model: str
    resolved_model: str
    used_thinking_off_fallback: bool


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the plan-review adapter."""
    parser: argparse.ArgumentParser = build_base_parser(
        "Review an implementation plan with Gemini"
    )
    parser.add_argument(
        "proposal",
        nargs="?",
        default=None,
        help="Plan text to review. Omit to start an interactive REPL.",
    )
    parser.add_argument(
        "--thinking",
        choices=(_THINKING_ON, _THINKING_OFF),
        default=_THINKING_ON,
        help="Enable or disable explicit thinking configuration.",
    )
    return parser


def run(
    proposal: str | None = None,
    model: str | None = None,
    session: str | None = None,
    continue_session: bool = False,
    thinking: str = _THINKING_ON,
    execute: bool = False,
    **kwargs: object,
) -> None:
    """Run one plan review turn or an interactive REPL."""
    del execute
    del kwargs

    config = load_config()
    registry_root: Path = Path(__file__).parent.parent.parent
    registry: Registry = Registry(root_dir=registry_root)
    resolved_model: ResolvedPlanReviewModel = _resolve_plan_review_model(
        registry=registry,
        requested_model=model,
        thinking_mode=thinking,
    )

    if proposal is None:
        if not sys.stdin.isatty():
            raise SystemExit(
                "plan_review requires a proposal argument when stdin is not interactive."
            )
        session_context: SessionContext = _build_session_context(
            session_id=session,
            continue_session=continue_session,
            force_session=True,
        )
        _run_repl(
            session_context=session_context,
            resolved_model=resolved_model,
            thinking_mode=thinking,
            output_dir=config.output_dir,
        )
        return

    session_context = _build_session_context(
        session_id=session,
        continue_session=continue_session,
        force_session=False,
    )
    review_text: str = _review_with_failover(
        proposal=proposal,
        session_context=session_context,
        registry=registry,
        requested_model=model,
        thinking_mode=thinking,
    )
    emit_output(review_text, output_dir=config.output_dir)


def _plan_review_candidate_models(*, requested_model: str | None) -> tuple[str, ...]:
    """Return ordered candidate models for plan_review failover."""
    if requested_model is not None:
        return (requested_model,)

    return _DEFAULT_PLAN_REVIEW_MODELS


def _review_with_failover(
    *,
    proposal: str,
    session_context: SessionContext,
    registry: Registry,
    requested_model: str | None,
    thinking_mode: str,
) -> str:
    """Run plan_review with model failover.

    If the caller explicitly requested a model, do not silently fall back.
    If no model was requested, try the ranked defaults in order.
    """
    last_error: Exception | None = None
    candidate_model: str

    for candidate_model in _plan_review_candidate_models(
        requested_model=requested_model
    ):
        try:
            resolved_model: ResolvedPlanReviewModel = _resolve_plan_review_model(
                registry=registry,
                requested_model=candidate_model,
                thinking_mode=thinking_mode,
            )
            return _review_once(
                proposal=proposal,
                session_context=session_context,
                resolved_model=resolved_model,
                thinking_mode=thinking_mode,
            )
        except Exception as exc:
            last_error = exc
            if requested_model is not None:
                raise
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("No candidate model available for plan_review.")


def _resolve_plan_review_model(
    *,
    registry: Registry,
    requested_model: str | None,
    thinking_mode: str,
) -> ResolvedPlanReviewModel:
    """Validate the requested model and normalize thinking-off fallback."""
    requested_model_id: str = requested_model or _DEFAULT_PLAN_REVIEW_MODEL
    _validate_text_capable_model(registry=registry, model_id=requested_model_id)

    if thinking_mode == _THINKING_OFF and not _supports_true_thinking_off(
        requested_model_id
    ):
        fallback_model_id: str = _resolve_thinking_off_fallback_model(registry=registry)
        return ResolvedPlanReviewModel(
            requested_model=requested_model_id,
            resolved_model=fallback_model_id,
            used_thinking_off_fallback=True,
        )

    return ResolvedPlanReviewModel(
        requested_model=requested_model_id,
        resolved_model=requested_model_id,
        used_thinking_off_fallback=False,
    )


def _validate_text_capable_model(*, registry: Registry, model_id: str) -> None:
    """Reject unknown or non-text models for plan review."""
    try:
        model_record = registry.get_model(model_id)
    except ModelNotFoundError:
        raise

    capabilities: list[str] = model_record.get("capabilities", [])
    if "text" not in capabilities:
        raise CapabilityUnavailableError(
            f"Model '{model_id}' does not support text generation required by plan_review."
        )


def _resolve_thinking_off_fallback_model(*, registry: Registry) -> str:
    """Return the highest-ranked text model that supports true thinking-off."""
    candidate_model_id: str
    for candidate_model_id in _THINKING_OFF_FALLBACK_MODELS:
        try:
            _validate_text_capable_model(registry=registry, model_id=candidate_model_id)
        except (CapabilityUnavailableError, ModelNotFoundError):
            continue
        return candidate_model_id

    raise CapabilityUnavailableError(
        "No text-capable model in the configured fallback order supports thinking-off."
    )


def _supports_true_thinking_off(model_id: str) -> bool:
    """Return True only for model families that support a true off switch."""
    if model_id.startswith("gemini-2.5-flash-lite"):
        return True
    if model_id.startswith("gemini-2.5-flash"):
        return True
    return False


def _build_thinking_config(
    *, resolved_model_id: str, thinking_mode: str
) -> dict[str, object]:
    """Build the request ``thinkingConfig`` block for the selected model."""
    if resolved_model_id.startswith("gemini-3"):
        if thinking_mode == _THINKING_OFF:
            raise CapabilityUnavailableError(
                f"Model '{resolved_model_id}' does not support full thinking-off."
            )
        return {"thinkingConfig": {"thinkingLevel": "HIGH"}}

    if resolved_model_id.startswith("gemini-2.5"):
        thinking_budget: int = -1 if thinking_mode == _THINKING_ON else 0
        return {"thinkingConfig": {"thinkingBudget": thinking_budget}}

    return {}


def _build_session_context(
    *,
    session_id: str | None,
    continue_session: bool,
    force_session: bool,
) -> SessionContext:
    """Prepare session history for one plan-review invocation."""
    resolved_session_id: str | None = session_id

    if continue_session and resolved_session_id is None:
        session_state_for_lookup: SessionState = SessionState(
            sessions_dir=_plan_review_sessions_dir()
        )
        resolved_session_id = session_state_for_lookup.most_recent()

    if resolved_session_id is None and not force_session:
        return SessionContext(
            session_state=None,
            session_id=None,
            contents=[],
            created_session=False,
        )

    if resolved_session_id is None:
        resolved_session_id = _auto_session_id()

    session_state: SessionState = SessionState(sessions_dir=_plan_review_sessions_dir())
    created_session: bool = False
    contents: list[Content] = []

    if session_state.exists(resolved_session_id):
        contents = session_state.get_history(resolved_session_id)
    else:
        session_state.create(resolved_session_id)
        created_session = True

    return SessionContext(
        session_state=session_state,
        session_id=resolved_session_id,
        contents=contents,
        created_session=created_session,
    )


def _plan_review_sessions_dir() -> Path:
    """Return the dedicated session directory for plan-review conversations."""
    config_directory: Path = Path.home() / ".config" / "gemini-skill"
    return config_directory / _PLAN_REVIEW_SESSION_DIRNAME


def _auto_session_id() -> str:
    """Create a deterministic session id prefix for interactive review sessions."""
    timestamp_text: str = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"plan-review-{timestamp_text}"


def _run_repl(
    *,
    session_context: SessionContext,
    resolved_model: ResolvedPlanReviewModel,
    thinking_mode: str,
    output_dir: str | None,
) -> None:
    """Run the manual plan-review REPL."""
    if session_context.session_id is not None:
        safe_print(f"[plan_review] session: {session_context.session_id}")
    safe_print("Enter a plan revision to review. Use /done to accept or /quit to stop.")

    while True:
        proposal_text: str = input("plan_review> ").strip()
        if proposal_text == "":
            continue
        if proposal_text == "/quit":
            return
        if proposal_text == "/done":
            return

        review_text: str = _review_once(
            proposal=proposal_text,
            session_context=session_context,
            resolved_model=resolved_model,
            thinking_mode=thinking_mode,
        )
        emit_output(review_text, output_dir=output_dir)


def _review_once(
    *,
    proposal: str,
    session_context: SessionContext,
    resolved_model: ResolvedPlanReviewModel,
    thinking_mode: str,
) -> str:
    """Send one review turn to Gemini and update session state if active."""
    request_contents: list[Content] = list(session_context.contents)
    user_message: Content = {"role": "user", "parts": [{"text": proposal}]}
    request_contents.append(user_message)

    generation_config: dict[str, object] = {
        "maxOutputTokens": 8192,
        "temperature": 0.2,
    }
    generation_config.update(
        _build_thinking_config(
            resolved_model_id=resolved_model.resolved_model,
            thinking_mode=thinking_mode,
        )
    )

    request_body: dict[str, object] = {
        "contents": request_contents,
        "generationConfig": generation_config,
    }

    if _PLAN_REVIEW_SYSTEM_PROMPT:
        request_body["systemInstruction"] = {
            "parts": [{"text": _PLAN_REVIEW_SYSTEM_PROMPT}]
        }

    response = cast(
        GeminiResponse,
        api_call(
            f"models/{resolved_model.resolved_model}:generateContent",
            body=request_body,
        ),
    )

    normalized_text: str = _normalize_review_text(extract_text(response))
    if (
        session_context.session_state is not None
        and session_context.session_id is not None
    ):
        response_content: Content = response["candidates"][0]["content"]
        session_context.session_state.append_message(
            session_context.session_id, user_message
        )
        session_context.session_state.append_message(
            session_context.session_id, response_content
        )
        session_context.contents.append(user_message)
        session_context.contents.append(response_content)

    return normalized_text


def _normalize_review_text(raw_text: str) -> str:
    """Ensure every response starts with the required verdict line."""
    stripped_text: str = raw_text.strip()
    if stripped_text == "":
        return "VERDICT: REVISE"

    stripped_lines: list[str] = stripped_text.splitlines()
    first_line: str = stripped_lines[0].strip()
    remaining_lines: list[str] = stripped_lines[1:]

    normalized_verdict: str | None = _normalize_verdict_line(first_line)
    if normalized_verdict is None:
        return f"VERDICT: REVISE\n{stripped_text}"

    remaining_text: str = "\n".join(remaining_lines).strip()
    if remaining_text == "":
        return normalized_verdict
    return f"{normalized_verdict}\n{remaining_text}"


def _normalize_verdict_line(first_line: str) -> str | None:
    """Normalize the first line to the strict verdict contract when possible."""
    if not first_line.upper().startswith("VERDICT:"):
        return None

    verdict_value: str = first_line.split(":", 1)[1].strip().upper()
    if verdict_value.startswith("APPROVED"):
        return "VERDICT: APPROVED"
    if verdict_value.startswith("REVISE"):
        return "VERDICT: REVISE"
    return None
