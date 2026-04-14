"""Shared adapter lifecycle helpers.

Provides common functionality used by all adapters:
    - build_base_parser(): ArgumentParser with shared flags (--model, --session)
    - add_execute_flag(): Opt-in mutating-operation flag
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
from collections.abc import Mapping
from pathlib import Path

from core.infra.sanitize import safe_print
from core.transport.base import GeminiResponse, Part

# Responses exceeding this size are saved to file instead of stdout
_LARGE_RESPONSE_THRESHOLD = 50_000  # characters


def build_base_parser(description: str) -> argparse.ArgumentParser:
    """Create an ArgumentParser with flags common to all adapters.

    Common flags:
        --model: Override the default model selection.
        --session: Start or continue a named conversation session.
        --continue: Continue the most recent session.

    Args:
        description: Help text describing this adapter.

    Returns:
        An ArgumentParser with common flags added.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.set_defaults(execute=False)
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model for this command.",
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


def add_execute_flag(parser: argparse.ArgumentParser) -> None:
    """Add the ``--execute`` confirmation flag to a mutating parser."""
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute the operation (mutating operations only).",
    )


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

    fd, path = tempfile.mkstemp(prefix="gemini-skill-", suffix=".txt", dir=str(directory))
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)

    abs_path = str(Path(path).resolve())
    safe_print(
        f"Response saved to {abs_path} "
        f"({len(text)} chars, exceeds {_LARGE_RESPONSE_THRESHOLD} char stdout limit)"
    )


def emit_json(data: Mapping[str, object] | object) -> None:
    """Output structured JSON data to stdout.

    Used by media adapters (image_gen, video_gen, music_gen) to return
    file paths and metadata in a machine-readable format.

    Args:
        data: Dictionary to serialize as JSON.
    """
    safe_print(json.dumps(data, indent=2))


def extract_text(response: GeminiResponse) -> str:
    """Extract text from a Gemini generateContent response.

    Handles safety blocks and missing candidates gracefully by raising
    a clear ValueError instead of an unhelpful KeyError/IndexError.

    Args:
        response: The parsed JSON response from generateContent.

    Returns:
        The text content of the first candidate's first text part.

    Raises:
        ValueError: If the response has no candidates (safety block, quota, etc.).
    """
    candidates = response.get("candidates")
    if not candidates:
        feedback = response.get("promptFeedback", {})
        reason = feedback.get("blockReason", "unknown")
        raise ValueError(
            f"Gemini API returned no candidates (blockReason={reason}). "
            "This may be a safety filter, quota, or content policy block."
        )
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if "text" in part:
            return part["text"]
    return ""


def extract_parts(response: GeminiResponse) -> list[Part]:
    """Extract content parts from a Gemini response.

    Returns the full parts list (text, inlineData, functionCall, etc.)
    so adapters can handle multi-modal or tool responses.

    Args:
        response: The parsed JSON response from generateContent.

    Returns:
        List of content parts. Empty list if no candidates.

    Raises:
        ValueError: If the response has no candidates.
    """
    candidates = response.get("candidates")
    if not candidates:
        feedback = response.get("promptFeedback", {})
        reason = feedback.get("blockReason", "unknown")
        raise ValueError(f"Gemini API returned no candidates (blockReason={reason}).")
    return candidates[0].get("content", {}).get("parts", [])


def create_media_output_file(suffix: str, output_dir: str | None = None) -> str:
    """Create a unique output file path for media generation adapters.

    Uses secure tempfile.mkstemp to avoid race conditions, then closes
    the fd (callers write to the path, not the fd).

    Args:
        suffix: File extension including leading dot (e.g., ".png").
        output_dir: Target directory, or None for OS temp dir.

    Returns:
        Absolute path to a new empty file.
    """
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="gemini-skill-", suffix=suffix, dir=str(directory))
    os.close(fd)
    return str(Path(path).resolve())


def mime_to_ext(mime_type: str, mapping: dict[str, str], default: str) -> str:
    """Convert a MIME type to a file extension using a caller-provided table.

    Args:
        mime_type: The MIME type string (e.g., "image/png").
        mapping: Dict mapping MIME types to extensions (with leading dot).
        default: Fallback extension if mime_type is not in mapping.

    Returns:
        File extension with leading dot.
    """
    return mapping.get(mime_type, default)
