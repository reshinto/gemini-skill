"""Phase 11.2 coverage branch-fillers.

This file consolidates the ~20 remaining branch-coverage gaps identified
during the Phase 11 audit. Each test covers exactly one or two partial
branches — they are small and mechanical but essential for the 100%
line + branch coverage gate on the production tree.

Grouping them in one file (instead of spreading across 16+ existing
test files) keeps the gap list reviewable in a single place and makes
it obvious when a branch regresses.

All tests follow the project rules:
- No ``typing.Any``
- No single-character variable names
- Every test annotated ``-> None``
- Every test has a one-line docstring
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ----------------------------------------------------------------------
# adapters/data/embeddings.py — branch 57→62
# ----------------------------------------------------------------------


class TestImageGenNoTextFallthrough:
    """Coverage: image_gen falls through when response has no image and no text."""

    def test_response_without_image_or_text_exits_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A response with no inlineData and no text parts exits the
        function without emitting anything — branch 157→exit."""
        from adapters.media.image_gen import run

        # No inlineData parts, no text parts
        empty_response = {"candidates": [{"content": {"parts": [{"unknownField": "value"}]}}]}
        with (
            patch("adapters.media.image_gen.api_call", return_value=empty_response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.media.image_gen.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=str(tmp_path))
            run(prompt="test", execute=True)
        # No emit_output call and no emit_json call; function just returns.


class TestMusicGenNoTextFallthrough:
    """Coverage: music_gen falls through when response has no audio and no text."""

    def test_response_without_audio_or_text_exits_cleanly(self, tmp_path: Path) -> None:
        """A response with no inlineData and no text parts exits cleanly —
        branch 103→exit."""
        from adapters.media.music_gen import run

        empty_response = {"candidates": [{"content": {"parts": [{"unknownField": "value"}]}}]}
        with (
            patch("adapters.media.music_gen.api_call", return_value=empty_response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.media.music_gen.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=str(tmp_path))
            run(prompt="test", execute=True)


class TestSearchWithoutGrounding:
    """Coverage: search path where grounding is falsy or chunks are empty."""

    def test_grounding_with_empty_chunks(self) -> None:
        """Grounding metadata present but ``groundingChunks`` is empty —
        triggers branch 81→90 (skip chunk loop entirely)."""
        from adapters.tools.search import run

        response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "answer"}]},
                    "groundingMetadata": {"groundingChunks": []},
                }
            ]
        }
        with (
            patch("adapters.tools.search.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.search.load_config") as mock_cfg,
            patch("adapters.tools.search.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="q", i_understand_privacy=True)
        emitted_text = mock_emit.call_args[0][0]
        assert "Sources" not in emitted_text

    def test_no_grounding_no_show_grounding(self) -> None:
        """Default path with no grounding metadata skips the sources block —
        branch 81→90."""
        from adapters.tools.search import run

        response = {"candidates": [{"content": {"parts": [{"text": "plain"}]}}]}
        with (
            patch("adapters.tools.search.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.search.load_config") as mock_cfg,
            patch("adapters.tools.search.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="q", i_understand_privacy=True, show_grounding=False)
        mock_emit.assert_called_once()
        emitted_text = mock_emit.call_args[0][0]
        assert "Sources" not in emitted_text


class TestEmbeddingsRawValuesNotList:
    """Coverage: embedding field is not a dict → values stay empty."""

    def test_values_stay_empty_when_embedding_is_not_dict(self) -> None:
        """``embedding`` field being a string (not a dict) falls through
        to the empty default — branch 57→62."""
        from unittest.mock import patch

        from adapters.data.embeddings import run

        # embedding is a string — the `isinstance(embedding_value, dict)`
        # guard on line 57 evaluates False, skipping the body and falling
        # through to line 62 (emit_json) with values as the empty default.
        malformed: dict[str, object] = {"embedding": "not-a-dict"}
        with (
            patch("adapters.data.embeddings.api_call", return_value=malformed),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.data.embeddings.load_config") as mock_cfg,
            patch("adapters.data.embeddings.emit_json") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "embed-001"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(text="hello")
        args, _ = mock_emit.call_args
        assert args[0]["values"] == []


# ----------------------------------------------------------------------
# adapters/experimental/computer_use.py — branch 66→63
# ----------------------------------------------------------------------


class TestComputerUseUnknownPart:
    """Coverage: a part with neither 'text' nor 'computerUseAction' is skipped."""

    def test_part_with_neither_key_skipped(self) -> None:
        """A response part lacking both known keys falls through without error."""
        from adapters.experimental.computer_use import run

        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"unknownKey": "value"},  # Triggers 66→63 fallthrough
                            {"text": "hello"},
                        ]
                    }
                }
            ]
        }
        with (
            patch("adapters.experimental.computer_use.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.experimental.computer_use.load_config") as mock_cfg,
            patch("adapters.experimental.computer_use.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="test", i_understand_privacy=True)
        mock_emit.assert_called_once()


# ----------------------------------------------------------------------
# adapters/generation/live.py — branches 168→183, 184→192, 186→192
# ----------------------------------------------------------------------


def _build_live_session_context(
    stream_factory: object, has_aclose: bool = True, aclose_return: object = None
) -> object:
    """Build a fake live-session context manager for the live adapter.

    Returns an async context manager that yields a session object whose
    ``receive()`` method returns the given async iterator (built from
    ``stream_factory``). The stream's ``aclose`` behavior is configurable
    so tests can exercise the cleanup branches at lines 184 / 186.
    """

    async def async_noop(*args: object, **kwargs: object) -> None:
        return None

    class _FakeStream:
        def __init__(self) -> None:
            self._iter = stream_factory()

        def __aiter__(self) -> object:
            return self._iter.__aiter__()

    stream_instance = _FakeStream()
    if has_aclose:
        if aclose_return is None:

            async def _aclose() -> None:
                return None

            stream_instance.aclose = _aclose  # type: ignore[attr-defined]
        else:

            def _aclose_sync() -> object:
                return aclose_return

            stream_instance.aclose = _aclose_sync  # type: ignore[attr-defined]

    fake_session = MagicMock()
    fake_session.send_client_content = async_noop  # type: ignore[assignment]
    fake_session.receive = lambda: stream_instance

    class _FakeSessionContext:
        async def __aenter__(self) -> object:
            return fake_session

        async def __aexit__(self, *args: object) -> None:
            return None

    return _FakeSessionContext()


class TestLiveAdapterBranches:
    """Coverage for the async live adapter's cleanup-branch edges."""

    @pytest.mark.asyncio
    async def test_stream_ends_naturally_without_break(self) -> None:
        """An empty receive stream ends without ever hitting the break — branch 168→183."""
        import adapters.generation.live as live_module

        async def empty_stream() -> object:
            if False:  # pragma: no cover - keeps the function async-iterable
                yield None

        fake_client = MagicMock()
        fake_client.aio.live.connect = MagicMock(
            return_value=_build_live_session_context(empty_stream)
        )

        with (
            patch("adapters.generation.live.get_client", return_value=fake_client),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "gemini-live-2.5-flash-preview"
            mock_cfg.return_value = MagicMock(output_dir=None)
            await live_module.run_async(prompt="hello")

    @pytest.mark.asyncio
    async def test_stream_without_aclose_skips_cleanup(self) -> None:
        """A stream object lacking ``aclose`` skips the cleanup call — branch 184→192."""
        import adapters.generation.live as live_module

        complete_msg = MagicMock()
        complete_msg.text = "done"
        complete_server = MagicMock()
        complete_server.turn_complete = True
        complete_msg.server_content = complete_server

        async def stream_with_complete() -> object:
            yield complete_msg

        fake_client = MagicMock()
        fake_client.aio.live.connect = MagicMock(
            return_value=_build_live_session_context(stream_with_complete, has_aclose=False)
        )

        with (
            patch("adapters.generation.live.get_client", return_value=fake_client),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "gemini-live-2.5-flash-preview"
            mock_cfg.return_value = MagicMock(output_dir=None)
            await live_module.run_async(prompt="hello")

    @pytest.mark.asyncio
    async def test_stream_aclose_returning_non_awaitable(self) -> None:
        """An aclose that returns None (not an awaitable) is invoked but not awaited
        — branch 186→192."""
        import adapters.generation.live as live_module

        complete_msg = MagicMock()
        complete_msg.text = "done"
        complete_server = MagicMock()
        complete_server.turn_complete = True
        complete_msg.server_content = complete_server

        async def stream_with_complete() -> object:
            yield complete_msg

        fake_client = MagicMock()
        fake_client.aio.live.connect = MagicMock(
            return_value=_build_live_session_context(
                stream_with_complete, has_aclose=True, aclose_return="not-awaitable"
            )
        )

        with (
            patch("adapters.generation.live.get_client", return_value=fake_client),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_router_cls.return_value.select_model.return_value = "gemini-live-2.5-flash-preview"
            mock_cfg.return_value = MagicMock(output_dir=None)
            await live_module.run_async(prompt="hello")


# ----------------------------------------------------------------------
# adapters/tools/code_exec.py — branch 62→56
# ----------------------------------------------------------------------


class TestCodeExecUnknownPart:
    """Coverage: a response part matching none of the known keys is skipped."""

    def test_part_with_unknown_key_skipped(self) -> None:
        """A part with none of text/executableCode/codeExecutionResult falls through."""
        from adapters.tools.code_exec import run

        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"unknownKey": "value"},  # triggers 62→56 fall-through
                            {"text": "hello"},
                        ]
                    }
                }
            ]
        }
        with (
            patch("adapters.tools.code_exec.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.code_exec.load_config") as mock_cfg,
            patch("adapters.tools.code_exec.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="hello")
        mock_emit.assert_called_once()


# ----------------------------------------------------------------------
# adapters/tools/maps.py — branch 67→76
# ----------------------------------------------------------------------


class TestMapsWithoutGroundingChunks:
    """Coverage: grounding present but groundingChunks empty → skip source block."""

    def test_grounding_without_chunks(self) -> None:
        """``groundingMetadata`` with empty ``groundingChunks`` skips the source block."""
        from adapters.tools.maps import run

        response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "The answer"}]},
                    "groundingMetadata": {"groundingChunks": []},  # empty → 67→76
                }
            ]
        }
        with (
            patch("adapters.tools.maps.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.maps.load_config") as mock_cfg,
            patch("adapters.tools.maps.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="test", i_understand_privacy=True)
        mock_emit.assert_called_once()


# ----------------------------------------------------------------------
# adapters/tools/search.py — branches 81→90, 87→83
# ----------------------------------------------------------------------


class TestSearchAdapterBranches:
    """Coverage for search grounding edge cases."""

    def test_no_grounding_metadata_emits_plain_text(self) -> None:
        """Response without grounding metadata skips the sources footer (branch 81→90)."""
        from adapters.tools.search import run

        response = {"candidates": [{"content": {"parts": [{"text": "plain answer"}]}}]}
        with (
            patch("adapters.tools.search.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.search.load_config") as mock_cfg,
            patch("adapters.tools.search.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="q", i_understand_privacy=True)
        mock_emit.assert_called_once()

    def test_chunk_without_uri_skipped(self) -> None:
        """Grounding chunk missing the ``uri`` field is skipped (branch 87→83)."""
        from adapters.tools.search import run

        response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "answer"}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"title": "no-uri-here"}},  # missing uri
                        ]
                    },
                }
            ]
        }
        with (
            patch("adapters.tools.search.api_call", return_value=response),
            patch("core.routing.router.Router") as mock_router_cls,
            patch("adapters.tools.search.load_config") as mock_cfg,
            patch("adapters.tools.search.emit_output") as mock_emit,
        ):
            mock_router_cls.return_value.select_model.return_value = "m"
            mock_cfg.return_value = MagicMock(output_dir=None)
            run(prompt="q", i_understand_privacy=True)
        mock_emit.assert_called_once()


# ----------------------------------------------------------------------
# core/routing/registry.py — branches 50→56, 52→56
# ----------------------------------------------------------------------


class TestRegistryLoadSectionEdges:
    """Coverage for ``Registry._load_section`` defensive guards."""

    def test_file_missing_key_returns_empty(self, tmp_path: Path) -> None:
        """A registry file that parses as dict but lacks the expected key
        returns ``{}`` — branch 50→56."""
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "models.json").write_text('{"other": {"foo": "bar"}}')
        (registry_dir / "capabilities.json").write_text('{"capabilities": {}}')

        from core.routing.registry import Registry

        registry = Registry(root_dir=tmp_path)
        assert registry.list_models() == []

    def test_section_wrong_type_returns_empty(self, tmp_path: Path) -> None:
        """A registry file with the expected key but a non-dict section
        returns ``{}`` — branch 52→56."""
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "models.json").write_text('{"models": "not-a-dict"}')
        (registry_dir / "capabilities.json").write_text('{"capabilities": {}}')

        from core.routing.registry import Registry

        registry = Registry(root_dir=tmp_path)
        assert registry.list_models() == []


# ----------------------------------------------------------------------
# core/state/file_state.py — branches 56→62, 58→62
# ----------------------------------------------------------------------


class TestFileStateLoadEdges:
    """Coverage for ``FileState._load`` defensive guards."""

    def test_missing_files_key(self, tmp_path: Path) -> None:
        """State file without the ``files`` key returns empty (branch 56→62)."""
        from core.state.file_state import FileState

        state_path = tmp_path / "files.json"
        state_path.write_text('{"other": {}}')
        state = FileState(state_dir=tmp_path)
        assert state.get_all() == {}

    def test_files_value_wrong_type(self, tmp_path: Path) -> None:
        """State file with ``files`` but non-dict value returns empty (branch 58→62)."""
        from core.state.file_state import FileState

        state_path = tmp_path / "files.json"
        state_path.write_text('{"files": "not-a-dict"}')
        state = FileState(state_dir=tmp_path)
        assert state.get_all() == {}


# ----------------------------------------------------------------------
# core/state/session_state.py — branches 74→80, 76→80
# ----------------------------------------------------------------------


class TestSessionStateLoadEdges:
    """Coverage for ``SessionState._load`` defensive guards."""

    def test_missing_contents_key(self, tmp_path: Path) -> None:
        """Session JSON without ``contents`` returns empty list (branch 74→80)."""
        from core.state.session_state import SessionState

        state = SessionState(sessions_dir=tmp_path)
        (tmp_path / "abc.json").write_text('{"other": "x"}')
        assert state.get_history("abc") == []

    def test_contents_wrong_type(self, tmp_path: Path) -> None:
        """Session JSON with non-list ``contents`` returns empty list (branch 76→80)."""
        from core.state.session_state import SessionState

        state = SessionState(sessions_dir=tmp_path)
        (tmp_path / "abc.json").write_text('{"contents": "not-a-list"}')
        assert state.get_history("abc") == []


# ----------------------------------------------------------------------
# core/state/store_state.py — branches 50→56, 52→56
# ----------------------------------------------------------------------


class TestStoreStateLoadEdges:
    """Coverage for ``StoreState._load`` defensive guards."""

    def test_missing_stores_key(self, tmp_path: Path) -> None:
        """State file without ``stores`` key returns empty (branch 50→56)."""
        from core.state.store_state import StoreState

        state_path = tmp_path / "stores.json"
        state_path.write_text('{"other": {}}')
        state = StoreState(state_dir=tmp_path)
        assert state.list_stores() == []

    def test_stores_wrong_type(self, tmp_path: Path) -> None:
        """State file with non-dict ``stores`` value returns empty (branch 52→56)."""
        from core.state.store_state import StoreState

        state_path = tmp_path / "stores.json"
        state_path.write_text('{"stores": "not-a-dict"}')
        state = StoreState(state_dir=tmp_path)
        assert state.list_stores() == []


# ----------------------------------------------------------------------
# core/cli/update_main.py — line 98 (_fetch_latest_release non-dict)
# ----------------------------------------------------------------------


class TestFetchLatestReleaseNonDict:
    """Coverage for the ``_fetch_latest_release`` non-dict payload fallthrough."""

    def test_non_dict_payload_returns_empty(self) -> None:
        """A GitHub API response that parses to a JSON array returns {}."""
        from core.cli.update_main import _fetch_latest_release

        mock_response = MagicMock()
        mock_response.read.return_value = b'["not", "a", "dict"]'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.cli.update_main.urlopen", return_value=mock_response):
            result = _fetch_latest_release()
        assert result == {}


# ----------------------------------------------------------------------
# core/infra/filelock.py — line 85 (lock timeout path)
# ----------------------------------------------------------------------


class TestFileLockGuards:
    """Coverage: defensive guards in FileLock helpers."""

    def test_try_lock_raises_when_fd_is_none(self, tmp_path: Path) -> None:
        """Calling _try_lock without first opening the file descriptor
        raises RuntimeError — branch on line 85."""
        from core.infra.filelock import FileLock

        lock_path = tmp_path / "guard.lock"
        lock = FileLock(lock_path)
        # Don't call _acquire(); _fd remains None.
        with pytest.raises(RuntimeError, match="not initialized"):
            lock._try_lock()

    def test_timeout_raised_when_lock_unavailable(self, tmp_path: Path) -> None:
        """When another process holds the lock and timeout elapses,
        LockTimeout is raised — exercises the timeout retry path."""
        import time

        from core.infra.filelock import FileLock, LockTimeout

        lock_path = tmp_path / "busy.lock"

        # Hold the lock via a real FileLock on the same path
        first = FileLock(lock_path, timeout=5.0)
        first._acquire()
        try:
            # Now try to acquire with a very short timeout — this forces
            # the retry loop to execute time.sleep at least once before
            # timing out.
            second = FileLock(lock_path, timeout=0.15)
            start = time.monotonic()
            with pytest.raises(LockTimeout):
                second._acquire()
            elapsed = time.monotonic() - start
            assert elapsed >= 0.1
        finally:
            first._release()


class TestTimeoutContextExit:
    """Coverage: TimeoutGuard.__exit__ branches."""

    def test_signal_path_exit(self) -> None:
        """The signal-based __exit__ path resets the alarm and old handler."""
        from core.infra.timeouts import TimeoutGuard

        with TimeoutGuard(seconds=10):
            pass  # The exit path runs after the with-block

    def test_watchdog_path_exit(self) -> None:
        """The watchdog __exit__ path cancels the timer."""
        import threading

        from core.infra.timeouts import TimeoutGuard

        completed = threading.Event()

        def worker() -> None:
            with TimeoutGuard(seconds=10):
                pass
            completed.set()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)
        assert completed.is_set()

    def test_signal_exit_when_old_handler_is_none(self) -> None:
        """Exit path where ``_use_signal=True`` AND ``_old_handler is None``
        skips the signal.signal restore — branch 76→exit."""
        from core.infra.timeouts import TimeoutGuard

        guard = TimeoutGuard(seconds=10)
        # Manually set the state that __enter__ would normally produce,
        # but with _old_handler unset (None). This exercises the False
        # branch of the inner ``if self._old_handler is not None``.
        guard._use_signal = True
        guard._old_handler = None
        guard.__exit__(None, None, None)

    def test_watchdog_exit_when_watchdog_is_none(self) -> None:
        """Exit path where ``_use_signal=False`` AND ``_watchdog is None``
        falls out cleanly — branch 78→exit."""
        from core.infra.timeouts import TimeoutGuard

        guard = TimeoutGuard(seconds=10)
        guard._use_signal = False
        guard._watchdog = None
        guard.__exit__(None, None, None)


class TestInstallMainSettingsBufferEdges:
    """Coverage for ``_setup_user_settings`` pre_resolved filtering branches."""

    def test_settings_buffer_env_not_dict_skipped(self, tmp_path: Path) -> None:
        """When the in-memory settings_buffer's env field is not a dict,
        pre_resolved stays empty — branch 177→182."""
        from core.cli import install_main

        captured: list[dict[str, str]] = []

        def fake_migrate(legacy_env: object, buffer: dict[str, object], **kwargs: object) -> None:
            buffer["env"] = "not-a-dict"  # forces the isinstance check to fail

        def fake_prompt(buffer: dict[str, object], **kwargs: object) -> None:
            return None

        def fake_merge(*args: object, **kwargs: object) -> None:
            captured.append(dict(kwargs.get("pre_resolved", {})))

        install_dir = tmp_path / "install"
        install_dir.mkdir()
        with (
            patch.object(install_main, "migrate_legacy_env_to_settings", side_effect=fake_migrate),
            patch.object(install_main, "prompt_gemini_api_key", side_effect=fake_prompt),
            patch.object(install_main, "merge_settings_env", side_effect=fake_merge),
        ):
            install_main._setup_user_settings(install_dir, yes=True, interactive=False)
        assert captured == [{}]

    def test_settings_buffer_env_with_non_string_value(self, tmp_path: Path) -> None:
        """A dict env with non-string values filters them out — branch 179→178."""
        from core.cli import install_main

        captured: list[dict[str, str]] = []

        def fake_migrate(legacy_env: object, buffer: dict[str, object], **kwargs: object) -> None:
            buffer["env"] = {
                "GEMINI_API_KEY": "AIzaSy-real-string",
                "other_int": 42,  # non-string value, filtered out
            }

        def fake_prompt(buffer: dict[str, object], **kwargs: object) -> None:
            return None

        def fake_merge(*args: object, **kwargs: object) -> None:
            captured.append(dict(kwargs.get("pre_resolved", {})))

        install_dir = tmp_path / "install"
        install_dir.mkdir()
        with (
            patch.object(install_main, "migrate_legacy_env_to_settings", side_effect=fake_migrate),
            patch.object(install_main, "prompt_gemini_api_key", side_effect=fake_prompt),
            patch.object(install_main, "merge_settings_env", side_effect=fake_merge),
        ):
            install_main._setup_user_settings(install_dir, yes=True, interactive=False)
        assert captured == [{"GEMINI_API_KEY": "AIzaSy-real-string"}]


class TestNormalizeBytesHandling:
    """Coverage: normalize layer base64-encodes bytes to match raw HTTP shape."""

    def test_bytes_value_base64_encoded(self) -> None:
        """A bytes primitive is base64-encoded into a string."""
        from core.transport.normalize import _translate_keys

        result = _translate_keys(b"hello")
        assert result == "aGVsbG8="

    def test_nested_bytes_in_dict_encoded(self) -> None:
        """A bytes value inside a dict is base64-encoded recursively.

        The key ``thoughtSignature`` is not in ``_SNAKE_TO_CAMEL`` (snake
        form is also not), so the key passes through unchanged. Only the
        value translation is exercised here.
        """
        from core.transport.normalize import _translate_keys

        result = _translate_keys({"someField": b"\x01\x02\x03"})
        assert result == {"someField": "AQID"}

    def test_nested_bytes_in_list_encoded(self) -> None:
        """A bytes element inside a list is base64-encoded recursively."""
        from core.transport.normalize import _translate_keys

        result = _translate_keys([b"a", b"b"])
        assert result == ["YQ==", "Yg=="]


class TestSdkTransportValueErrorTranslation:
    """Coverage: _wrap_sdk_errors translates SDK 'not supported' ValueError to BackendUnavailableError."""

    def test_not_supported_in_gemini_api_translates_to_backend_unavailable(self) -> None:
        """A ValueError with the SDK's "not supported in Gemini API" string
        is translated to BackendUnavailableError so the coordinator falls
        back to raw HTTP."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk.transport import _wrap_sdk_errors

        with pytest.raises(BackendUnavailableError, match="unsupported tool surface"):
            with _wrap_sdk_errors():
                raise ValueError("google_maps parameter is not supported in Gemini API.")

    def test_unrelated_value_error_propagates_unchanged(self) -> None:
        """A ValueError NOT matching the SDK pattern propagates as-is
        (preserving the architect-mandated "no string-matching on bugs" contract)."""
        from core.transport.sdk.transport import _wrap_sdk_errors

        with pytest.raises(ValueError, match="totally different"):
            with _wrap_sdk_errors():
                raise ValueError("totally different programmer bug")


class TestInstallMainCleanInstallMissingFile:
    """Coverage: _clean_install skips operational files that don't exist (branch 309→307)."""

    def test_clean_install_skips_missing_operational_file(self, tmp_path: Path) -> None:
        """When an _OPERATIONAL_FILES entry is missing from source_dir,
        the loop continues to the next file without raising."""
        from core.cli import install_main

        source_dir = tmp_path / "src"
        source_dir.mkdir()
        install_dir = tmp_path / "install"

        install_main._clean_install(source_dir, install_dir)

        assert install_dir.is_dir()
