"""Unit tests for the module-level body translation helpers.

These helpers were extracted from ``SdkTransport`` class methods in
Phase 11.3 so that ``SdkAsyncTransport`` can call them without
instantiating a throwaway transport instance on every hot-path dispatch.
The tests here exercise the helpers in isolation — no class instance,
no live SDK client, no network.

Scope:
    - ``_build_generate_content_kwargs``
    - ``_build_embed_content_config``
    - ``_extract_video_prompt``
    - ``_wrap_collection``

Each helper is pure: no I/O, no side effects, no ``self``. That makes
them ideal for fast, deterministic unit tests.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from core.transport.sdk.transport import (
    _build_embed_content_config,
    _build_generate_content_kwargs,
    _extract_video_prompt,
    _wrap_collection,
)


class TestBuildGenerateContentKwargs:
    """_build_generate_content_kwargs folds legacy body keys into (contents, config)."""

    def test_empty_body_returns_empty_contents_and_none_config(self) -> None:
        """An empty body produces ``([], None)`` — no SDK types needed."""
        contents, config = _build_generate_content_kwargs({})
        assert contents == []
        assert config is None

    def test_contents_only_returns_none_config(self) -> None:
        """When only ``contents`` is present, no config object is built."""
        body: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": "hi"}]}]
        }
        contents, config = _build_generate_content_kwargs(body)
        assert contents == body["contents"]
        assert config is None

    def test_generation_config_triggers_config_build(self) -> None:
        """A ``generationConfig`` dict produces a ``GenerateContentConfig`` object."""
        body: dict[str, object] = {
            "contents": [],
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 100},
        }
        contents, config = _build_generate_content_kwargs(body)
        assert contents == []
        # google-genai types.GenerateContentConfig exposes temperature
        assert config is not None
        assert getattr(config, "temperature", None) == 0.5

    def test_system_instruction_sibling_merged_into_config(self) -> None:
        """``systemInstruction`` is a top-level sibling but lives on the config object."""
        body: dict[str, object] = {
            "systemInstruction": {"parts": [{"text": "Be terse"}]},
        }
        _, config = _build_generate_content_kwargs(body)
        assert config is not None
        # The sibling was promoted into the config
        assert getattr(config, "system_instruction", None) is not None

    def test_tools_sibling_merged_into_config(self) -> None:
        """The ``tools`` sibling is folded into the single config object."""
        body: dict[str, object] = {
            "tools": [{"googleSearch": {}}],
        }
        _, config = _build_generate_content_kwargs(body)
        assert config is not None
        assert getattr(config, "tools", None) is not None

    def test_cached_content_sibling_merged_into_config(self) -> None:
        """``cachedContent`` is folded in even without a generationConfig block."""
        body: dict[str, object] = {
            "cachedContent": "cachedContents/abc123",
        }
        _, config = _build_generate_content_kwargs(body)
        assert config is not None
        assert getattr(config, "cached_content", None) == "cachedContents/abc123"


class TestBuildEmbedContentConfig:
    """_build_embed_content_config extracts embed-specific fields into a config object."""

    def test_empty_body_returns_none(self) -> None:
        """No embed-specific keys → no config object (SDK accepts ``config=None``)."""
        assert _build_embed_content_config({}) is None

    def test_body_without_embed_keys_returns_none(self) -> None:
        """Irrelevant keys are ignored; only ``outputDimensionality``/``taskType`` matter."""
        body: dict[str, object] = {"contents": ["hello"], "temperature": 0.7}
        assert _build_embed_content_config(body) is None

    def test_output_dimensionality_produces_config(self) -> None:
        """Setting ``outputDimensionality`` triggers config construction."""
        body: dict[str, object] = {"outputDimensionality": 768}
        config = _build_embed_content_config(body)
        assert config is not None
        assert getattr(config, "output_dimensionality", None) == 768

    def test_task_type_produces_config(self) -> None:
        """Setting ``taskType`` alone also triggers config construction."""
        body: dict[str, object] = {"taskType": "SEMANTIC_SIMILARITY"}
        config = _build_embed_content_config(body)
        assert config is not None
        assert getattr(config, "task_type", None) == "SEMANTIC_SIMILARITY"


class TestExtractVideoPrompt:
    """_extract_video_prompt pulls the prompt string out of Veo body shapes."""

    def test_instances_shape_with_prompt_returns_prompt(self) -> None:
        """The canonical Veo shape: ``{"instances": [{"prompt": "..."}]}``."""
        body: dict[str, object] = {"instances": [{"prompt": "a cat"}]}
        assert _extract_video_prompt(body) == "a cat"

    def test_top_level_prompt_fallback(self) -> None:
        """When ``instances`` is absent, falls back to top-level ``prompt``."""
        body: dict[str, object] = {"prompt": "a dog"}
        assert _extract_video_prompt(body) == "a dog"

    def test_empty_body_returns_empty_string(self) -> None:
        """Missing prompt entirely returns an empty string (not None)."""
        assert _extract_video_prompt({}) == ""

    def test_instances_is_empty_list_falls_through(self) -> None:
        """An empty ``instances`` list falls through to top-level lookup."""
        body: dict[str, object] = {"instances": [], "prompt": "fallback"}
        assert _extract_video_prompt(body) == "fallback"

    def test_instances_first_entry_missing_prompt(self) -> None:
        """An entry without a ``prompt`` key yields ``""`` (top-level is also absent)."""
        body: dict[str, object] = {"instances": [{"other": "value"}]}
        assert _extract_video_prompt(body) == ""

    def test_instances_entry_not_dict(self) -> None:
        """A non-dict entry inside instances is skipped gracefully."""
        body: dict[str, object] = {"instances": ["not-a-dict"]}
        assert _extract_video_prompt(body) == ""

    def test_instances_prompt_not_str(self) -> None:
        """A non-string prompt inside instances yields empty string."""
        body: dict[str, object] = {"instances": [{"prompt": 42}]}
        assert _extract_video_prompt(body) == ""

    def test_top_level_prompt_not_str(self) -> None:
        """A non-string top-level prompt yields empty string."""
        body: dict[str, object] = {"prompt": [1, 2, 3]}
        assert _extract_video_prompt(body) == ""


class TestWrapCollection:
    """_wrap_collection normalizes iterable SDK collection results."""

    def test_non_iterable_returns_empty_list(self) -> None:
        """Passing a non-iterable returns ``{key: []}`` without raising."""
        envelope = _wrap_collection("files", object())
        assert envelope == {"files": []}

    def test_empty_list_returns_empty_list(self) -> None:
        """An empty iterable produces an empty list."""
        envelope = _wrap_collection("files", [])
        assert envelope == {"files": []}

    def test_single_item_wrapped_via_normalize(self) -> None:
        """Each item is passed through ``sdk_response_to_rest_envelope``."""
        # Build a mock pydantic-like item with .model_dump
        fake_item = MagicMock()
        fake_item.model_dump.return_value = {"name": "files/abc", "mimeType": "text/plain"}
        envelope = _wrap_collection("files", [fake_item])
        assert "files" in envelope
        files_list = cast(list[dict[str, object]], envelope["files"])
        assert len(files_list) == 1
        assert files_list[0]["name"] == "files/abc"

    def test_multiple_items_preserved_in_order(self) -> None:
        """Multiple items are normalized in order, no reordering."""
        first_item = MagicMock()
        first_item.model_dump.return_value = {"name": "files/1"}
        second_item = MagicMock()
        second_item.model_dump.return_value = {"name": "files/2"}
        envelope = _wrap_collection("files", [first_item, second_item])
        files_list = cast(list[dict[str, object]], envelope["files"])
        assert [entry["name"] for entry in files_list] == ["files/1", "files/2"]

    def test_generator_accepted(self) -> None:
        """Any iterable (not just list) is accepted — generators work too."""

        def generator() -> object:
            fake = MagicMock()
            fake.model_dump.return_value = {"name": "files/gen"}
            yield fake

        envelope = _wrap_collection("files", generator())
        files_list = cast(list[dict[str, object]], envelope["files"])
        assert len(files_list) == 1

    def test_custom_key_name(self) -> None:
        """The ``key`` argument determines the envelope key, not hardcoded to 'files'."""
        envelope = _wrap_collection("cachedContents", [])
        assert envelope == {"cachedContents": []}


class TestClassDelegatesStillWork:
    """SdkTransport class methods still work as delegators (backward compat)."""

    def test_sdk_transport_class_methods_delegate(self) -> None:
        """Existing callers that hold an SdkTransport instance keep working."""
        from core.transport.sdk.transport import SdkTransport

        instance = SdkTransport()
        body: dict[str, object] = {"contents": [{"role": "user", "parts": [{"text": "x"}]}]}
        contents, config = instance._build_generate_content_kwargs(body)
        assert contents == body["contents"]
        assert config is None

    def test_sdk_transport_embed_delegates(self) -> None:
        """Embed delegator returns same result as module-level function."""
        from core.transport.sdk.transport import SdkTransport

        instance = SdkTransport()
        assert instance._build_embed_content_config({}) is None

    def test_sdk_transport_video_prompt_delegates(self) -> None:
        """Video prompt delegator returns same result as module-level function."""
        from core.transport.sdk.transport import SdkTransport

        instance = SdkTransport()
        assert instance._extract_video_prompt({"prompt": "x"}) == "x"

    def test_sdk_transport_wrap_collection_delegates(self) -> None:
        """Wrap-collection delegator returns same result as module-level function."""
        from core.transport.sdk.transport import SdkTransport

        instance = SdkTransport()
        envelope = instance._wrap_collection("files", [])
        assert envelope == {"files": []}
