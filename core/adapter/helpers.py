"""Shared adapter lifecycle helpers.

Provides common functionality used by all adapters:
    - build_base_parser(): ArgumentParser with shared flags (--model, --execute, --session)
    - check_dry_run(): Enforce dry-run policy for mutating operations
    - emit_output(): Print text or save large responses to file
    - emit_json(): Output structured JSON for media adapters

The large response guard (50KB threshold) prevents Claude Code token
overflow by saving large responses to a file and returning only the path.

Dependencies: core/infra/sanitize.py (safe_print)
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from core.infra.sanitize import safe_print

# Responses exceeding this size are saved to file instead of stdout
_LARGE_RESPONSE_THRESHOLD = 50_000  # characters


def build_base_parser(description: str) -> argparse.ArgumentParser:
    """Create an ArgumentParser with flags common to all adapters.

    Common flags:
        --model: Override the default model selection.
        --execute: Required for mutating operations (dry-run default).
        --session: Start or continue a named conversation session.
        --continue: Continue the most recent session.

    Args:
        description: Help text describing this adapter.

    Returns:
        An ArgumentParser with common flags added.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model for this command.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute the operation (required for mutating commands).",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Start or continue a named conversation session.",
    )
    parser.add_argument(
        "--continue",
        dest="continue_session",
        action="store_true",
        default=False,
        help="Continue the most recent conversation session.",
    )
    return parser


def check_dry_run(execute: bool, operation: str) -> bool:
    """Check if the operation should be skipped due to dry-run mode.

    Prints a dry-run message and returns True if execute is False.

    Args:
        execute: Whether the --execute flag was provided.
        operation: Description of the operation for the dry-run message.

    Returns:
        True if the operation should be skipped (dry-run), False to proceed.
    """
    if not execute:
        safe_print(f"[DRY RUN] Would {operation}. Pass --execute to run.")
        return True
    return False


def emit_output(
    text: str,
    output_dir: str | None = None,
) -> None:
    """Print text output, or save to file if it exceeds the size threshold.

    Large responses (>50KB) are saved to a unique file to prevent
    Claude Code token overflow. The file path and size are printed instead.

    Args:
        text: The text content to output.
        output_dir: Directory for large response files. None = OS temp dir.
    """
    if len(text) <= _LARGE_RESPONSE_THRESHOLD:
        safe_print(text)
        return

    # Save large response to file
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)

    fd, path = tempfile.mkstemp(
        prefix="gemini-skill-", suffix=".txt", dir=str(directory)
    )
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)

    abs_path = str(Path(path).resolve())
    safe_print(
        f"Response saved to {abs_path} "
        f"({len(text)} chars, exceeds {_LARGE_RESPONSE_THRESHOLD} char stdout limit)"
    )


def emit_json(data: dict[str, Any]) -> None:
    """Output structured JSON data to stdout.

    Used by media adapters (image_gen, video_gen, music_gen) to return
    file paths and metadata in a machine-readable format.

    Args:
        data: Dictionary to serialize as JSON.
    """
    safe_print(json.dumps(data, indent=2))
