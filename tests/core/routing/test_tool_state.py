"""Tests for core/routing/tool_state.py — tool state preservation.

Verifies that id, tool_type, thought_signature, and unknown fields
are preserved exactly as returned by the API in multi-turn tool loops.
"""
from __future__ import annotations

import pytest


class TestExtractToolState:
    """extract_tool_state() must find and preserve tool-state parts."""

    def test_extracts_function_call_part(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {"text": "Let me run that code."},
            {
                "functionCall": {"name": "run_code", "args": {"code": "1+1"}},
                "id": "call-123",
                "tool_type": "function_calling",
            },
        ]
        result = extract_tool_state(parts)
        assert len(result) == 1
        assert result[0]["id"] == "call-123"

    def test_extracts_executable_code_part(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {
                "executableCode": {"code": "print(1)", "language": "PYTHON"},
                "id": "exec-456",
                "tool_type": "code_execution",
            },
        ]
        result = extract_tool_state(parts)
        assert len(result) == 1
        assert result[0]["tool_type"] == "code_execution"

    def test_preserves_thought_signature(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {
                "functionCall": {"name": "search", "args": {}},
                "id": "call-789",
                "thought_signature": "sig-abc-def",
            },
        ]
        result = extract_tool_state(parts)
        assert result[0]["thought_signature"] == "sig-abc-def"

    def test_preserves_unknown_fields(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {
                "functionCall": {"name": "f", "args": {}},
                "id": "c1",
                "future_field": {"nested": True},
                "another_new_field": 42,
            },
        ]
        result = extract_tool_state(parts)
        assert result[0]["future_field"] == {"nested": True}
        assert result[0]["another_new_field"] == 42

    def test_skips_text_only_parts(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {"text": "Just some text."},
            {"text": "More text."},
        ]
        result = extract_tool_state(parts)
        assert result == []

    def test_skips_inline_data_parts(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {"inlineData": {"mimeType": "image/png", "data": "base64data"}},
        ]
        result = extract_tool_state(parts)
        assert result == []

    def test_extracts_code_execution_result(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {
                "codeExecutionResult": {"output": "2", "outcome": "OUTCOME_OK"},
                "id": "result-1",
            },
        ]
        result = extract_tool_state(parts)
        assert len(result) == 1

    def test_extracts_function_response(self):
        from core.routing.tool_state import extract_tool_state

        parts = [
            {
                "functionResponse": {"name": "search", "response": {"results": []}},
                "id": "resp-1",
            },
        ]
        result = extract_tool_state(parts)
        assert len(result) == 1

    def test_empty_parts_returns_empty(self):
        from core.routing.tool_state import extract_tool_state
        assert extract_tool_state([]) == []

    def test_round_trip_preserves_all_data(self):
        from core.routing.tool_state import extract_tool_state

        original = {
            "functionCall": {"name": "f", "args": {"x": 1}},
            "id": "call-1",
            "tool_type": "function_calling",
            "thought_signature": "sig-123",
            "deeply_nested": {"a": {"b": {"c": [1, 2, 3]}}},
        }
        result = extract_tool_state([original])
        assert result[0] == original


class TestInjectToolState:
    """inject_tool_state() must merge preserved parts into request contents."""

    def test_appends_preserved_parts(self):
        from core.routing.tool_state import inject_tool_state

        contents = [
            {"role": "user", "parts": [{"text": "hello"}]},
            {"role": "model", "parts": [{"text": "hi"}]},
        ]
        preserved = [
            {"functionCall": {"name": "f", "args": {}}, "id": "c1"},
        ]
        result = inject_tool_state(contents, preserved)
        # Last model turn should have the preserved parts appended
        last_model = result[-1]
        assert any("functionCall" in p for p in last_model["parts"])

    def test_creates_model_turn_if_needed(self):
        from core.routing.tool_state import inject_tool_state

        contents = [
            {"role": "user", "parts": [{"text": "hello"}]},
        ]
        preserved = [
            {"functionCall": {"name": "f", "args": {}}, "id": "c1"},
        ]
        result = inject_tool_state(contents, preserved)
        assert result[-1]["role"] == "model"

    def test_empty_preserved_returns_unchanged(self):
        from core.routing.tool_state import inject_tool_state

        contents = [{"role": "user", "parts": [{"text": "hi"}]}]
        result = inject_tool_state(contents, [])
        assert result == contents

    def test_does_not_modify_original(self):
        from core.routing.tool_state import inject_tool_state

        contents = [
            {"role": "model", "parts": [{"text": "ok"}]},
        ]
        original_len = len(contents[0]["parts"])
        preserved = [{"functionCall": {"name": "f", "args": {}}, "id": "c1"}]
        inject_tool_state(contents, preserved)
        # Original should be unchanged (deep copy)
        assert len(contents[0]["parts"]) == original_len


class TestHasToolState:
    """has_tool_state() must detect tool-bearing parts."""

    def test_function_call_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"functionCall": {"name": "f"}}) is True

    def test_executable_code_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"executableCode": {"code": "x"}}) is True

    def test_function_response_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"functionResponse": {"name": "f"}}) is True

    def test_code_execution_result_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"codeExecutionResult": {"output": "x"}}) is True

    def test_text_only_not_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"text": "hello"}) is False

    def test_inline_data_not_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({"inlineData": {}}) is False

    def test_empty_part_not_detected(self):
        from core.routing.tool_state import has_tool_state
        assert has_tool_state({}) is False
