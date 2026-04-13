"""Tests for core/transport/policy.py — the fallback eligibility decision table.

The policy layer is a pure function: given an exception that bubbled out of
the primary backend, decide whether the coordinator should attempt the
fallback backend or re-raise immediately. This file is the contract for that
decision — every supported exception class is covered with explicit
parametrized rows so future edits cannot silently change behavior.

Why a pure function: the coordinator needs to be backend-agnostic and
testable without any HTTP/SDK setup. By isolating the decision in a
side-effect-free function, we get exhaustive coverage with trivial fixtures.
"""

from __future__ import annotations

import socket
from urllib.error import URLError

import pytest

from core.infra.errors import (
    AuthError,
    APIError,
    CapabilityUnavailableError,
    CostLimitError,
    ModelNotFoundError,
)


class TestNonEligibleErrors:
    """Errors that must NEVER trigger fallback.

    Auth, model-not-found, cost-limit, and programmer bugs (assertion / value /
    type errors) are all conditions that will fail identically on the fallback
    backend, so retrying wastes time and obscures the real cause.
    """

    def test_auth_error_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(AuthError("bad key")) is False

    def test_model_not_found_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(ModelNotFoundError("no such model")) is False

    def test_cost_limit_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(CostLimitError("over budget", current=10.0, limit=5.0)) is False

    def test_assertion_error_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(AssertionError("invariant violated")) is False

    def test_value_error_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(ValueError("bad json")) is False

    def test_type_error_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(TypeError("can't multiply sequence")) is False


class TestApiErrorByStatusCode:
    """APIError eligibility depends entirely on the HTTP status code.

    Rule: 4xx (except 429) is the request's fault and will fail the same way
    on the fallback. 429 (rate limit) and 5xx (server) and any APIError with
    no status code (e.g. parse failure) are eligible.
    """

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_4xx_except_429_not_eligible(self, code):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(APIError("client error", status_code=code)) is False

    def test_429_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(APIError("rate limit", status_code=429)) is True

    @pytest.mark.parametrize("code", [500, 502, 503, 504])
    def test_5xx_eligible(self, code):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(APIError("server error", status_code=code)) is True

    def test_api_error_without_status_code_is_eligible(self):
        """Parse failures and other transport-class APIErrors carry no code."""
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(APIError("parse failed")) is True


class TestBackendAvailabilityErrors:
    """Errors that mean 'this backend can't even start' must be eligible."""

    def test_capability_unavailable_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(CapabilityUnavailableError("missing tool")) is True

    def test_import_error_is_eligible(self):
        """Raised when google-genai is not importable in the venv."""
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(ImportError("No module named 'google.genai'")) is True

    def test_module_not_found_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(ModuleNotFoundError("No module named 'google'")) is True

    def test_backend_unavailable_is_eligible(self):
        """BackendUnavailableError lives in core.transport.base (transport-layer)."""
        from core.transport.policy import is_fallback_eligible
        from core.transport.base import BackendUnavailableError

        assert is_fallback_eligible(BackendUnavailableError("sdk missing")) is True


class TestNetworkErrors:
    """Transport-class network failures are eligible."""

    def test_url_error_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(URLError("dns failure")) is True

    def test_socket_timeout_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(socket.timeout("read timed out")) is True

    def test_connection_error_is_eligible(self):
        from core.transport.policy import is_fallback_eligible

        assert is_fallback_eligible(ConnectionError("connection reset")) is True


class TestUnknownErrorClass:
    """An exception we haven't taught the policy about defaults to NOT eligible.

    Failing closed is the safe default: an unknown exception is more likely to
    be a programmer bug or a missing case than a transient transport issue,
    and bubbling it up surfaces the gap immediately.
    """

    def test_unknown_exception_class_is_not_eligible(self):
        from core.transport.policy import is_fallback_eligible

        class WeirdError(Exception):
            pass

        assert is_fallback_eligible(WeirdError("unknown")) is False
