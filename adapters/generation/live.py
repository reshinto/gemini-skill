"""Live API realtime adapter — bidirectional streaming with Gemini Live.

The Live API exposes a realtime bidirectional session against Gemini Live
models (``gemini-live-2.5-flash-preview`` and friends). The session lives
inside an ``async with client.aio.live.connect(...) as session`` block;
inside that block the caller sends Content turns via
``session.send_client_content(...)`` and drains ``session.receive()``
as an async iterator until a message with ``server_content.turn_complete``
arrives.

This adapter is **async-only**. It declares ``IS_ASYNC = True`` at
module level so the Phase 6 dispatch layer runs it via
``asyncio.run(adapter.run_async(**kwargs))`` instead of the sync
``adapter.run(**kwargs)`` path. There is no ``run()`` function — a
caller that imports this module and tries to invoke it synchronously
will get a clear AttributeError.

Why direct SDK access instead of the transport facade? Same reason as
``adapters/generation/imagen.py``: the Live session shape doesn't fit
the ``GeminiResponse`` dict envelope the transport normalize layer is
built around, and the capability is SDK-only (the raw HTTP backend
has no analogue to plumb through). Going direct keeps the adapter
self-contained and the transport layer clean.

Dependencies: core/transport/sdk/client_factory.py (get_client),
core/adapter/helpers.py, core/infra/config.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import TracebackType
from typing import Protocol, cast

from core.adapter.helpers import build_base_parser
from core.infra.config import load_config
from core.transport.sdk.client_factory import get_client

# Async dispatch marker — consulted by core/cli/dispatch.py via
# ``getattr(module, "IS_ASYNC", False)``. Adapters without this flag
# take the sync dispatch path; adapters with it take the
# ``asyncio.run(module.run_async(**kwargs))`` path.
IS_ASYNC: bool = True

# Modalities the Live API accepts for the response channel. ``TEXT``
# is the default because text-only sessions are the cheapest and most
# testable surface. Audio / video modes exist in the SDK but require
# additional client-side media handling that's out of scope for this
# adapter's Phase 7 scope.
_LIVE_MODALITIES: tuple[str, ...] = ("TEXT", "AUDIO")


class _LiveServerContentProtocol(Protocol):
    turn_complete: bool


class _LiveMessageProtocol(Protocol):
    text: str | None
    server_content: _LiveServerContentProtocol | None


class _LiveReceiveStreamProtocol(Protocol):
    def __aiter__(self) -> AsyncIterator[_LiveMessageProtocol]: ...

    async def __anext__(self) -> _LiveMessageProtocol: ...

    async def aclose(self) -> None: ...


class _LiveSessionProtocol(Protocol):
    async def send_client_content(self, *, turns: list[object]) -> object: ...

    def receive(self) -> AsyncIterator[_LiveMessageProtocol] | _LiveReceiveStreamProtocol: ...


class _LiveConnectContextManagerProtocol(Protocol):
    async def __aenter__(self) -> _LiveSessionProtocol: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> object: ...


class _LiveServiceProtocol(Protocol):
    def connect(self, *, model: str, config: object) -> _LiveConnectContextManagerProtocol: ...


class _LiveAioProtocol(Protocol):
    live: _LiveServiceProtocol


class _LiveClientProtocol(Protocol):
    aio: _LiveAioProtocol


def get_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the live adapter."""
    parser = build_base_parser("Realtime bidirectional session with Gemini Live")
    parser.add_argument("prompt", help="The initial prompt to send to the Live session.")
    parser.add_argument(
        "--modality",
        default="TEXT",
        choices=_LIVE_MODALITIES,
        help="Response modality (TEXT or AUDIO).",
    )
    return parser


async def run_async(
    prompt: str,
    model: str | None = None,
    modality: str = "TEXT",
    **kwargs: object,
) -> None:
    """Open a Live session, send the prompt, drain responses to stdout.

    The drain loop stops on the first message whose ``server_content``
    carries ``turn_complete=True``. Messages with ``text=None`` (e.g.
    server-side control frames) are skipped without printing a blank
    line. Messages queued after turn_complete are ignored — the
    adapter's contract is one user turn per invocation.

    Args:
        prompt: Initial user turn text.
        model: Optional Gemini Live model override. Defaults to the
            router's pick for the ``live`` capability.
        modality: Response modality — ``"TEXT"`` or ``"AUDIO"``.
        **kwargs: Unused; accepted for parser-kwargs compatibility.
    """
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("live")

    # Lazy imports of the SDK types so the module still imports cleanly
    # when google-genai isn't available (the parser surface remains
    # reachable for ``--help`` even in that case).
    from google.genai import types

    # The SDK's ``response_modalities`` field is typed as
    # ``list[Modality]`` (an enum), but pydantic accepts the string
    # equivalent at validation time. Passing the validated dict through
    # ``model_validate`` keeps mypy happy without forcing callers to
    # import the Modality enum.
    live_config = types.LiveConnectConfig.model_validate({"response_modalities": [modality]})
    client = cast(_LiveClientProtocol, get_client())

    async with client.aio.live.connect(model=resolved_model, config=live_config) as session:
        # Send the prompt as a single Content turn. The SDK's
        # ``send_client_content`` accepts either a single Content
        # or a list; a list of one is the simplest shape.
        user_turn = types.Content(role="user", parts=[types.Part(text=prompt)])
        await session.send_client_content(turns=[user_turn])

        receive_stream = session.receive()
        try:
            async for msg in receive_stream:
                # Skip control frames that don't carry text output — a
                # blank line for every server keepalive would spam stdout
                # and break Claude Code's token budget.
                text = getattr(msg, "text", None)
                if text:
                    # ``end="", flush=True`` matches the existing streaming
                    # adapter's contract — chunks land on stdout as they
                    # arrive so a human reader sees incremental progress.
                    print(text, end="", flush=True)

                server_content = getattr(msg, "server_content", None)
                if server_content is not None and getattr(server_content, "turn_complete", False):
                    break
        finally:
            aclose = getattr(receive_stream, "aclose", None)
            if callable(aclose):
                maybe_awaitable = aclose()
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable

    # Trailing newline so the next shell prompt starts on its own line.
    # Not inside the loop because the streamed text may not end with
    # ``\n`` naturally and a loop-tail newline would double-up.
    sys.stdout.write("\n")
    sys.stdout.flush()
