"""File Search / hosted RAG adapter.

Manages File Search stores and queries them for retrieval-augmented
generation. Uses long-running operations for store uploads.
Preview capability with high churn risk.

Mutating operations require --execute. File Search stores persist
indefinitely (unlike Files API 48hr expiry).

Dependencies: core/infra/client.py, core/adapter/helpers.py,
    core/state/store_state.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import cast

from core.adapter.helpers import (
    add_execute_flag,
    build_base_parser,
    check_dry_run,
    emit_json,
    emit_output,
    extract_text,
)
from core.infra.sanitize import safe_print
from core.infra.client import api_call
from core.infra.config import load_config
from core.transport.base import GeminiResponse


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the file search adapter."""
    parser = build_base_parser("Manage File Search stores and query them")
    sub = parser.add_subparsers(dest="action", help="File Search action")

    create_p = sub.add_parser("create", help="Create a File Search store")
    add_execute_flag(create_p)
    create_p.add_argument("name", help="Display name for the store.")

    upload_p = sub.add_parser("upload", help="Upload a document to a store")
    add_execute_flag(upload_p)
    upload_p.add_argument("store", help="Store resource name.")
    upload_p.add_argument("file_uri", help="Gemini file URI to import.")

    query_p = sub.add_parser("query", help="Query a store with a prompt")
    query_p.add_argument("prompt", help="The search query.")
    query_p.add_argument("--store", required=True, help="Store resource name.")

    sub.add_parser("list", help="List File Search stores")

    delete_p = sub.add_parser("delete", help="Delete a store")
    add_execute_flag(delete_p)
    delete_p.add_argument("name", help="Store resource name to delete.")

    return parser


def run(
    action: str | None = None,
    name: str | None = None,
    store: str | None = None,
    file_uri: str | None = None,
    prompt: str | None = None,
    model: str | None = None,
    execute: bool = False,
    **kwargs: object,
) -> None:
    """Execute File Search operations."""
    if action == "create":
        _create_store(name=name, execute=execute)
    elif action == "upload":
        _upload_to_store(store=store, file_uri=file_uri, execute=execute)
    elif action == "query":
        _query_store(prompt=prompt, store=store, model=model)
    elif action == "list":
        _list_stores()
    elif action == "delete":
        _delete_store(name=name, execute=execute)
    else:
        safe_print("[ERROR] No action specified. Use: create, upload, query, list, delete")


def _create_store(name: str | None, execute: bool) -> None:
    """Create a new File Search store."""
    if not name:
        safe_print("[ERROR] No store name provided.")
        return
    if check_dry_run(execute, f"create File Search store '{name}'"):
        return

    body: dict[str, object] = {"displayName": name}
    response = api_call("fileSearchStores", body=body)
    emit_json(response)


def _upload_to_store(
    store: str | None,
    file_uri: str | None,
    execute: bool,
) -> None:
    """Upload a file to a File Search store."""
    if not store or not file_uri:
        safe_print("[ERROR] Both store and file_uri are required.")
        return
    if check_dry_run(execute, f"upload {file_uri} to store {store}"):
        return

    body: dict[str, object] = {"fileUri": file_uri}
    response = api_call(f"{store}:uploadToFileSearchStore", body=body)

    # Long-running operation — poll for completion
    op_name = response.get("name")
    if isinstance(op_name, str) and op_name:
        safe_print(f"Upload started: {op_name}")
        _poll_operation(op_name)
    else:
        emit_json(response)


def _query_store(
    prompt: str | None,
    store: str | None,
    model: str | None,
) -> None:
    """Query a File Search store."""
    if not prompt or not store:
        safe_print("[ERROR] Both prompt and --store are required.")
        return

    from core.routing.router import Router
    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("file_search")

    body: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"fileSearch": {"store": store}}],
    }

    response = cast(GeminiResponse, api_call(f"models/{resolved_model}:generateContent", body=body))
    text = extract_text(response)
    emit_output(text, output_dir=config.output_dir)


def _list_stores() -> None:
    """List all File Search stores."""
    response = api_call("fileSearchStores", method="GET")
    stores_value = response.get("fileSearchStores")
    stores = stores_value if isinstance(stores_value, list) else []
    emit_json({"count": len(stores), "stores": stores})


def _delete_store(name: str | None, execute: bool) -> None:
    """Delete a File Search store."""
    if not name:
        safe_print("[ERROR] No store name provided.")
        return
    if check_dry_run(execute, f"delete store {name}"):
        return
    api_call(name, method="DELETE")
    safe_print(f"Deleted store {name}")


def _poll_operation(op_name: str, max_wait: int = 1800) -> None:
    """Poll a long-running operation until completion or timeout."""
    start = time.time()
    while time.time() - start < max_wait:
        response = api_call(op_name, method="GET")
        if response.get("done"):
            emit_json(response)
            return
        time.sleep(10)

    safe_print(
        f"[POLL TIMEOUT] Operation not complete after {max_wait}s. "
        f"Operation: {op_name}. You can resume polling later."
    )
