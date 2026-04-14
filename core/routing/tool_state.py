"""Shared tool state preservation for multi-turn tool loops.

Preserves provider-returned content parts (id, tool_type, thought_signature,
and any additional fields) exactly as received. The implementation treats
these as opaque blobs — round-tripping the full JSON without assuming a
fixed field list.

Used by function_calling, code_exec, and future tool-using adapters
to maintain state across multi-turn API calls.

Dependency: none (leaf module).
"""

from __future__ import annotations

import copy

from core.transport.base import Content, Part

# Fields that indicate a part carries tool state
_TOOL_STATE_KEYS = frozenset(
    {
        "functionCall",
        "functionResponse",
        "executableCode",
        "codeExecutionResult",
    }
)


def has_tool_state(part: Part) -> bool:
    """Check if a content part carries tool state.

    A part has tool state if it contains any of the known tool-related
    keys (functionCall, functionResponse, executableCode, codeExecutionResult).

    Args:
        part: A single content part from a Gemini API response.

    Returns:
        True if the part contains tool state.
    """
    return bool(_TOOL_STATE_KEYS & part.keys())


def extract_tool_state(parts: list[Part]) -> list[Part]:
    """Extract tool-state parts from a list of content parts.

    Preserves the entire part exactly as returned by the API,
    including id, tool_type, thought_signature, and any unknown
    fields added in future API versions.

    Args:
        parts: List of content parts from a Gemini API response.

    Returns:
        List of parts that contain tool state, preserved exactly.
    """
    return [part for part in parts if has_tool_state(part)]


def inject_tool_state(
    contents: list[Content],
    preserved_parts: list[Part],
) -> list[Content]:
    """Merge preserved tool state parts into the request contents.

    Appends the preserved parts to the last model turn. If no model
    turn exists, creates one. Does not modify the original contents.

    Args:
        contents: The current conversation contents array.
        preserved_parts: Tool state parts to inject.

    Returns:
        A new contents array with preserved parts merged in.
    """
    if not preserved_parts:
        return contents

    result = copy.deepcopy(contents)

    # Find or create the last model turn
    model_turn: Content | None = None
    for entry in reversed(result):
        if entry.get("role") == "model":
            model_turn = entry
            break

    if model_turn is None:
        model_turn = {"role": "model", "parts": []}
        result.append(model_turn)

    model_turn["parts"].extend(preserved_parts)
    return result
