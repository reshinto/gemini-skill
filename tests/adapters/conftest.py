"""Shared fixtures for adapter tests.

Provides mock API responses and a fake registry for adapter testing.
All adapter tests mock core.infra.client to avoid network calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_api_call():
    """Fixture that patches api_call and returns the mock for assertion."""
    with patch("core.infra.client.api_call") as mock:
        mock.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Mock response"}],
                        "role": "model",
                    },
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "cachedContentTokenCount": 0,
            },
        }
        yield mock


@pytest.fixture
def mock_stream():
    """Fixture that patches stream_generate_content."""
    with patch("core.infra.client.stream_generate_content") as mock:
        mock.return_value = iter(
            [
                {"candidates": [{"content": {"parts": [{"text": "chunk1"}]}}]},
                {"candidates": [{"content": {"parts": [{"text": "chunk2"}]}}]},
            ]
        )
        yield mock


@pytest.fixture
def mock_resolve_key():
    """Fixture that patches resolve_key to return a fake key."""
    with patch("core.infra.client.resolve_key", return_value="fake-key"):
        yield
