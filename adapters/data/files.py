"""File API adapter — upload, list, get, download, and delete files.

Uses the Gemini Files API (upload/v1beta/files) for managing uploaded
files. Mutating operations (upload, download, delete) are gated at the
dispatch policy boundary via registry metadata.

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/infra/sanitize.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.adapter.helpers import add_execute_flag, build_base_parser, check_dry_run, emit_json
from core.infra.client import api_call, upload_file
from core.infra.mime import guess_mime_for_path
from core.infra.sanitize import safe_print
from core.transport.raw_http.client import download_file_bytes


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the files adapter."""
    parser = build_base_parser("Manage files in the Gemini Files API")
    sub = parser.add_subparsers(dest="action", help="File action")

    upload_p = sub.add_parser("upload", help="Upload a file")
    add_execute_flag(upload_p)
    upload_p.add_argument("path", help="Path to the file to upload.")
    upload_p.add_argument("--mime", default=None, help="Override MIME type.")
    upload_p.add_argument("--display-name", default=None, help="Display name.")

    sub.add_parser("list", help="List uploaded files")

    get_p = sub.add_parser("get", help="Get file metadata")
    get_p.add_argument("name", help="File resource name (e.g., files/abc123).")

    delete_p = sub.add_parser("delete", help="Delete a file")
    add_execute_flag(delete_p)
    delete_p.add_argument("name", help="File resource name to delete.")

    # Phase 7: download a previously-uploaded file's raw bytes to a
    # local path. Remote read-only, but still gated because it writes
    # to the local filesystem and users expect no side effects without
    # explicit confirmation.
    download_p = sub.add_parser("download", help="Download a file's contents")
    add_execute_flag(download_p)
    download_p.add_argument("name", help="File resource name (e.g., files/abc123).")
    download_p.add_argument("out_path", help="Local path to write the downloaded bytes.")

    return parser


def run(
    action: str | None = None,
    path: str | None = None,
    name: str | None = None,
    out_path: str | None = None,
    mime: str | None = None,
    display_name: str | None = None,
    execute: bool = False,
    **kwargs: object,
) -> None:
    """Execute file management operations.

    Dispatch enforces the mutating policy gate; per-adapter check_dry_run
    remains as defense-in-depth when adapters are called directly.
    """
    if action == "upload":
        _upload(path=path, mime=mime, display_name=display_name, execute=execute)
    elif action == "list":
        _list_files()
    elif action == "get":
        _get_file(name=name)
    elif action == "delete":
        _delete_file(name=name, execute=execute)
    elif action == "download":
        _download(name=name, out_path=out_path, execute=execute)
    else:
        safe_print("[ERROR] No action specified. Use: upload, list, get, delete, download")


def _upload(
    path: str | None,
    mime: str | None,
    display_name: str | None,
    execute: bool,
) -> None:
    """Upload a file to the Gemini Files API."""
    if not path:
        safe_print("[ERROR] No file path provided.")
        return
    if check_dry_run(execute, f"upload {path}"):
        return

    file_path = Path(path)
    mime_type = mime or guess_mime_for_path(file_path)
    response = upload_file(file_path, mime_type=mime_type, display_name=display_name)

    wrapped_file = response.get("file")
    file_info = wrapped_file if isinstance(wrapped_file, dict) else response
    emit_json(
        {
            "name": file_info.get("name", ""),
            "uri": file_info.get("uri", ""),
            "mimeType": file_info.get("mimeType", mime_type),
            "sizeBytes": file_info.get("sizeBytes", ""),
            "state": file_info.get("state", ""),
        }
    )


def _list_files() -> None:
    """List all uploaded files."""
    response = api_call("files", method="GET")
    raw_files = response.get("files")
    files = raw_files if isinstance(raw_files, list) else []
    emit_json(
        {
            "count": len(files),
            "files": [
                {
                    "name": file_record.get("name", ""),
                    "displayName": file_record.get("displayName", ""),
                    "mimeType": file_record.get("mimeType", ""),
                    "sizeBytes": file_record.get("sizeBytes", ""),
                    "state": file_record.get("state", ""),
                }
                for file_record in files
            ],
        }
    )


def _get_file(name: str | None) -> None:
    """Get metadata for a single file."""
    if not name:
        safe_print("[ERROR] No file name provided.")
        return
    emit_json(api_call(name, method="GET"))


def _download(name: str | None, out_path: str | None, execute: bool) -> None:
    """Download an uploaded file's raw bytes to ``out_path``.

    Non-mutating on the remote side but still dry-run-gated because the
    adapter writes to the local filesystem and users running in dry-run
    mode expect ZERO side effects. Uses the raw HTTP transport helper
    ``download_file_bytes`` directly because the bytes response doesn't
    fit the JSON dict envelope the facade/coordinator is built around.
    """
    if not name:
        safe_print("[ERROR] No file name provided.")
        return
    if not out_path:
        safe_print("[ERROR] No output path provided.")
        return
    if check_dry_run(execute, f"download {name} -> {out_path}"):
        return

    data = download_file_bytes(name)
    target = Path(out_path)
    # Auto-create parent directories so nested output paths work
    # without a separate mkdir step. parents=True is idempotent.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    emit_json(
        {
            "path": str(target),
            "name": name,
            "size_bytes": len(data),
        }
    )


def _delete_file(name: str | None, execute: bool) -> None:
    """Delete a file."""
    if not name:
        safe_print("[ERROR] No file name provided.")
        return
    if check_dry_run(execute, f"delete {name}"):
        return
    api_call(name, method="DELETE")
    safe_print(f"Deleted {name}")
