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
        with pytest.raises(SystemExit):
            main(["nonexistent"])
        err = capsys.readouterr().out + capsys.readouterr().err
        # Should exit with error

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


class TestDispatchAllAdapters:
    """Verify every capability has a dispatch entry."""

    @pytest.mark.parametrize("command,adapter_path", [
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
    ])
    def test_command_registered(self, command, adapter_path):
        from core.cli.dispatch import ALLOWED_COMMANDS
        assert command in ALLOWED_COMMANDS
