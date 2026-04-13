"""Batch API adapter — submit, list, get, and cancel batch jobs.

Submits multiple requests for async processing at reduced cost.
Mutating operations (create, cancel) require --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

import argparse
from typing import Any

from core.adapter.helpers import build_base_parser, check_dry_run, emit_json
from core.infra.sanitize import safe_print
from core.infra.client import api_call


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the batch adapter."""
    parser = build_base_parser("Manage Gemini batch processing jobs")
    sub = parser.add_subparsers(dest="action", help="Batch action")

    create_p = sub.add_parser("create", help="Create a batch job")
    create_p.add_argument("--src", required=True, help="Source file URI (JSONL).")
    create_p.add_argument("--dest", required=True, help="Destination file URI.")

    sub.add_parser("list", help="List batch jobs")

    get_p = sub.add_parser("get", help="Get batch job status")
    get_p.add_argument("name", help="Batch job resource name.")

    cancel_p = sub.add_parser("cancel", help="Cancel a running batch job")
    cancel_p.add_argument("name", help="Batch job resource name to cancel.")

    return parser


def run(
    action: str | None = None,
    name: str | None = None,
    src: str | None = None,
    dest: str | None = None,
    model: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute batch management operations."""
    if action == "create":
        _create(src=src, dest=dest, model=model, execute=execute)
    elif action == "list":
        _list_batches()
    elif action == "get":
        _get_batch(name=name)
    elif action == "cancel":
        _cancel_batch(name=name, execute=execute)
    else:
        safe_print("[ERROR] No action specified. Use: create, list, get, cancel")


def _create(
    src: str | None,
    dest: str | None,
    model: str | None,
    execute: bool,
) -> None:
    """Create a batch processing job."""
    if not src or not dest:
        safe_print("[ERROR] Both --src and --dest are required.")
        return

    if check_dry_run(execute, f"create batch job from {src}"):
        return

    body: dict[str, Any] = {
        "inputConfig": {"gcsSource": {"inputUri": src}},
        "outputConfig": {"gcsDestination": {"outputUriPrefix": dest}},
    }
    if model:
        body["model"] = f"models/{model}"

    response = api_call("batchJobs", body=body)
    emit_json(response)


def _list_batches() -> None:
    """List all batch jobs."""
    response = api_call("batchJobs", method="GET")
    jobs = response.get("batchJobs", [])
    emit_json({"count": len(jobs), "jobs": jobs})


def _get_batch(name: str | None) -> None:
    """Get status of a batch job."""
    if not name:
        safe_print("[ERROR] No batch job name provided.")
        return
    response = api_call(name, method="GET")
    emit_json(response)


def _cancel_batch(name: str | None, execute: bool) -> None:
    """Cancel a running batch job."""
    if not name:
        safe_print("[ERROR] No batch job name provided.")
        return
    if check_dry_run(execute, f"cancel batch {name}"):
        return
    api_call(f"{name}:cancel", body={})
    safe_print(f"Cancelled batch {name}")
