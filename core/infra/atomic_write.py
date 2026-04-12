"""Atomic file write utility using tempfile + os.replace.

Provides a single shared implementation of the atomic write pattern
used throughout the project. Prevents data corruption from crashes
or concurrent access by writing to a temp file first, then atomically
replacing the target.

Dependency: none (leaf module, stdlib only).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_json(
    path: Path,
    data: str,
    dir_mode: int = 0o700,
    file_mode: int = 0o600,
) -> None:
    """Atomically write string data to a file with secure permissions.

    Creates the parent directory if needed (with dir_mode permissions).
    Writes to a temp file in the same directory, sets file_mode, then
    atomically replaces the target via os.replace().

    Args:
        path: Target file path.
        data: String content to write.
        dir_mode: Permission mode for the parent directory (default 0o700).
        file_mode: Permission mode for the file (default 0o600).
    """
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(str(parent), dir_mode)
    except OSError:
        pass

    fd, tmp_path = tempfile.mkstemp(
        dir=str(parent), prefix=".atomic-", suffix=".tmp"
    )
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        fd = -1

        try:
            os.chmod(tmp_path, file_mode)
        except OSError:
            pass

        os.replace(tmp_path, str(path))
    except Exception:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
