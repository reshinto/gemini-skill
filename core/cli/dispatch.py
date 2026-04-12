"""CLI dispatcher + policy enforcement.

The policy boundary for the skill CLI. Validates subcommands against
a whitelist, parses arguments via each adapter's parser, and calls
the adapter's run() function.

REPO-WIDE INVARIANT: Never os.system(), never shell=True, never
concatenate user text into shell commands.

Dependencies: all adapter modules, core/routing/registry.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from core.infra.sanitize import safe_print

# Whitelist of allowed commands → adapter module path
ALLOWED_COMMANDS: dict[str, str] = {
    # Generation
    "text": "adapters.generation.text",
    "multimodal": "adapters.generation.multimodal",
    "structured": "adapters.generation.structured",
    "streaming": "adapters.generation.streaming",
    # Data
    "embed": "adapters.data.embeddings",
    "token_count": "adapters.data.token_count",
    "files": "adapters.data.files",
    "cache": "adapters.data.cache",
    "batch": "adapters.data.batch",
    "file_search": "adapters.data.file_search",
    # Tools
    "function_calling": "adapters.tools.function_calling",
    "code_exec": "adapters.tools.code_exec",
    "search": "adapters.tools.search",
    "maps": "adapters.tools.maps",
    # Media (preview)
    "image_gen": "adapters.media.image_gen",
    "video_gen": "adapters.media.video_gen",
    "music_gen": "adapters.media.music_gen",
    # Experimental
    "computer_use": "adapters.experimental.computer_use",
    "deep_research": "adapters.experimental.deep_research",
}


def main(argv: list[str]) -> None:
    """Dispatch a CLI command to the appropriate adapter.

    Args:
        argv: Command-line arguments (without the script name).
    """
    if not argv:
        _print_help()
        return

    command = argv[0]
    remaining = argv[1:]

    if command in ("help", "--help", "-h"):
        _print_help()
        return

    if command == "models":
        _list_models()
        return

    if command not in ALLOWED_COMMANDS:
        safe_print(f"[ERROR] Unknown command: {command}")
        safe_print("Run 'help' to see available commands.")
        sys.exit(1)

    # Import the adapter module and invoke it
    adapter_module = importlib.import_module(ALLOWED_COMMANDS[command])
    parser = adapter_module.get_parser()
    args = parser.parse_args(remaining)
    adapter_module.run(**vars(args))


def _print_help() -> None:
    """Print usage and command list."""
    safe_print("Usage: gemini <command> [args]")
    safe_print("")
    safe_print("Available commands:")
    for cmd in sorted(ALLOWED_COMMANDS.keys()):
        safe_print(f"  {cmd}")
    safe_print("  help      - Show this help message")
    safe_print("  models    - List available models from registry")
    safe_print("")
    safe_print("Run '<command> --help' for command-specific usage.")


def _list_models() -> None:
    """List all models from the registry."""
    from core.routing.registry import Registry
    root = Path(__file__).parent.parent.parent
    reg = Registry(root_dir=root)
    for model_id in sorted(reg.list_models()):
        model = reg.get_model(model_id)
        status = model.get("status", "unknown")
        safe_print(f"  {model_id}  [{status}]")
