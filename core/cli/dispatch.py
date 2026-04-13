"""CLI dispatcher + policy enforcement.

The policy boundary for the skill CLI. Validates subcommands against
a whitelist, enforces mutating and privacy-sensitive rules from the
registry, checks AdapterProtocol conformance, parses arguments via
each adapter's parser, and calls the adapter's run() function.

REPO-WIDE INVARIANT: Never os.system(), never shell=True, never
concatenate user text into shell commands.

Dependencies: all adapter modules, core/routing/registry.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from core.infra.errors import CapabilityUnavailableError
from core.infra.sanitize import safe_print

# Whitelist of allowed commands → adapter module path
ALLOWED_COMMANDS: dict[str, str] = {
    # Generation
    "text": "adapters.generation.text",
    "multimodal": "adapters.generation.multimodal",
    "structured": "adapters.generation.structured",
    "streaming": "adapters.generation.streaming",
    "imagen": "adapters.generation.imagen",
    "live": "adapters.generation.live",
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

# Environment/argument flag for opting into privacy-sensitive operations
_PRIVACY_OPT_IN_FLAG = "--i-understand-privacy"
_FLAGS_WITH_VALUES = {"--model", "--session"}
_BOOLEAN_FLAGS = {"--continue", "--execute", _PRIVACY_OPT_IN_FLAG}


def main(argv: list[str]) -> None:
    """Dispatch a CLI command to the appropriate adapter.

    Enforces policy rules (mutating, privacy-sensitive) at the boundary
    before delegating to the adapter. This ensures the registry's metadata
    is the single source of truth for command safety gates.

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

    # Normalize privacy opt-in before policy enforcement so normal CLI
    # callers do not need to pass the dispatcher-only flag manually.
    normalized_args = _inject_privacy_opt_in_if_needed(command, remaining)

    # Enforce registry-driven policy before invoking the adapter
    _enforce_policy(command, normalized_args)

    # Strip policy-only flags before handing off to the adapter
    adapter_args = [a for a in normalized_args if a != _PRIVACY_OPT_IN_FLAG]

    # Import and validate adapter
    adapter_module = importlib.import_module(ALLOWED_COMMANDS[command])
    _validate_adapter_protocol(command, adapter_module)

    parser = adapter_module.get_parser()
    args = parser.parse_args(adapter_args)

    # Phase 6: adapters may opt in to async dispatch by declaring
    # ``IS_ASYNC = True`` at module level and implementing ``async def
    # run_async(**kwargs)`` instead of (or alongside) the sync ``run``.
    # Async adapters are used for the Live API and any future ``--parallel``
    # feature. The 19 existing sync adapters don't carry this attribute,
    # so the default ``getattr(..., False)`` preserves the sync path.
    if getattr(adapter_module, "IS_ASYNC", False):
        import asyncio

        asyncio.run(adapter_module.run_async(**vars(args)))
        return

    adapter_module.run(**vars(args))


def _inject_privacy_opt_in_if_needed(command: str, args: list[str]) -> list[str]:
    """Append the privacy opt-in flag for privacy-sensitive commands."""
    from core.routing.registry import Registry

    try:
        reg = Registry(root_dir=_get_repo_root())
        cap = reg.get_capability(command)
    except CapabilityUnavailableError:
        return args

    if cap.get("privacy_sensitive") and _PRIVACY_OPT_IN_FLAG not in args:
        return args + [_PRIVACY_OPT_IN_FLAG]
    return args


def _enforce_policy(command: str, args: list[str]) -> None:
    """Apply registry-driven policy rules to a command.

    Blocks privacy-sensitive commands without explicit opt-in.
    Blocks mutating commands without --execute (dry-run default).

    Args:
        command: The command name.
        args: Remaining arguments (checked for --execute).
    """
    from core.routing.registry import Registry

    try:
        reg = Registry(root_dir=_get_repo_root())
        cap = reg.get_capability(command)
    except CapabilityUnavailableError:
        # Command not in registry — allow (e.g., future commands)
        return

    if cap.get("privacy_sensitive") and _PRIVACY_OPT_IN_FLAG not in args:
        safe_print(
            f"[BLOCKED] '{command}' is privacy-sensitive and sends data to "
            "external services (search results, maps, computer interaction, "
            "or long-term research storage).\n"
            f"Pass {_PRIVACY_OPT_IN_FLAG} to proceed."
        )
        sys.exit(1)

    if _is_mutating_invocation(cap, args) and "--execute" not in args:
        safe_print(
            f"[DRY RUN] '{command}' is a mutating operation. " "Pass --execute to actually run it."
        )
        sys.exit(0)


def _extract_action_token(args: list[str]) -> str | None:
    """Return the subcommand/action token from raw CLI args, if any."""
    i = 0
    while i < len(args):
        token = args[i]
        if token in _FLAGS_WITH_VALUES:
            i += 2
            continue
        if token in _BOOLEAN_FLAGS:
            i += 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None


def _is_mutating_invocation(cap: dict[str, object], args: list[str]) -> bool:
    """Resolve whether this specific invocation is mutating."""
    action = _extract_action_token(args)
    mutating_actions = cap.get("mutating_actions")
    if isinstance(mutating_actions, list):
        return action in mutating_actions
    return bool(cap.get("mutating", False))


def _validate_adapter_protocol(command: str, adapter_module: ModuleType) -> None:
    """Verify an adapter module implements AdapterProtocol.

    Checks for the presence of get_parser and run attributes. Exits
    with a clear error if the contract is violated.
    """
    if not (hasattr(adapter_module, "get_parser") and hasattr(adapter_module, "run")):
        safe_print(
            f"[ERROR] Adapter '{command}' does not implement AdapterProtocol. "
            "Missing get_parser() or run()."
        )
        sys.exit(1)


def _get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent.parent


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
    safe_print("")
    safe_print("Policy:")
    safe_print("  - Mutating commands require --execute (dry-run default)")
    safe_print("  - Privacy-sensitive commands are opt-in internally at dispatch")


def _list_models() -> None:
    """List all models from the registry."""
    from core.routing.registry import Registry

    reg = Registry(root_dir=_get_repo_root())
    for model_id in sorted(reg.list_models()):
        model = reg.get_model(model_id)
        status = model.get("status", "unknown")
        safe_print(f"  {model_id}  [{status}]")
