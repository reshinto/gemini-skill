"""Tests for core/routing/router.py — model selection logic.

Verifies task-type routing, complexity levels, user overrides,
preview model preferences, and fallback behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_registry(tmp_path: Path) -> Path:
    """Create a minimal registry for testing."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "models.json").write_text(json.dumps({
        "models": {
            "gemini-2.5-flash": {
                "display_name": "Flash",
                "status": "stable",
                "api_version": "v1beta",
                "capabilities": ["text", "multimodal", "structured", "streaming",
                                 "function_calling", "code_exec", "search", "cache", "token_count"],
                "pricing": {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375},
            },
            "gemini-2.5-pro": {
                "display_name": "Pro",
                "status": "stable",
                "api_version": "v1beta",
                "capabilities": ["text", "multimodal", "structured", "streaming",
                                 "function_calling", "code_exec", "search", "cache", "token_count"],
                "pricing": {"input_per_1m": 1.25, "output_per_1m": 10.00, "cached_per_1m": 0.3125},
            },
            "gemini-2.5-flash-lite": {
                "display_name": "Flash Lite",
                "status": "stable",
                "api_version": "v1beta",
                "capabilities": ["text", "multimodal", "streaming", "file_search", "token_count"],
                "pricing": {"input_per_1m": 0.075, "output_per_1m": 0.30, "cached_per_1m": 0.01875},
            },
            "gemini-embedding-2-preview": {
                "display_name": "Embedding",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["embed"],
                "pricing": {"input_per_1m": 0.0, "output_per_1m": 0.0, "cached_per_1m": 0.0},
            },
            "gemini-3-flash-preview": {
                "display_name": "3 Flash Preview",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["text", "multimodal", "structured", "function_calling",
                                 "code_exec", "search", "maps", "file_search", "computer_use", "token_count"],
                "pricing": {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375},
            },
            "gemini-3.1-flash-image-preview": {
                "display_name": "Image Gen",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["image_gen"],
                "pricing": {"input_per_1m": 0.15, "output_per_1m": 0.60, "cached_per_1m": 0.0375},
            },
            "gemini-3.1-pro-preview": {
                "display_name": "3.1 Pro Preview",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["text", "multimodal", "structured", "function_calling",
                                 "code_exec", "search", "token_count"],
                "pricing": {"input_per_1m": 1.25, "output_per_1m": 10.00, "cached_per_1m": 0.3125},
            },
            "veo-3.1-generate-preview": {
                "display_name": "Veo",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["video_gen"],
                "pricing": {"input_per_1m": 0.0, "output_per_1m": 0.0, "cached_per_1m": 0.0},
            },
            "lyria-3-clip-preview": {
                "display_name": "Lyria",
                "status": "preview",
                "api_version": "v1beta",
                "capabilities": ["music_gen"],
                "pricing": {"input_per_1m": 0.0, "output_per_1m": 0.0, "cached_per_1m": 0.0},
            },
        }
    }))
    (registry_dir / "capabilities.json").write_text(json.dumps({
        "capabilities": {
            "text": {"command": "text", "default_model": "gemini-2.5-flash"},
            "embed": {"command": "embed", "default_model": "gemini-embedding-2-preview"},
            "image_gen": {"command": "image_gen", "default_model": "gemini-3.1-flash-image-preview"},
            "video_gen": {"command": "video_gen", "default_model": "veo-3.1-generate-preview"},
            "music_gen": {"command": "music_gen", "default_model": "lyria-3-clip-preview"},
            "computer_use": {"command": "computer_use", "default_model": "gemini-3-flash-preview"},
            "maps": {"command": "maps", "default_model": None},
            "file_search": {"command": "file_search", "default_model": "gemini-2.5-flash-lite"},
        }
    }))
    return tmp_path


class TestSelectModelDefaults:
    """select_model() must pick sensible defaults by task type."""

    def test_text_defaults_to_flash(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("text") == "gemini-2.5-flash"

    def test_embed_routes_to_embedding_model(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("embed") == "gemini-embedding-2-preview"

    def test_image_gen_routes_to_image_model(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("image_gen") == "gemini-3.1-flash-image-preview"

    def test_video_gen_routes_to_veo(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("video_gen") == "veo-3.1-generate-preview"

    def test_music_gen_routes_to_lyria(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("music_gen") == "lyria-3-clip-preview"

    def test_computer_use_routes_to_3_flash(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("computer_use") == "gemini-3-flash-preview"

    def test_file_search_routes_to_flash_lite(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("file_search") == "gemini-2.5-flash-lite"


class TestSelectModelComplexity:
    """select_model() must adjust for complexity level."""

    def test_high_complexity_selects_pro(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("text", complexity="high") == "gemini-2.5-pro"

    def test_medium_complexity_selects_flash(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("text", complexity="medium") == "gemini-2.5-flash"

    def test_low_complexity_selects_lite(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        assert router.select_model("text", complexity="low") == "gemini-2.5-flash-lite"

    def test_default_complexity_is_medium(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        # No complexity arg = medium = flash
        assert router.select_model("text") == "gemini-2.5-flash"


class TestSelectModelUserOverride:
    """User override must always win."""

    def test_user_override_wins(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        result = router.select_model("text", user_override="gemini-2.5-pro")
        assert result == "gemini-2.5-pro"

    def test_user_override_validated(self, tmp_path):
        from core.routing.router import Router
        from core.infra.errors import ModelNotFoundError
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        with pytest.raises(ModelNotFoundError, match="nonexistent"):
            router.select_model("text", user_override="nonexistent")

    def test_user_override_ignores_complexity(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        result = router.select_model("text", complexity="low", user_override="gemini-2.5-pro")
        assert result == "gemini-2.5-pro"


class TestSelectModelPreviewPreference:
    """prefer_preview_models must route to preview variants."""

    def test_prefer_preview_selects_31_pro(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root, prefer_preview=True)
        result = router.select_model("text", complexity="high")
        assert result == "gemini-3.1-pro-preview"

    def test_prefer_preview_flash_stays_flash(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root, prefer_preview=True)
        # Medium complexity — still uses flash (no preview flash variant for text)
        result = router.select_model("text", complexity="medium")
        assert result == "gemini-2.5-flash"

    def test_no_preview_by_default(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        result = router.select_model("text", complexity="high")
        assert result == "gemini-2.5-pro"

    def test_specialty_tasks_ignore_preview_flag(self, tmp_path):
        """Specialty tasks (embed, image_gen, etc.) always use their dedicated model."""
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root, prefer_preview=True)
        assert router.select_model("embed") == "gemini-embedding-2-preview"
        assert router.select_model("image_gen") == "gemini-3.1-flash-image-preview"
        assert router.select_model("video_gen") == "veo-3.1-generate-preview"


class TestSelectModelSpecialtyFallbacks:
    """Specialty routing must fall back gracefully."""

    def test_specialty_with_null_default_model_falls_back(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        # maps has default_model: null
        result = router.select_model("maps")
        assert result == "gemini-2.5-flash"

    def test_specialty_missing_from_registry_falls_back(self, tmp_path):
        from core.routing.router import Router
        # Create registry without the needed capability
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(exist_ok=True)
        (registry_dir / "models.json").write_text(json.dumps({"models": {}}))
        (registry_dir / "capabilities.json").write_text(json.dumps({"capabilities": {}}))
        router = Router(root_dir=tmp_path)
        # file_search is in _SPECIALTY_TASKS but not in this registry
        result = router.select_model("file_search")
        assert result == "gemini-2.5-flash"


class TestSelectModelUnknownTaskType:
    """Unknown task types must fall back gracefully."""

    def test_unknown_task_falls_back_to_flash(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        result = router.select_model("unknown_task")
        assert result == "gemini-2.5-flash"


class TestRouterGetPricing:
    """Router.get_pricing() must return pricing for a model."""

    def test_returns_pricing_dict(self, tmp_path):
        from core.routing.router import Router
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        pricing = router.get_pricing("gemini-2.5-flash")
        assert pricing["input_per_1m"] == 0.15

    def test_raises_for_unknown_model(self, tmp_path):
        from core.routing.router import Router
        from core.infra.errors import ModelNotFoundError
        root = _make_registry(tmp_path)
        router = Router(root_dir=root)
        with pytest.raises(ModelNotFoundError):
            router.get_pricing("nonexistent")


class TestRouterCapabilityInfo:
    """Router must provide capability metadata."""

    def test_is_mutating(self, tmp_path):
        from core.routing.router import Router
        # Need capabilities with mutating flag
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(exist_ok=True)
        (registry_dir / "models.json").write_text(json.dumps({"models": {}}))
        (registry_dir / "capabilities.json").write_text(json.dumps({
            "capabilities": {
                "files": {"command": "files", "mutating": True, "privacy_sensitive": False},
                "text": {"command": "text", "mutating": False, "privacy_sensitive": False},
            }
        }))
        router = Router(root_dir=tmp_path)
        assert router.is_mutating("files") is True
        assert router.is_mutating("text") is False

    def test_is_privacy_sensitive(self, tmp_path):
        from core.routing.router import Router
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(exist_ok=True)
        (registry_dir / "models.json").write_text(json.dumps({"models": {}}))
        (registry_dir / "capabilities.json").write_text(json.dumps({
            "capabilities": {
                "search": {"command": "search", "mutating": False, "privacy_sensitive": True},
                "text": {"command": "text", "mutating": False, "privacy_sensitive": False},
            }
        }))
        router = Router(root_dir=tmp_path)
        assert router.is_privacy_sensitive("search") is True
        assert router.is_privacy_sensitive("text") is False

    def test_unknown_capability_raises(self, tmp_path):
        from core.routing.router import Router
        from core.infra.errors import CapabilityUnavailableError
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(exist_ok=True)
        (registry_dir / "models.json").write_text(json.dumps({"models": {}}))
        (registry_dir / "capabilities.json").write_text(json.dumps({"capabilities": {}}))
        router = Router(root_dir=tmp_path)
        with pytest.raises(CapabilityUnavailableError):
            router.is_mutating("nonexistent")
