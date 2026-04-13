"""Tests for adapters/generation/live.py — Live API realtime adapter.

The Live API is google-genai's bidirectional streaming surface exposed
as ``client.aio.live.connect(model, config)``. The connect call returns
an async context manager; inside the ``async with`` block the caller
sends ``Content`` turns via ``session.send_client_content(...)`` and
drains ``session.receive()`` as an async iterator until a message with
``server_content.turn_complete == True`` arrives.

The adapter is ``IS_ASYNC = True`` — the dispatch layer detects the
marker and runs it via ``asyncio.run(adapter.run_async(**kwargs))``.
All tests mock ``client.aio.live.connect``; no live network.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeReceiveStream:
    """Async iterator returned by ``_FakeSession.receive``.

    Exposes ``aclose`` so the adapter can explicitly close the stream
    when it stops on ``turn_complete`` before consuming every message.
    """

    def __init__(self, messages: list[MagicMock]) -> None:
        self._iter = iter(messages)
        self.aclose = AsyncMock()

    def __aiter__(self) -> _FakeReceiveStream:
        return self

    async def __anext__(self) -> MagicMock:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeSession:
    """A minimal fake that mimics ``live.connect`` session behavior.

    ``send_client_content`` is an AsyncMock so the test can assert it
    was awaited with the right Content. ``receive`` returns a fresh
    async iterator each call so the adapter's drain loop exercises
    the ``async for`` surface naturally.
    """

    def __init__(self, messages: list[MagicMock]) -> None:
        self._messages = messages
        self.send_client_content = AsyncMock()
        self.last_receive_stream: _FakeReceiveStream | None = None

    def receive(self) -> _FakeReceiveStream:
        self.last_receive_stream = _FakeReceiveStream(self._messages)
        return self.last_receive_stream


class _FakeConnectCM:
    """Async context manager wrapper around a _FakeSession."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        return None


def _make_message(text: str | None = None, turn_complete: bool = False) -> MagicMock:
    """Build a mock live-session message with the shape the adapter reads."""
    msg = MagicMock()
    msg.text = text
    if turn_complete:
        msg.server_content = MagicMock()
        msg.server_content.turn_complete = True
    else:
        msg.server_content = MagicMock()
        msg.server_content.turn_complete = False
    return msg


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Return a mocked SDK client whose ``aio.live.connect`` yields a
    _FakeSession. Tests override the session messages by reassigning
    ``patched_client._fake_messages``."""
    client = MagicMock(name="genai.Client")
    client.aio = MagicMock(name="client.aio")
    client.aio.live = MagicMock(name="client.aio.live")
    default_messages: list[MagicMock] = [
        _make_message(text="hi"),
        _make_message(text=" there"),
        _make_message(turn_complete=True),
    ]
    client._fake_messages = default_messages

    def _connect(**_: object) -> _FakeConnectCM:
        return _FakeConnectCM(_FakeSession(client._fake_messages))

    client.aio.live.connect = MagicMock(side_effect=_connect)
    return client


@pytest.fixture(autouse=True)
def _reset_client_cache() -> Iterator[None]:
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


class TestLiveModuleFlags:
    def test_is_async_marker_true(self) -> None:
        from adapters.generation import live

        assert live.IS_ASYNC is True

    def test_has_run_async(self) -> None:
        import inspect

        from adapters.generation import live

        assert inspect.iscoroutinefunction(live.run_async)


class TestLiveGetParser:
    def test_has_prompt(self) -> None:
        from adapters.generation.live import get_parser

        args = get_parser().parse_args(["hello"])
        assert args.prompt == "hello"

    def test_defaults(self) -> None:
        from adapters.generation.live import get_parser

        args = get_parser().parse_args(["hi"])
        # Modality defaults to TEXT so text-only uses don't need a flag.
        assert args.modality == "TEXT"

    def test_modality_choice(self) -> None:
        from adapters.generation.live import get_parser

        args = get_parser().parse_args(["hi", "--modality", "AUDIO"])
        assert args.modality == "AUDIO"


class TestLiveRunAsync:
    @pytest.mark.asyncio
    async def test_streams_text_until_turn_complete(
        self, patched_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.live import run_async

        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="say hi", modality="TEXT")

        out = capsys.readouterr().out
        assert "hi" in out
        assert " there" in out

    @pytest.mark.asyncio
    async def test_sends_prompt_as_content_turn(self, patched_client: MagicMock) -> None:
        from adapters.generation.live import run_async

        captured_session: dict[str, _FakeSession] = {}
        original_connect = patched_client.aio.live.connect

        def _spy_connect(**kw: object) -> _FakeConnectCM:
            cm = original_connect(**kw)
            captured_session["s"] = cm._session
            return cm

        patched_client.aio.live.connect = MagicMock(side_effect=_spy_connect)

        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="say hi", modality="TEXT")

        session = captured_session["s"]
        session.send_client_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_receives_model_and_modalities(self, patched_client: MagicMock) -> None:
        from adapters.generation.live import run_async

        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="say hi", modality="TEXT", model="gemini-live-test")

        call = patched_client.aio.live.connect.call_args
        assert call.kwargs["model"] == "gemini-live-test"
        # config carries response_modalities set to the chosen value
        cfg = call.kwargs["config"]
        assert "TEXT" in cfg.response_modalities

    @pytest.mark.asyncio
    async def test_stops_on_turn_complete_even_with_trailing_messages(
        self, patched_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """After a ``turn_complete`` message, the adapter stops draining
        even if the session has more messages queued. This prevents a
        runaway loop on a misbehaving server that keeps the channel
        open past turn completion."""
        from adapters.generation.live import run_async

        patched_client._fake_messages = [
            _make_message(text="a"),
            _make_message(turn_complete=True),
            _make_message(text="SHOULD_NOT_APPEAR"),
        ]
        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="hi", modality="TEXT")
        out = capsys.readouterr().out
        assert "a" in out
        assert "SHOULD_NOT_APPEAR" not in out

    @pytest.mark.asyncio
    async def test_skips_messages_without_text(
        self, patched_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Messages with ``text=None`` (e.g. server-side control frames)
        are skipped without printing a blank line."""
        from adapters.generation.live import run_async

        patched_client._fake_messages = [
            _make_message(text=None),
            _make_message(text="only-this"),
            _make_message(turn_complete=True),
        ]
        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="hi", modality="TEXT")
        out = capsys.readouterr().out
        assert "only-this" in out

    @pytest.mark.asyncio
    async def test_closes_receive_stream_when_turn_completes(
        self, patched_client: MagicMock
    ) -> None:
        from adapters.generation.live import run_async

        captured_session: dict[str, _FakeSession] = {}
        original_connect = patched_client.aio.live.connect

        def _spy_connect(**kw: object) -> _FakeConnectCM:
            cm = original_connect(**kw)
            captured_session["s"] = cm._session
            return cm

        patched_client._fake_messages = [
            _make_message(text="a"),
            _make_message(turn_complete=True),
            _make_message(text="ignored"),
        ]
        patched_client.aio.live.connect = MagicMock(side_effect=_spy_connect)

        with (
            patch("adapters.generation.live.get_client", return_value=patched_client),
            patch("adapters.generation.live.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            await run_async(prompt="hi", modality="TEXT")

        session = captured_session["s"]
        assert session.last_receive_stream is not None
        session.last_receive_stream.aclose.assert_awaited_once()
