"""Shared type aliases and small TypedDicts used across the repository."""

from __future__ import annotations

import sys
from typing import TypedDict

# ``typing.TypeAlias`` is Python 3.10+. Fall back to ``typing_extensions``
# on 3.9 so the supported-floor (Python 3.9+) still works. ``TypedDict`` is
# available from the stdlib on both versions so it imports directly above.
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:  # pragma: no cover - 3.9-only branch, not exercised on 3.10+ CI
    from typing_extensions import TypeAlias

JSONValue: TypeAlias = object
JSONObject: TypeAlias = dict[str, JSONValue]


class SettingsBuffer(TypedDict, total=False):
    """Subset of ``~/.claude/settings.json`` this repository mutates."""

    env: dict[str, str]
