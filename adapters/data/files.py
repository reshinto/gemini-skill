"""File API adapter — upload, list, get, and delete files.

Uses the Gemini Files API (upload/v1beta/files) for managing uploaded
files. Tracks upload state via core/state/file_state.py to avoid
redundant uploads of identical content.

Mutating operations (upload, delete) require --execute flag.

Dependencies: core/infra/client.py, core/state/file_state.py,
    core/state/identity.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, check_dry_run, emit_json
from core.infra.client import api_call, upload_file
from core.infra.config import load_config
from core.infra.mime import guess_mime_for_path
from core.state.identity import compute_identity


def get_parser():
    """Return the argument parser for the files adapter."""
    parser = build_base_parser("Manage files in the Gemini Files API")
    sub = parser.add_subparsers(dest="action", help="File action")

    upload_p = sub.add_parser("upload", help="Upload a file")
    upload_p.add_argument("path", help="Path to the file to upload.")
    upload_p.add_argument("--mime", default=None, help="Override MIME type.")
    upload_p.add_argument("--display-name", default=None, help="Display name.")

    sub.add_parser("list", help="List uploaded files")

    get_p = sub.add_parser("get", help="Get file metadata")
    get_p.add_argument("name", help="File resource name (e.g., files/abc123).")

    delete_p = sub.add_parser("delete", help="Delete a file")
    delete_p.add_argument("name", help="File resource name to delete.")

    return parser


def run(
    action: str | None = None,
    path: str | None = None,
    name: str | None = None,
    mime: str | None = None,
    display_name: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute file management operations."""
    if action == "upload":
        _upload(path=path, mime=mime, display_name=display_name, execute=execute)
    elif action == "list":
        _list_files()
    elif action == "get":
        _get_file(name=name)
    elif action == "delete":
        _delete_file(name=name, execute=execute)
    else:
        from core.infra.sanitize import safe_print
        safe_print("[ERROR] No action specified. Use: upload, list, get, delete")


def _upload(
    path: str | None,
    mime: str | None,
    display_name: str | None,
    execute: bool,
) -> None:
    """Upload a file to the Gemini Files API."""
    if not path:
        from core.infra.sanitize import safe_print
        safe_print("[ERROR] No file path provided.")
        return

    if check_dry_run(execute, f"upload {path}"):
        return

    file_path = Path(path)
    mime_type = mime or guess_mime_for_path(file_path)
    response = upload_file(file_path, mime_type=mime_type, display_name=display_name)

    file_info = response.get("file", {})
    emit_json({
        "name": file_info.get("name", ""),
        "uri": file_info.get("uri", ""),
        "mimeType": file_info.get("mimeType", mime_type),
        "sizeBytes": file_info.get("sizeBytes", ""),
        "state": file_info.get("state", ""),
    })


def _list_files() -> None:
    """List all uploaded files."""
    response = api_call("files", method="GET")
    files = response.get("files", [])
    emit_json({
        "count": len(files),
        "files": [
            {
                "name": f.get("name", ""),
                "displayName": f.get("displayName", ""),
                "mimeType": f.get("mimeType", ""),
                "sizeBytes": f.get("sizeBytes", ""),
                "state": f.get("state", ""),
            }
            for f in files
        ],
    })


def _get_file(name: str | None) -> None:
    """Get metadata for a single file."""
    if not name:
        from core.infra.sanitize import safe_print
        safe_print("[ERROR] No file name provided.")
        return
    response = api_call(name, method="GET")
    emit_json(response)


def _delete_file(name: str | None, execute: bool) -> None:
    """Delete a file."""
    if not name:
        from core.infra.sanitize import safe_print
        safe_print("[ERROR] No file name provided.")
        return
    if check_dry_run(execute, f"delete {name}"):
        return
    api_call(name, method="DELETE")
    from core.infra.sanitize import safe_print
    safe_print(f"Deleted {name}")
