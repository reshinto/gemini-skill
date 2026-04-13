"""Context caching adapter — create, list, get, and delete caches.

Caches large content (system instructions, files) to reduce cost and
latency on repeated requests. Mutating operations require --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, check_dry_run, emit_json
from core.infra.sanitize import safe_print
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the cache adapter."""
    parser = build_base_parser("Manage Gemini context caches")
    sub = parser.add_subparsers(dest="action", help="Cache action")

    create_p = sub.add_parser("create", help="Create a cache")
    create_p.add_argument("content", help="Content to cache (text or file URI).")
    create_p.add_argument("--ttl", default="3600s", help="Time-to-live (e.g., '3600s').")

    sub.add_parser("list", help="List existing caches")

    get_p = sub.add_parser("get", help="Get cache metadata")
    get_p.add_argument("name", help="Cache resource name.")

    delete_p = sub.add_parser("delete", help="Delete a cache")
    delete_p.add_argument("name", help="Cache resource name to delete.")

    return parser


def run(
    action: str | None = None,
    content: str | None = None,
    name: str | None = None,
    ttl: str = "3600s",
    model: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute cache management operations."""
    if action == "create":
        _create(content=content, ttl=ttl, model=model, execute=execute)
    elif action == "list":
        _list_caches()
    elif action == "get":
        _get_cache(name=name)
    elif action == "delete":
        _delete_cache(name=name, execute=execute)
    else:
        safe_print("[ERROR] No action specified. Use: create, list, get, delete")


def _create(
    content: str | None,
    ttl: str,
    model: str | None,
    execute: bool,
) -> None:
    """Create a context cache."""
    if not content:
        safe_print("[ERROR] No content provided.")
        return

    if check_dry_run(execute, f"create cache with TTL {ttl}"):
        return

    from core.routing.router import Router
    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("cache")

    body: dict[str, Any] = {
        "model": f"models/{resolved_model}",
        "contents": [{"role": "user", "parts": [{"text": content}]}],
        "ttl": ttl,
    }

    response = api_call("cachedContents", body=body)
    emit_json(response)


def _list_caches() -> None:
    """List all context caches."""
    response = api_call("cachedContents", method="GET")
    caches = response.get("cachedContents", [])
    emit_json({"count": len(caches), "caches": caches})


def _get_cache(name: str | None) -> None:
    """Get metadata for a single cache."""
    if not name:
        safe_print("[ERROR] No cache name provided.")
        return
    response = api_call(name, method="GET")
    emit_json(response)


def _delete_cache(name: str | None, execute: bool) -> None:
    """Delete a context cache."""
    if not name:
        safe_print("[ERROR] No cache name provided.")
        return
    if check_dry_run(execute, f"delete cache {name}"):
        return
    api_call(name, method="DELETE")
    safe_print(f"Deleted cache {name}")
