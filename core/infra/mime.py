"""MIME type detection helper with Python 3.13+ compatibility.

Provides a single function guess_mime_for_path() that handles the
version-gated difference between Python 3.13+ (mimetypes.guess_file_type)
and Python 3.9-3.12 (mimetypes.guess_type). Neither inspects file contents
— both are filename/extension-based only.

Users can override MIME detection via the --mime CLI flag.

Dependency: none (leaf module, stdlib only).
"""

from __future__ import annotations

import mimetypes
import sys
from pathlib import Path
from typing import Union

# Default fallback when MIME type cannot be determined
_FALLBACK_MIME = "application/octet-stream"


def guess_mime_for_path(path: Union[str, Path]) -> str:
    """Guess the MIME type for a file based on its name/extension.

    Uses mimetypes.guess_file_type() on Python 3.13+ and
    mimetypes.guess_type() on earlier versions. Neither function
    inspects file contents — this is purely extension-based.

    Args:
        path: File path (string or Path object).

    Returns:
        The guessed MIME type string, or "application/octet-stream"
        if the type cannot be determined.
    """
    path = Path(path)

    if sys.version_info >= (3, 13) and hasattr(mimetypes, "guess_file_type"):
        mime_type, _ = mimetypes.guess_file_type(path)
    else:
        mime_type, _ = mimetypes.guess_type(str(path))

    return mime_type or _FALLBACK_MIME
