"""Tests for core/transport/sdk/client_factory.py — lazy SDK client construction.

The client factory is the single point where the skill instantiates a
``google.genai.Client``. Three contracts must hold:

1. **Lazy import**: ``import google.genai`` happens inside the function body,
   not at module top. The module must be importable on a machine where
   google-genai is NOT installed — that's the whole point of the dual-backend
   architecture (raw HTTP keeps working without the SDK).
2. **API-key auth only**: the client is always built with ``api_key=...``.
   Vertex AI, ADC, and ``google-auth`` are explicitly out of scope.
3. **Singleton caching**: ``get_client()`` returns the same Client instance
   across calls within a process (via ``functools.lru_cache``). Tests need a
   way to reset the cache between runs.

The async client (``client.aio``) is exposed via ``get_async_client()`` so
callers that only need async surfaces don't need to know about the parent.
"""

from __future__ import annotations

import sys
from unittest import mock

import pytest


# NOTE: cache reset is handled by the autouse fixture in
# tests/transport/conftest.py which runs for every test in this directory
# tree (including this file under tests/transport/sdk/). Do not duplicate
# the fixture here — keeping it in one place means a future addition
# (e.g. a third singleton) only needs editing once.


class TestGetClient:
    """``get_client()`` builds a ``google.genai.Client`` with API-key auth."""

    def test_returns_client_built_with_resolved_key(self):
        from core.transport.sdk import client_factory

        fake_client = mock.Mock(name="genai.Client instance")
        fake_genai = mock.Mock()
        fake_genai.Client.return_value = fake_client

        with mock.patch.dict(
            sys.modules, {"google.genai": fake_genai, "google": mock.Mock(genai=fake_genai)}
        ):
            with mock.patch.object(
                client_factory, "resolve_key", return_value="test-sdk-key-001"
            ) as mock_resolve:
                result = client_factory.get_client()

        assert result is fake_client
        mock_resolve.assert_called_once_with()
        fake_genai.Client.assert_called_once_with(api_key="test-sdk-key-001")

    def test_is_cached_across_calls(self):
        from core.transport.sdk import client_factory

        fake_client = mock.Mock()
        fake_genai = mock.Mock()
        fake_genai.Client.return_value = fake_client

        with mock.patch.dict(
            sys.modules, {"google.genai": fake_genai, "google": mock.Mock(genai=fake_genai)}
        ):
            with mock.patch.object(
                client_factory, "resolve_key", return_value="test-sdk-key-cached"
            ):
                first = client_factory.get_client()
                second = client_factory.get_client()

        assert first is second
        fake_genai.Client.assert_called_once()

    def test_import_error_raises_backend_unavailable(self):
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk import client_factory

        # Setting sys.modules["google.genai"] = None is the documented Python
        # idiom for "pretend this module is not installed". The next `from
        # google import genai` raises ModuleNotFoundError, which our factory
        # catches and re-raises as BackendUnavailableError. We ALSO patch
        # "google" itself to None — `from google import genai` may otherwise
        # find the genai attribute on an already-imported `google` package
        # object instead of consulting sys.modules. Patching both is the
        # belt-and-braces approach that works regardless of how the parent
        # package was loaded into the test process.
        with mock.patch.dict(sys.modules, {"google.genai": None, "google": None}):
            with pytest.raises(BackendUnavailableError) as exc_info:
                client_factory.get_client()

        assert "google-genai" in str(exc_info.value)


class TestClientConstructionErrorSanitized:
    """If genai.Client(...) raises with the api_key in the message, the
    wrapper must redact it before re-raising as BackendUnavailableError."""

    def test_constructor_error_with_embedded_key_is_redacted(self):
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk import client_factory

        # AIza + 35 chars = 39 total — matches the sanitize regex pattern
        # the skill uses to redact Google API keys from error surfaces.
        leaked_key = "AIzaSyTestKey12345678901234567890123456"

        fake_genai = mock.Mock()
        fake_genai.Client.side_effect = ValueError(f"bad key {leaked_key} rejected")

        with mock.patch.dict(
            sys.modules, {"google.genai": fake_genai, "google": mock.Mock(genai=fake_genai)}
        ):
            with mock.patch.object(client_factory, "resolve_key", return_value=leaked_key):
                with pytest.raises(BackendUnavailableError) as exc_info:
                    client_factory.get_client()

        message = str(exc_info.value)
        assert leaked_key not in message
        assert "[REDACTED]" in message

    def test_constructor_error_cause_chain_is_suppressed(self):
        """``raise ... from None`` deliberately drops __cause__ so traceback
        serializers (Sentry, logging.exception) cannot walk the chain and
        print the original unsanitized exception's str() — which would
        echo the api_key argument the constructor was called with."""
        from core.transport.base import BackendUnavailableError
        from core.transport.sdk import client_factory

        leaked_key = "AIzaSyTestKey12345678901234567890123456"
        fake_genai = mock.Mock()
        fake_genai.Client.side_effect = ValueError(f"raw {leaked_key}")

        with mock.patch.dict(
            sys.modules, {"google.genai": fake_genai, "google": mock.Mock(genai=fake_genai)}
        ):
            with mock.patch.object(client_factory, "resolve_key", return_value=leaked_key):
                with pytest.raises(BackendUnavailableError) as exc_info:
                    client_factory.get_client()

        # __cause__ must be None — the chain is intentionally suppressed.
        assert exc_info.value.__cause__ is None


class TestGetAsyncClient:
    """``get_async_client()`` returns the parent client's ``.aio`` attribute."""

    def test_returns_aio_namespace_of_sync_client(self):
        from core.transport.sdk import client_factory

        fake_aio = mock.Mock(name="client.aio")
        fake_client = mock.Mock()
        fake_client.aio = fake_aio
        fake_genai = mock.Mock()
        fake_genai.Client.return_value = fake_client

        with mock.patch.dict(
            sys.modules, {"google.genai": fake_genai, "google": mock.Mock(genai=fake_genai)}
        ):
            with mock.patch.object(
                client_factory, "resolve_key", return_value="test-sdk-key-async"
            ):
                result = client_factory.get_async_client()

        assert result is fake_aio
