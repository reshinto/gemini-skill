"""Video generation adapter — Veo.

Uses long-running operations (predictLongRunning). Polls operation
until done, extracts download URI, saves video to file.
5-10 min generation time. Mutating — requires --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from urllib.request import Request, urlopen

from core.adapter.helpers import (
    add_execute_flag,
    build_base_parser,
    check_dry_run,
    create_media_output_file,
    emit_json,
)
from core.infra.client import api_call
from core.infra.config import load_config
from core.infra.sanitize import safe_print


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the video generation adapter."""
    parser = build_base_parser("Generate videos using Veo")
    add_execute_flag(parser)
    parser.add_argument("prompt", help="Video generation prompt.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for output files.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Seconds between poll attempts (default: 15).",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=1800,
        help="Maximum seconds to wait for generation (default: 1800).",
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    output_dir: str | None = None,
    poll_interval: int = 15,
    max_wait: int = 1800,
    execute: bool = False,
    **kwargs: object,
) -> None:
    """Execute video generation with Veo."""
    if check_dry_run(execute, f"generate video: {prompt}"):
        return

    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("video_gen")

    body: dict[str, object] = {
        "instances": [{"prompt": prompt}],
    }

    # Submit long-running operation
    op = api_call(
        f"models/{resolved_model}:predictLongRunning",
        body=body,
    )
    operation_name_value = op.get("name")
    if not isinstance(operation_name_value, str) or not operation_name_value:
        safe_print("[ERROR] Video generation did not return an operation name.")
        emit_json(op)
        return
    operation_name = operation_name_value
    safe_print(f"Video generation started: {operation_name}")

    # Poll until done
    start = time.time()
    while time.time() - start < max_wait:
        status = api_call(operation_name, method="GET")
        if status.get("done"):
            break
        time.sleep(poll_interval)
    else:
        safe_print(
            f"[POLL TIMEOUT] Video not ready after {max_wait}s. " f"Operation: {operation_name}"
        )
        return

    # Extract video URI and download
    video_uri = _extract_video_uri(status)
    if not video_uri:
        safe_print("[ERROR] No video URI in response.")
        emit_json(status)
        return

    video_bytes = _download(video_uri)
    out_dir = output_dir or config.output_dir
    output_path = create_media_output_file(".mp4", out_dir)
    Path(output_path).write_bytes(video_bytes)

    emit_json(
        {
            "path": output_path,
            "mime_type": "video/mp4",
            "size_bytes": len(video_bytes),
            "operation": operation_name,
        }
    )


def _extract_video_uri(status: dict[str, object]) -> str | None:
    """Extract video download URI from operation response."""
    response = status.get("response")
    if not isinstance(response, dict):
        return None
    videos = response.get("generatedVideos")
    if not isinstance(videos, list) or not videos:
        return None
    first_video = videos[0]
    if not isinstance(first_video, dict):
        return None
    video = first_video.get("video")
    if not isinstance(video, dict):
        return None
    uri = video.get("uri")
    if isinstance(uri, str):
        return uri
    return None


def _download(uri: str) -> bytes:
    """Download content from a URI."""
    request = Request(uri)
    with urlopen(request, timeout=300) as response:
        return response.read()
