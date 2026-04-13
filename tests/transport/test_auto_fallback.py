"""End-to-end auto-fallback tests using REAL backends + the coordinator.

The coordinator unit tests in ``test_coordinator.py`` use ``Mock(spec=Transport)``
fakes to pin the dispatch matrix. This file is the integration cousin: real
``SdkTransport`` + real ``RawHttpTransport`` instances wired through the real
``TransportCoordinator``, with mocks pushed all the way down to
``client_factory.get_client`` (SDK side) and ``urlopen`` (raw HTTP side).

The point: prove that for every SDK-unsupported capability listed in the
canonical plan (``maps``, ``music_gen``, ``computer_use``, ``file_search``,
``deep_research``), the coordinator's capability gate routes to raw HTTP
**without any SDK probe at all** — i.e. ``get_client`` is never called and
``client.models.*`` / ``client.files.*`` / etc. are never touched. This is
the deterministic-routing contract that replaces the architect-rejected
"try SDK, catch AttributeError" heuristic.
"""

from __future__ import annotations

from unittest import mock

import pytest

# NOTE: Singleton reset is handled by the autouse fixture in
# tests/transport/conftest.py which runs for every test in this directory.
# Do not duplicate the fixture here — keeping it in one place means a
# future addition (e.g. a third singleton) only needs editing once.


@pytest.mark.parametrize(
    "capability",
    [
        "maps",
        "music_gen",
        "computer_use",
        "file_search",
        "deep_research",
    ],
)
class TestUnsupportedCapabilityRoutesToRawHttp:
    """For every capability the SDK does NOT claim to support, the
    coordinator must route to raw HTTP without ever constructing the
    SDK client. Parametrized across the canonical not-supported list."""

    def test_capability_gate_skips_sdk_entirely(self, capability: str) -> None:
        from core.transport.coordinator import TransportCoordinator
        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        # Mock the raw HTTP underlying client so no real network call.
        # The coordinator should reach this through the fallback path.
        with mock.patch(
            "core.transport.raw_http.transport._client_api_call",
            return_value={"candidates": [{"text": f"raw_http handled {capability}"}]},
        ) as raw_mock:
            # Patch the SDK client factory at its IMPORT site in the SDK
            # transport module. If the coordinator misroutes and accidentally
            # touches the SDK, this Mock will be called and fail the test.
            with mock.patch(
                "core.transport.sdk.transport.get_client"
            ) as sdk_get_client:
                coord = TransportCoordinator(
                    primary=SdkTransport(),
                    fallback=RawHttpTransport(),
                )
                result = coord.execute_api_call(
                    endpoint="models/gemini:generateContent",
                    body={"contents": []},
                    method="POST",
                    api_version="v1beta",
                    timeout=30,
                    capability=capability,
                )

        # Raw HTTP got the call.
        raw_mock.assert_called_once()
        # SDK was NEVER probed — get_client must not have been invoked.
        sdk_get_client.assert_not_called()
        assert result == {"candidates": [{"text": f"raw_http handled {capability}"}]}


class TestSupportedCapabilityRoutesToSdk:
    """The mirror case: a supported capability lands on the SDK and the raw
    HTTP path is never touched. Pins the contract in the other direction
    so a registry mistake doesn't silently disable the SDK backend."""

    def test_text_capability_routes_to_sdk(self) -> None:
        from core.transport.coordinator import TransportCoordinator
        from core.transport.raw_http.transport import RawHttpTransport
        from core.transport.sdk.transport import SdkTransport

        # Build a pydantic-shaped fake response.
        fake_resp = mock.Mock()
        fake_resp.model_dump.return_value = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "from sdk"}]},
                    "finish_reason": "STOP",
                }
            ]
        }

        fake_client = mock.Mock(name="genai.Client")
        fake_client.models = mock.Mock()
        fake_client.models.generate_content.return_value = fake_resp

        with mock.patch(
            "core.transport.sdk.transport.get_client", return_value=fake_client
        ):
            with mock.patch(
                "core.transport.raw_http.transport._client_api_call"
            ) as raw_mock:
                coord = TransportCoordinator(
                    primary=SdkTransport(),
                    fallback=RawHttpTransport(),
                )
                result = coord.execute_api_call(
                    endpoint="models/gemini-2.5-flash:generateContent",
                    body={"contents": []},
                    method="POST",
                    api_version="v1beta",
                    timeout=30,
                    capability="text",
                )

        fake_client.models.generate_content.assert_called_once()
        raw_mock.assert_not_called()
        assert result["candidates"][0]["content"]["parts"][0]["text"] == "from sdk"


class TestUnsupportedCapabilityNoFallbackRaises:
    """When the SDK refuses a capability AND no fallback is configured,
    the coordinator must raise BackendUnavailableError instead of silently
    invoking the primary anyway."""

    def test_no_fallback_raises_backend_unavailable(self) -> None:
        from core.transport.base import BackendUnavailableError
        from core.transport.coordinator import TransportCoordinator
        from core.transport.sdk.transport import SdkTransport

        with mock.patch(
            "core.transport.sdk.transport.get_client"
        ) as sdk_get_client:
            coord = TransportCoordinator(primary=SdkTransport(), fallback=None)
            with pytest.raises(BackendUnavailableError, match="maps"):
                coord.execute_api_call(
                    endpoint="x",
                    body={},
                    method="POST",
                    api_version="v1beta",
                    timeout=30,
                    capability="maps",
                )
        sdk_get_client.assert_not_called()


class TestFacadeLegacyPathDoesNotUseCapabilityGate:
    """The legacy facade calls execute_api_call with capability=None, so
    the gate is skipped and the primary always runs first. Pin this so a
    future facade refactor that accidentally turns on the gate breaks
    the existing 19 adapters in a visible way."""

    def test_legacy_facade_uses_capability_none(self) -> None:
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_api_call.return_value = {"candidates": []}
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            facade.api_call("models/gemini:generateContent", body={"contents": []})
        # Most important assertion: capability=None was passed through.
        assert fake_coord.execute_api_call.call_args.kwargs["capability"] is None
