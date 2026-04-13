"""Shared type aliases and small TypedDicts used across the repository."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

JSONValue: TypeAlias = object
JSONObject: TypeAlias = dict[str, JSONValue]


class SettingsBuffer(TypedDict, total=False):
    """Subset of ``~/.claude/settings.json`` this repository mutates."""

    env: dict[str, str]
