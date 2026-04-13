"""Tests for core/infra/client.py — the legacy shim with the api_key bypass.

The shim is a thin wrapper that forwards ``api_call`` /
``stream_generate_content`` / ``upload_file`` to the public facade in
``core/transport`` so adapters that import via the legacy path keep
working. The single piece of non-trivial behavior is the ``api_key=``
bypass: when a caller passes an explicit key, the shim routes directly
to ``core/transport/raw_http/client.api_call`` rather than through the
coordinator. This file pins both the re-export contract and the bypass
behavior.
"""

from __future__ import annotations

from unittest import mock

import pytest


class TestReExports:
    """Names re-exported from the facade must be the same objects."""

    def test_api_call_re_exported(self) -> None:
        import core.infra.client as shim

        assert callable(shim.api_call)

    def test_stream_re_exported(self) -> None:
        import core.infra.client as shim
        import core.transport as facade

        assert shim.stream_generate_content is facade.stream_generate_content

    def test_upload_re_exported(self) -> None:
        import core.infra.client as shim
        import core.transport as facade

        assert shim.upload_file is facade.upload_file

    def test_base_url_re_exported(self) -> None:
        import core.infra.client as shim
        from core.transport.raw_http.client import BASE_URL

        assert shim.BASE_URL == BASE_URL


class TestApiKeyBypass:
    """``api_call(api_key=...)`` must route directly to the raw HTTP client.

    The bypass exists because the SDK backend has no equivalent
    direct-key parameter; passing ``api_key`` is unambiguously a request
    for the raw HTTP path. The coordinator must NOT be touched.
    """

    def test_explicit_api_key_bypasses_coordinator(self) -> None:
        import core.infra.client as shim
        import core.transport as facade

        fake_coord = mock.Mock()
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            with mock.patch(
                "core.transport.raw_http.client.api_call",
                return_value={"candidates": [{"text": "via raw"}]},
            ) as direct:
                result = shim.api_call(
                    endpoint="models/gemini:generateContent",
                    body={"contents": []},
                    api_key="explicit-key-value",
                )

        assert result == {"candidates": [{"text": "via raw"}]}
        # Coordinator was NEVER called.
        fake_coord.execute_api_call.assert_not_called()
        # Direct raw HTTP call was made with the key forwarded through.
        direct.assert_called_once()
        assert direct.call_args.kwargs["api_key"] == "explicit-key-value"

    def test_no_api_key_routes_through_facade(self) -> None:
        """When ``api_key`` is None, the shim forwards to the public
        facade which goes through the coordinator. Verify the facade
        sees the call and the raw HTTP client does NOT."""
        import core.infra.client as shim
        import core.transport as facade

        fake_coord = mock.Mock()
        fake_coord.execute_api_call.return_value = {"candidates": [{"text": "via coord"}]}
        with mock.patch.object(facade, "_get_coordinator", return_value=fake_coord):
            with mock.patch(
                "core.transport.raw_http.client.api_call"
            ) as direct:
                result = shim.api_call(
                    endpoint="models/gemini:generateContent",
                    body={"contents": []},
                )

        assert result == {"candidates": [{"text": "via coord"}]}
        fake_coord.execute_api_call.assert_called_once()
        direct.assert_not_called()

    def test_api_key_bypass_forwards_all_kwargs(self) -> None:
        """Verify every kwarg flows through to the raw HTTP client."""
        import core.infra.client as shim

        with mock.patch(
            "core.transport.raw_http.client.api_call", return_value={}
        ) as direct:
            shim.api_call(
                endpoint="models",
                body={"foo": "bar"},
                method="GET",
                api_version="v1",
                timeout=42,
                api_key="abc",
            )

        kwargs = direct.call_args.kwargs
        assert kwargs["endpoint"] == "models"
        assert kwargs["body"] == {"foo": "bar"}
        assert kwargs["method"] == "GET"
        assert kwargs["api_version"] == "v1"
        assert kwargs["timeout"] == 42
        assert kwargs["api_key"] == "abc"

    def test_api_key_bypass_with_none_body_passes_none(self) -> None:
        """Edge case: GET with no body — None must be forwarded as None
        (not coerced to an empty dict by the dict() copy)."""
        import core.infra.client as shim

        with mock.patch(
            "core.transport.raw_http.client.api_call", return_value={}
        ) as direct:
            shim.api_call(endpoint="models", method="GET", api_key="k")

        assert direct.call_args.kwargs["body"] is None
