"""Tests for core/infra/errors.py — error types and retry classification.

Tests the fail-closed error hierarchy and the retry policy that determines
whether a failed API call should be retried, treated as a timeout, or
immediately surfaced to the user.
"""
from __future__ import annotations

import pytest


class TestGeminiSkillError:
    """Base error must be catchable and carry a user-friendly message."""

    def test_base_error_is_exception(self):
        from core.infra.errors import GeminiSkillError
        assert issubclass(GeminiSkillError, Exception)

    def test_base_error_message(self):
        from core.infra.errors import GeminiSkillError
        err = GeminiSkillError("something went wrong")
        assert str(err) == "something went wrong"


class TestErrorSubclasses:
    """Each error subclass must inherit from GeminiSkillError."""

    @pytest.mark.parametrize("cls_name", [
        "AuthError",
        "ModelNotFoundError",
        "CapabilityUnavailableError",
        "CostLimitError",
        "APIError",
    ])
    def test_subclass_inherits_base(self, cls_name):
        import core.infra.errors as mod
        cls = getattr(mod, cls_name)
        from core.infra.errors import GeminiSkillError
        assert issubclass(cls, GeminiSkillError)

    def test_api_error_carries_status_code(self):
        from core.infra.errors import APIError
        err = APIError("bad request", status_code=400)
        assert err.status_code == 400
        assert "bad request" in str(err)

    def test_api_error_default_status_code_is_none(self):
        from core.infra.errors import APIError
        err = APIError("unknown error")
        assert err.status_code is None

    def test_cost_limit_error_carries_amounts(self):
        from core.infra.errors import CostLimitError
        err = CostLimitError("limit exceeded", current=4.50, limit=5.00)
        assert err.current == 4.50
        assert err.limit == 5.00


class TestRetryClassification:
    """classify_retry() must return the correct action for each HTTP status."""

    def test_429_is_retry(self):
        from core.infra.errors import classify_retry
        assert classify_retry(429) == "retry"

    def test_503_is_retry(self):
        from core.infra.errors import classify_retry
        assert classify_retry(503) == "retry"

    def test_504_is_timeout(self):
        from core.infra.errors import classify_retry
        assert classify_retry(504) == "timeout"

    @pytest.mark.parametrize("code", [400, 401, 403, 404])
    def test_client_errors_are_no_retry(self, code):
        from core.infra.errors import classify_retry
        assert classify_retry(code) == "no_retry"

    def test_500_is_retry(self):
        from core.infra.errors import classify_retry
        assert classify_retry(500) == "retry"

    def test_unknown_5xx_is_retry(self):
        from core.infra.errors import classify_retry
        assert classify_retry(502) == "retry"

    def test_unknown_4xx_is_no_retry(self):
        from core.infra.errors import classify_retry
        assert classify_retry(422) == "no_retry"


class TestFormatUserError:
    """format_user_error() produces clean messages without tracebacks."""

    def test_format_includes_error_type(self):
        from core.infra.errors import AuthError, format_user_error
        err = AuthError("API key not set")
        msg = format_user_error(err)
        assert "[ERROR]" in msg
        assert "API key not set" in msg

    def test_format_does_not_include_traceback(self):
        from core.infra.errors import APIError, format_user_error
        err = APIError("server error", status_code=500)
        msg = format_user_error(err)
        assert "Traceback" not in msg
        assert "File " not in msg
