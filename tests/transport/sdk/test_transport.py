"""Tests for core/transport/sdk/transport.py — SdkTransport.

The SDK transport implements the Transport protocol by dispatching legacy
REST-shaped endpoint strings (e.g. ``models/gemini-2.5-flash:generateContent``)
into google-genai SDK method calls (e.g. ``client.models.generate_content``).

This test file is structured in slices that mirror the implementation slices:

- Slice 2a: class skeleton (name, Protocol fit, supports(), __init__)
- Slice 2b: api_call dispatch matrix (every supported endpoint family)
- Slice 2c: stream_generate_content + upload_file
- Slice 2d: _wrap_sdk_errors error mapping

Every test in this file mocks google.genai.Client. There is no live network.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _reset_client_factory() -> Iterator[None]:
    """Drop the client_factory lru_cache so each test gets a fresh instance."""
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


class TestSdkTransportSkeleton:
    """The Transport-shape contract the coordinator relies on."""

    def test_name_is_sdk(self) -> None:
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport.name == "sdk"
        assert SdkTransport().name == "sdk"

    def test_satisfies_transport_protocol(self) -> None:
        from core.transport.base import Transport
        from core.transport.sdk.transport import SdkTransport

        assert isinstance(SdkTransport(), Transport)

    def test_supported_capabilities_is_frozenset(self) -> None:
        """Guard against future test authors swapping the registry for a
        mutable ``set`` — the closed-world contract relies on immutability."""
        from core.transport.sdk.transport import SdkTransport

        assert isinstance(SdkTransport._SUPPORTED_CAPABILITIES, frozenset)


class TestSdkTransportSupports:
    """The explicit capability registry replaces try/except heuristics.

    Capabilities listed in ``_SUPPORTED_CAPABILITIES`` route through the SDK;
    everything else falls through to raw HTTP without an SDK probe. The
    coordinator (Phase 3) consults ``primary.supports(capability)`` BEFORE
    dispatching to ``api_call`` so the SDK transport never sees an
    unsupported capability call.
    """

    @pytest.mark.parametrize(
        "capability",
        [
            "text",
            "structured",
            "multimodal",
            "streaming",
            "embed",
            "token_count",
            "function_calling",
            "code_exec",
            "search",
            "image_gen",
            "video_gen",
            "files",
            "cache",
            "batch",
            "deep_research",
        ],
    )
    def test_supported_capabilities_return_true(self, capability: str) -> None:
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is True

    @pytest.mark.parametrize(
        "capability",
        ["maps", "music_gen", "computer_use", "file_search"],
    )
    def test_unsupported_capabilities_return_false(self, capability: str) -> None:
        """These four are not exposed by google-genai 1.33.0 — coordinator
        routes them deterministically to raw HTTP without probing the SDK."""
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is False

    @pytest.mark.parametrize(
        "capability",
        [
            "nonexistent-capability-xyz",
            "",  # empty string must not bypass the closed-world default
            "TEXT",  # case-sensitivity guard — uppercase aliases are NOT supported
            "text ",  # trailing whitespace must not match "text"
            " text",  # leading whitespace must not match "text"
            "text\x00",  # null byte injection guard
        ],
    )
    def test_adversarial_capability_strings_return_false(self, capability: str) -> None:
        """Closed-world default: anything not exactly in the registry returns
        False, including empty strings, case mismatches, whitespace-padded
        values, and null-byte-suffixed strings. This is the routing-bypass
        guard that keeps the coordinator's deterministic-fallback contract
        from being subverted by sloppy capability strings."""
        from core.transport.sdk.transport import SdkTransport

        assert SdkTransport().supports(capability) is False
