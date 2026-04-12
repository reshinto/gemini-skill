"""Tests for core/cli/health_main.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestHealthMain:
    def test_all_checks_pass(self, capsys):
        from core.cli.health_main import main
        with patch("core.auth.auth.resolve_key", return_value="fake-key"), \
             patch("core.infra.client.api_call", return_value={"models": [{"name": "m1"}]}):
            main([])
        output = capsys.readouterr().out
        assert "[OK] API key resolved" in output
        assert "[OK] API reachable" in output
        assert "All checks passed" in output

    def test_auth_failure(self, capsys):
        from core.cli.health_main import main
        from core.infra.errors import AuthError
        with patch("core.auth.auth.resolve_key", side_effect=AuthError("no key")):
            main([])
        output = capsys.readouterr().out
        assert "[FAIL] API key" in output
        assert "All checks passed" not in output

    def test_api_connectivity_failure(self, capsys):
        from core.cli.health_main import main
        with patch("core.auth.auth.resolve_key", return_value="fake-key"), \
             patch("core.infra.client.api_call", side_effect=Exception("network down")):
            main([])
        output = capsys.readouterr().out
        assert "[FAIL] API connectivity" in output
        assert "All checks passed" not in output
