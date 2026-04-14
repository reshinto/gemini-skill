"""Tests for adapters/generation/plan_review.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _mock_response(
    review_text: str = "VERDICT: REVISE\nTighten the rollback plan.",
) -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": review_text}], "role": "model"},
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "cachedContentTokenCount": 0,
        },
    }


def _registry_root() -> Path:
    return Path(__file__).resolve().parents[3]


class TestPlanReviewParser:
    def test_proposal_is_optional(self) -> None:
        from adapters.generation.plan_review import get_parser

        parser = get_parser()
        parsed_args = parser.parse_args([])
        assert parsed_args.proposal is None

    def test_thinking_flag_is_supported(self) -> None:
        from adapters.generation.plan_review import get_parser

        parser = get_parser()
        parsed_args = parser.parse_args(["proposal text", "--thinking", "off"])
        assert parsed_args.thinking == "off"


class TestPlanReviewModelResolution:
    def test_default_model_is_used_for_thinking_on(self) -> None:
        from adapters.generation.plan_review import _resolve_plan_review_model
        from core.routing.registry import Registry

        registry = Registry(root_dir=_registry_root())
        resolved_model = _resolve_plan_review_model(
            registry=registry,
            requested_model=None,
            thinking_mode="on",
        )

        assert resolved_model.requested_model == "gemini-3.1-pro-preview"
        assert resolved_model.resolved_model == "gemini-3.1-pro-preview"
        assert resolved_model.used_thinking_off_fallback is False

    def test_thinking_off_falls_back_to_flash(self) -> None:
        from adapters.generation.plan_review import _resolve_plan_review_model
        from core.routing.registry import Registry

        registry = Registry(root_dir=_registry_root())
        resolved_model = _resolve_plan_review_model(
            registry=registry,
            requested_model="gemini-3.1-pro-preview",
            thinking_mode="off",
        )

        assert resolved_model.resolved_model == "gemini-2.5-flash"
        assert resolved_model.used_thinking_off_fallback is True

    def test_non_text_model_is_rejected(self) -> None:
        from adapters.generation.plan_review import _resolve_plan_review_model
        from core.infra.errors import CapabilityUnavailableError
        from core.routing.registry import Registry

        registry = Registry(root_dir=_registry_root())

        with pytest.raises(CapabilityUnavailableError, match="does not support text"):
            _resolve_plan_review_model(
                registry=registry,
                requested_model="gemini-live-2.5-flash-preview",
                thinking_mode="on",
            )

    def test_missing_thinking_off_fallback_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from adapters.generation import plan_review
        from core.infra.errors import CapabilityUnavailableError
        from core.routing.registry import Registry

        registry = Registry(root_dir=_registry_root())
        monkeypatch.setattr(
            plan_review,
            "_THINKING_OFF_FALLBACK_MODELS",
            ("gemini-live-2.5-flash-preview",),
        )

        with pytest.raises(CapabilityUnavailableError, match="supports thinking-off"):
            plan_review._resolve_thinking_off_fallback_model(registry=registry)

    def test_unknown_model_is_re_raised(self) -> None:
        from adapters.generation.plan_review import _validate_text_capable_model
        from core.infra.errors import ModelNotFoundError
        from core.routing.registry import Registry

        registry = Registry(root_dir=_registry_root())

        with pytest.raises(ModelNotFoundError):
            _validate_text_capable_model(registry=registry, model_id="missing-model")

    def test_flash_lite_supports_true_thinking_off(self) -> None:
        from adapters.generation.plan_review import _supports_true_thinking_off

        assert _supports_true_thinking_off("gemini-2.5-flash-lite") is True

    def test_flash_supports_true_thinking_off(self) -> None:
        from adapters.generation.plan_review import _supports_true_thinking_off

        assert _supports_true_thinking_off("gemini-2.5-flash") is True


class TestThinkingConfig:
    def test_gemini_3_uses_thinking_level(self) -> None:
        from adapters.generation.plan_review import _build_thinking_config

        config = _build_thinking_config(
            resolved_model_id="gemini-3.1-pro-preview",
            thinking_mode="on",
        )

        assert config == {"thinkingConfig": {"thinkingLevel": "HIGH"}}

    def test_gemini_25_uses_dynamic_budget_for_thinking_on(self) -> None:
        from adapters.generation.plan_review import _build_thinking_config

        config = _build_thinking_config(
            resolved_model_id="gemini-2.5-flash",
            thinking_mode="on",
        )

        assert config == {"thinkingConfig": {"thinkingBudget": -1}}

    def test_gemini_25_uses_zero_budget_for_thinking_off(self) -> None:
        from adapters.generation.plan_review import _build_thinking_config

        config = _build_thinking_config(
            resolved_model_id="gemini-2.5-flash",
            thinking_mode="off",
        )

        assert config == {"thinkingConfig": {"thinkingBudget": 0}}

    def test_gemini_3_thinking_off_is_rejected(self) -> None:
        from adapters.generation.plan_review import _build_thinking_config
        from core.infra.errors import CapabilityUnavailableError

        with pytest.raises(
            CapabilityUnavailableError, match="does not support full thinking-off"
        ):
            _build_thinking_config(
                resolved_model_id="gemini-3.1-pro-preview",
                thinking_mode="off",
            )

    def test_non_gemini_model_family_returns_empty_config(self) -> None:
        from adapters.generation.plan_review import _build_thinking_config

        config = _build_thinking_config(
            resolved_model_id="custom-text-model",
            thinking_mode="on",
        )

        assert config == {}


class TestSessionContext:
    def test_no_session_requested_returns_empty_context(self) -> None:
        from adapters.generation.plan_review import _build_session_context

        session_context = _build_session_context(
            session_id=None,
            continue_session=False,
            force_session=False,
        )

        assert session_context.session_state is None
        assert session_context.session_id is None
        assert session_context.contents == []
        assert session_context.created_session is False

    def test_force_session_creates_new_session(self, tmp_path: Path) -> None:
        from adapters.generation import plan_review

        with patch.object(
            plan_review, "_plan_review_sessions_dir", return_value=tmp_path
        ):
            session_context = plan_review._build_session_context(
                session_id=None,
                continue_session=False,
                force_session=True,
            )

        assert session_context.session_state is not None
        assert session_context.session_id is not None
        assert session_context.created_session is True

    def test_existing_session_history_is_loaded(self, tmp_path: Path) -> None:
        from adapters.generation import plan_review
        from core.state.session_state import SessionState

        session_state = SessionState(sessions_dir=tmp_path)
        session_state.create("review-session")
        session_state.append_message(
            "review-session",
            {"role": "user", "parts": [{"text": "Initial plan"}]},
        )

        with patch.object(
            plan_review, "_plan_review_sessions_dir", return_value=tmp_path
        ):
            session_context = plan_review._build_session_context(
                session_id="review-session",
                continue_session=False,
                force_session=False,
            )

        assert len(session_context.contents) == 1
        assert session_context.created_session is False

    def test_continue_session_uses_most_recent(self, tmp_path: Path) -> None:
        from adapters.generation import plan_review
        from core.state.session_state import SessionState

        session_state = SessionState(sessions_dir=tmp_path)
        session_state.create("older")
        session_state.create("newer")

        with patch.object(
            plan_review, "_plan_review_sessions_dir", return_value=tmp_path
        ):
            session_context = plan_review._build_session_context(
                session_id=None,
                continue_session=True,
                force_session=False,
            )

        assert session_context.session_id == "newer"

    def test_plan_review_sessions_dir_uses_home_config_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from adapters.generation.plan_review import _plan_review_sessions_dir

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert (
            _plan_review_sessions_dir()
            == tmp_path / ".config" / "gemini-skill" / "plan-review-sessions"
        )


class TestNormalizeReviewText:
    def test_empty_text_defaults_to_revise(self) -> None:
        from adapters.generation.plan_review import _normalize_review_text

        assert _normalize_review_text("") == "VERDICT: REVISE"

    def test_missing_verdict_prepends_revise(self) -> None:
        from adapters.generation.plan_review import _normalize_review_text

        normalized_text = _normalize_review_text("Need more rollback detail.")

        assert normalized_text == "VERDICT: REVISE\nNeed more rollback detail."

    def test_approved_verdict_without_body_is_preserved(self) -> None:
        from adapters.generation.plan_review import _normalize_review_text

        normalized_text = _normalize_review_text("VERDICT: APPROVED")

        assert normalized_text == "VERDICT: APPROVED"

    def test_invalid_verdict_is_treated_as_revise(self) -> None:
        from adapters.generation.plan_review import _normalize_review_text

        normalized_text = _normalize_review_text("VERDICT: MAYBE\nUnclear.")

        assert normalized_text == "VERDICT: REVISE\nVERDICT: MAYBE\nUnclear."

    def test_revise_verdict_with_body_is_preserved(self) -> None:
        from adapters.generation.plan_review import _normalize_review_text

        normalized_text = _normalize_review_text("VERDICT: REVISE\nAdd test coverage.")

        assert normalized_text == "VERDICT: REVISE\nAdd test coverage."


class TestReviewOnce:
    def test_review_once_calls_api_with_system_prompt_and_thinking_config(self) -> None:
        from adapters.generation.plan_review import (
            SessionContext,
            ResolvedPlanReviewModel,
            _review_once,
        )

        session_context = SessionContext(
            session_state=None,
            session_id=None,
            contents=[],
            created_session=False,
        )
        resolved_model = ResolvedPlanReviewModel(
            requested_model="gemini-3.1-pro-preview",
            resolved_model="gemini-3.1-pro-preview",
            used_thinking_off_fallback=False,
        )

        with patch(
            "adapters.generation.plan_review.api_call",
            return_value=_mock_response(),
        ) as mock_api_call:
            normalized_text = _review_once(
                proposal="Here is the plan.",
                session_context=session_context,
                resolved_model=resolved_model,
                thinking_mode="on",
            )

        request_body = mock_api_call.call_args.kwargs["body"]
        from adapters.generation.plan_review import _PLAN_REVIEW_SYSTEM_PROMPT

        if _PLAN_REVIEW_SYSTEM_PROMPT:
            assert (
                request_body["systemInstruction"]["parts"][0]["text"]
                == _PLAN_REVIEW_SYSTEM_PROMPT
            )
        else:
            assert "systemInstruction" not in request_body
        assert (
            request_body["generationConfig"]["thinkingConfig"]["thinkingLevel"]
            == "HIGH"
        )
        assert normalized_text.startswith("VERDICT: REVISE")

    def test_review_once_persists_session_messages(self, tmp_path: Path) -> None:
        from adapters.generation import plan_review

        with patch.object(
            plan_review, "_plan_review_sessions_dir", return_value=tmp_path
        ):
            session_context = plan_review._build_session_context(
                session_id="review-session",
                continue_session=False,
                force_session=False,
            )

        resolved_model = plan_review.ResolvedPlanReviewModel(
            requested_model="gemini-2.5-flash",
            resolved_model="gemini-2.5-flash",
            used_thinking_off_fallback=False,
        )

        with patch(
            "adapters.generation.plan_review.api_call",
            return_value=_mock_response("VERDICT: APPROVED\nReady."),
        ):
            plan_review._review_once(
                proposal="Refined plan",
                session_context=session_context,
                resolved_model=resolved_model,
                thinking_mode="off",
            )

        assert session_context.session_state is not None
        assert session_context.session_id is not None
        assert (
            len(session_context.session_state.get_history(session_context.session_id))
            == 2
        )
        assert len(session_context.contents) == 2


class TestRunRepl:
    def test_run_repl_skips_blank_lines_and_stops_on_quit(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.plan_review import SessionContext, _run_repl
        from core.routing.registry import Registry

        session_context = SessionContext(
            session_state=None,
            session_id="review-session",
            contents=[],
            created_session=False,
        )
        registry = Registry(root_dir=_registry_root())

        with (
            patch("builtins.input", side_effect=["", "Revise test plan", "/quit"]),
            patch(
                "adapters.generation.plan_review._review_with_failover",
                return_value="VERDICT: REVISE\nAdd coverage.",
            ) as mock_review_with_failover,
        ):
            _run_repl(
                session_context=session_context,
                registry=registry,
                requested_model=None,
                thinking_mode="on",
                output_dir=None,
            )

        captured_output = capsys.readouterr().out
        assert "[plan_review] session: review-session" in captured_output
        assert "VERDICT: REVISE" in captured_output
        mock_review_with_failover.assert_called_once_with(
            proposal="Revise test plan",
            session_context=session_context,
            registry=registry,
            requested_model=None,
            thinking_mode="on",
        )

    def test_run_repl_without_session_id_skips_session_banner(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.plan_review import SessionContext, _run_repl
        from core.routing.registry import Registry

        session_context = SessionContext(
            session_state=None,
            session_id=None,
            contents=[],
            created_session=False,
        )
        registry = Registry(root_dir=_registry_root())

        with patch("builtins.input", side_effect=["/quit"]):
            _run_repl(
                session_context=session_context,
                registry=registry,
                requested_model=None,
                thinking_mode="on",
                output_dir=None,
            )

        captured_output = capsys.readouterr().out
        assert "[plan_review] session:" not in captured_output
        assert "Enter a plan revision to review." in captured_output

    def test_run_repl_stops_on_done(self) -> None:
        from adapters.generation.plan_review import SessionContext, _run_repl
        from core.routing.registry import Registry

        session_context = SessionContext(
            session_state=None,
            session_id="review-session",
            contents=[],
            created_session=False,
        )
        registry = Registry(root_dir=_registry_root())

        with (
            patch("builtins.input", side_effect=["/done"]),
            patch(
                "adapters.generation.plan_review._review_with_failover"
            ) as mock_review_with_failover,
        ):
            _run_repl(
                session_context=session_context,
                registry=registry,
                requested_model=None,
                thinking_mode="on",
                output_dir=None,
            )

        mock_review_with_failover.assert_not_called()


class TestRun:
    def test_run_requires_proposal_when_stdin_is_not_interactive(self) -> None:
        from adapters.generation.plan_review import run

        with patch("sys.stdin.isatty", return_value=False):
            with pytest.raises(SystemExit, match="requires a proposal argument"):
                run(proposal=None)

    def test_run_with_proposal_emits_review_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.plan_review import run

        with (
            patch(
                "adapters.generation.plan_review.api_call",
                return_value=_mock_response("VERDICT: APPROVED\nReady."),
            ),
            patch("adapters.generation.plan_review.load_config") as mock_load_config,
        ):
            mock_load_config.return_value = MagicMock(output_dir=None)
            run(proposal="Ship the plan.")

        assert "VERDICT: APPROVED" in capsys.readouterr().out

    def test_run_repl_path_delegates_to_run_repl(self, tmp_path: Path) -> None:
        from adapters.generation.plan_review import run

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("adapters.generation.plan_review.load_config") as mock_load_config,
            patch("adapters.generation.plan_review._run_repl") as mock_run_repl,
            patch(
                "adapters.generation.plan_review._plan_review_sessions_dir",
                return_value=tmp_path,
            ),
        ):
            mock_load_config.return_value = MagicMock(output_dir=None)
            run(proposal=None, session="manual-review")

        mock_run_repl.assert_called_once()
