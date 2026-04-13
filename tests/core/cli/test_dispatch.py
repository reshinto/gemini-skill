"""Tests for core/cli/dispatch.py — CLI dispatcher + policy enforcement."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestDispatchMain:
    def test_empty_argv_shows_help(self, capsys):
        from core.cli.dispatch import main

        main([])
        output = capsys.readouterr().out
        assert "Usage" in output or "commands" in output.lower()

    def test_unknown_command_fails_closed(self, capsys):
        from core.cli.dispatch import main

        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent"])
        assert exc_info.value.code == 1
        assert "Unknown command" in capsys.readouterr().out

    def test_text_command_routes_to_text_adapter(self):
        from core.cli.dispatch import main

        with patch("adapters.generation.text.run") as mock_run:
            main(["text", "hello"])
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["prompt"] == "hello"

    def test_embed_command_routes_to_embeddings(self):
        from core.cli.dispatch import main

        with patch("adapters.data.embeddings.run") as mock_run:
            main(["embed", "hello text"])
        mock_run.assert_called_once()

    def test_image_gen_command_routes(self):
        from core.cli.dispatch import main

        with patch("adapters.media.image_gen.run") as mock_run:
            main(["image_gen", "a cat", "--execute"])
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["execute"] is True

    def test_help_command_shows_commands(self, capsys):
        from core.cli.dispatch import main

        main(["help"])
        output = capsys.readouterr().out
        assert "text" in output
        assert "embed" in output

    def test_models_command_lists_registry(self, capsys):
        from core.cli.dispatch import main

        main(["models"])
        output = capsys.readouterr().out
        assert "gemini-2.5-flash" in output


class TestDispatchPolicyEnforcement:
    """Dispatch must enforce mutating and privacy-sensitive rules from registry."""

    def test_mutating_command_blocked_without_execute(self, capsys):
        from core.cli.dispatch import main

        with patch("adapters.media.image_gen.run") as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main(["image_gen", "a cat"])
        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert "[DRY RUN]" in output
        assert "image_gen" in output
        mock_run.assert_not_called()

    def test_mutating_command_allowed_with_execute(self):
        from core.cli.dispatch import main

        with patch("adapters.media.image_gen.run") as mock_run:
            main(["image_gen", "a cat", "--execute"])
        mock_run.assert_called_once()

    @pytest.mark.parametrize(
        ("command", "adapter_path", "argv"),
        [
            ("search", "adapters.tools.search.run", ["search", "weather today"]),
            ("maps", "adapters.tools.maps.run", ["maps", "coffee shops near me"]),
            ("computer_use", "adapters.experimental.computer_use.run", ["computer_use", "describe screen"]),
        ],
    )
    def test_privacy_sensitive_main_auto_injects_opt_in(self, command, adapter_path, argv):
        from core.cli.dispatch import main

        with patch(adapter_path) as mock_run:
            main(argv)
        mock_run.assert_called_once()

    def test_privacy_sensitive_allowed_with_opt_in(self):
        from core.cli.dispatch import main

        with patch("adapters.tools.search.run") as mock_run:
            main(["search", "weather today", "--i-understand-privacy"])
        mock_run.assert_called_once()

    def test_raw_policy_still_blocks_without_privacy_opt_in(self, capsys):
        from core.cli.dispatch import _enforce_policy

        with pytest.raises(SystemExit) as exc_info:
            _enforce_policy("search", ["weather today"])
        assert exc_info.value.code == 1
        output = capsys.readouterr().out
        assert "[BLOCKED]" in output
        assert "privacy-sensitive" in output

    def test_mutating_privacy_sensitive_without_execute_dry_runs(self, capsys):
        from core.cli.dispatch import main

        with patch("adapters.experimental.deep_research.run") as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main(["deep_research", "research topic"])
        assert exc_info.value.code == 0
        assert "[DRY RUN]" in capsys.readouterr().out
        mock_run.assert_not_called()

    @pytest.mark.parametrize(
        ("argv", "adapter_path"),
        [
            (["files", "list"], "adapters.data.files.run"),
            (["cache", "list"], "adapters.data.cache.run"),
            (["batch", "list"], "adapters.data.batch.run"),
            (["file_search", "query", "find doc", "--store", "stores/x"], "adapters.data.file_search.run"),
            (["file_search", "list"], "adapters.data.file_search.run"),
        ],
    )
    def test_read_only_operations_run_without_execute(self, argv, adapter_path):
        from core.cli.dispatch import main

        with patch(adapter_path) as mock_run:
            main(argv)
        mock_run.assert_called_once()

    @pytest.mark.parametrize(
        "argv",
        [
            ["files", "list", "--execute"],
            ["cache", "list", "--execute"],
            ["batch", "list", "--execute"],
            ["file_search", "query", "find doc", "--store", "stores/x", "--execute"],
        ],
    )
    def test_read_only_operations_reject_execute(self, argv):
        from core.cli.dispatch import main

        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 2

    @pytest.mark.parametrize(
        "argv",
        [
            ["files", "delete", "files/x"],
            ["cache", "delete", "cachedContents/x"],
            ["batch", "cancel", "batchJobs/x"],
            ["file_search", "delete", "fileSearchStores/x"],
        ],
    )
    def test_mutating_subcommands_still_dry_run_without_execute(self, argv, capsys):
        from core.cli.dispatch import main

        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_non_policy_command_runs_freely(self):
        from core.cli.dispatch import main

        with patch("adapters.generation.text.run") as mock_run:
            main(["text", "hello"])
        mock_run.assert_called_once()


class TestDispatchProtocolValidation:
    """Dispatch must validate AdapterProtocol conformance."""

    def test_malformed_adapter_rejected(self, capsys):
        from core.cli import dispatch

        # Inject a fake command that maps to a broken module
        original = dispatch.ALLOWED_COMMANDS.copy()
        try:
            dispatch.ALLOWED_COMMANDS["broken"] = "os"  # os has no get_parser/run
            with pytest.raises(SystemExit) as exc_info:
                dispatch.main(["broken"])
            assert exc_info.value.code == 1
            output = capsys.readouterr().out
            assert "AdapterProtocol" in output
        finally:
            dispatch.ALLOWED_COMMANDS.clear()
            dispatch.ALLOWED_COMMANDS.update(original)


class TestDispatchPolicyUnknownCapability:
    """Dispatch must not crash when command is not in the capability registry."""

    def test_unknown_capability_passes_through(self):
        from core.cli import dispatch
        from core.infra.errors import CapabilityUnavailableError

        # Mock Registry.get_capability to raise CapabilityUnavailableError
        with (
            patch(
                "core.routing.registry.Registry.get_capability",
                side_effect=CapabilityUnavailableError("not found"),
            ),
            patch("adapters.generation.text.run") as mock_run,
        ):
            dispatch.main(["text", "hello"])
        mock_run.assert_called_once()


class TestDispatchAllAdapters:
    """Verify every capability has a dispatch entry."""

    @pytest.mark.parametrize(
        "command,adapter_path",
        [
            ("text", "adapters.generation.text"),
            ("multimodal", "adapters.generation.multimodal"),
            ("structured", "adapters.generation.structured"),
            ("streaming", "adapters.generation.streaming"),
            ("embed", "adapters.data.embeddings"),
            ("token_count", "adapters.data.token_count"),
            ("function_calling", "adapters.tools.function_calling"),
            ("code_exec", "adapters.tools.code_exec"),
            ("files", "adapters.data.files"),
            ("cache", "adapters.data.cache"),
            ("batch", "adapters.data.batch"),
            ("search", "adapters.tools.search"),
            ("maps", "adapters.tools.maps"),
            ("file_search", "adapters.data.file_search"),
            ("image_gen", "adapters.media.image_gen"),
            ("video_gen", "adapters.media.video_gen"),
            ("music_gen", "adapters.media.music_gen"),
            ("computer_use", "adapters.experimental.computer_use"),
            ("deep_research", "adapters.experimental.deep_research"),
        ],
    )
    def test_command_registered(self, command, adapter_path):
        from core.cli.dispatch import ALLOWED_COMMANDS

        assert command in ALLOWED_COMMANDS


class TestDispatchAsyncAdapter:
    """Phase 6: adapters that declare ``IS_ASYNC = True`` must be run via
    ``asyncio.run(adapter.run_async(**kwargs))`` instead of the sync
    ``adapter.run(**kwargs)`` path. The existing 19 sync adapters are
    unaffected — dispatch only switches paths when the adapter module
    carries the opt-in marker.
    """

    def test_is_async_adapter_uses_run_async_via_asyncio_run(self) -> None:
        """An adapter module with ``IS_ASYNC = True`` + an ``async def run_async``
        must be dispatched through ``asyncio.run`` rather than the sync
        ``run`` path."""
        from core.cli.dispatch import main

        async_calls: list[dict[str, object]] = []

        async def _fake_run_async(**kwargs: object) -> None:
            async_calls.append(kwargs)

        sync_run = MagicMock(side_effect=AssertionError("sync run used"))

        fake_adapter = MagicMock()
        fake_adapter.IS_ASYNC = True
        fake_adapter.run = sync_run
        fake_adapter.run_async = _fake_run_async
        from types import SimpleNamespace

        parser = MagicMock()
        parser.parse_args.return_value = SimpleNamespace(prompt="hello", model=None)
        fake_adapter.get_parser.return_value = parser

        from core.cli.dispatch import ALLOWED_COMMANDS

        ALLOWED_COMMANDS["live"] = "adapters.generation.live"
        try:
            with patch("importlib.import_module", return_value=fake_adapter):
                main(["live", "hello"])
        finally:
            ALLOWED_COMMANDS.pop("live", None)

        assert len(async_calls) == 1
        assert async_calls[0]["prompt"] == "hello"
        fake_adapter.run.assert_not_called()

    def test_sync_adapter_uses_sync_run(self):
        """Adapters without ``IS_ASYNC`` (or with ``IS_ASYNC = False``)
        still take the sync path — regression guard for the 19 existing
        sync adapters."""
        from core.cli.dispatch import main

        with patch("adapters.generation.text.run") as mock_run:
            # adapters.generation.text has no IS_ASYNC attribute — sync path
            main(["text", "hello"])
        mock_run.assert_called_once()
