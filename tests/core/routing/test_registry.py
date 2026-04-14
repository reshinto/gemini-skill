"""Tests for core/routing/registry.py — JSON capability/model registry loader.

Verifies loading models and capabilities from JSON, lookup functions,
listing, filtering, pricing access, and error handling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_models(tmp_path: Path, models: dict) -> Path:
    """Helper to write a models.json file."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(exist_ok=True)
    (registry_dir / "models.json").write_text(json.dumps({"models": models}))
    return tmp_path


def _write_capabilities(tmp_path: Path, capabilities: dict) -> Path:
    """Helper to write a capabilities.json file."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(exist_ok=True)
    (registry_dir / "capabilities.json").write_text(json.dumps({"capabilities": capabilities}))
    return tmp_path


def _sample_model():
    return {
        "display_name": "Test Model",
        "description": "A test model",
        "status": "stable",
        "api_version": "v1beta",
        "capabilities": ["text", "streaming"],
        "pricing": {
            "input_per_1m": 0.15,
            "output_per_1m": 0.60,
            "cached_per_1m": 0.0375,
        },
    }


def _sample_capability():
    return {
        "command": "text",
        "adapter": "adapters/generation/text.py",
        "status": "supported",
        "api_version": "v1beta",
        "default_model": "test-model",
        "mutating": False,
        "privacy_sensitive": False,
        "preview": False,
        "reference": "reference/text.md",
        "doc_url": "https://example.com/docs",
    }


class TestLoadModels:
    """Registry must load model data from JSON."""

    def test_loads_models_from_json(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        models = reg.list_models()
        assert "test-model" in models

    def test_returns_empty_when_file_missing(self, tmp_path):
        from core.routing.registry import Registry

        reg = Registry(root_dir=tmp_path)
        assert reg.list_models() == []

    def test_returns_empty_on_invalid_json(self, tmp_path):
        from core.routing.registry import Registry

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "models.json").write_text("bad json {{{")
        reg = Registry(root_dir=tmp_path)
        assert reg.list_models() == []

    def test_multiple_models(self, tmp_path):
        from core.routing.registry import Registry

        models = {
            "model-a": _sample_model(),
            "model-b": _sample_model(),
        }
        _write_models(tmp_path, models)
        reg = Registry(root_dir=tmp_path)
        assert len(reg.list_models()) == 2


class TestGetModel:
    """Registry.get_model() must return model info or raise."""

    def test_get_existing_model(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        model = reg.get_model("test-model")
        assert model["display_name"] == "Test Model"
        assert model["pricing"]["input_per_1m"] == 0.15

    def test_get_missing_model_raises(self, tmp_path):
        from core.routing.registry import Registry
        from core.infra.errors import ModelNotFoundError

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        with pytest.raises(ModelNotFoundError, match="nonexistent"):
            reg.get_model("nonexistent")

    def test_get_model_includes_id(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        model = reg.get_model("test-model")
        assert model["id"] == "test-model"


class TestGetModelPricing:
    """Registry.get_model_pricing() must return pricing dict."""

    def test_returns_pricing(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        pricing = reg.get_model_pricing("test-model")
        assert pricing["input_per_1m"] == 0.15
        assert pricing["output_per_1m"] == 0.60
        assert pricing["cached_per_1m"] == 0.0375

    def test_raises_for_missing_model(self, tmp_path):
        from core.routing.registry import Registry
        from core.infra.errors import ModelNotFoundError

        _write_models(tmp_path, {})
        reg = Registry(root_dir=tmp_path)
        with pytest.raises(ModelNotFoundError):
            reg.get_model_pricing("nonexistent")


class TestLoadCapabilities:
    """Registry must load capability data from JSON."""

    def test_loads_capabilities_from_json(self, tmp_path):
        from core.routing.registry import Registry

        _write_capabilities(tmp_path, {"text": _sample_capability()})
        reg = Registry(root_dir=tmp_path)
        caps = reg.list_capabilities()
        assert "text" in caps

    def test_returns_empty_when_file_missing(self, tmp_path):
        from core.routing.registry import Registry

        reg = Registry(root_dir=tmp_path)
        assert reg.list_capabilities() == []

    def test_returns_empty_on_invalid_json(self, tmp_path):
        from core.routing.registry import Registry

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "capabilities.json").write_text("bad {")
        reg = Registry(root_dir=tmp_path)
        assert reg.list_capabilities() == []


class TestGetCapability:
    """Registry.get_capability() must return capability info or raise."""

    def test_get_existing_capability(self, tmp_path):
        from core.routing.registry import Registry

        _write_capabilities(tmp_path, {"text": _sample_capability()})
        reg = Registry(root_dir=tmp_path)
        cap = reg.get_capability("text")
        assert cap["command"] == "text"
        assert cap["adapter"] == "adapters/generation/text.py"

    def test_get_missing_capability_raises(self, tmp_path):
        from core.routing.registry import Registry
        from core.infra.errors import CapabilityUnavailableError

        _write_capabilities(tmp_path, {"text": _sample_capability()})
        reg = Registry(root_dir=tmp_path)
        with pytest.raises(CapabilityUnavailableError, match="nonexistent"):
            reg.get_capability("nonexistent")


class TestFilterModels:
    """Registry must filter models by capability and status."""

    def test_filter_by_capability(self, tmp_path):
        from core.routing.registry import Registry

        m1 = _sample_model()
        m1["capabilities"] = ["text", "streaming"]
        m2 = _sample_model()
        m2["capabilities"] = ["embed"]
        _write_models(tmp_path, {"m1": m1, "m2": m2})
        reg = Registry(root_dir=tmp_path)
        result = reg.models_for_capability("text")
        assert "m1" in result
        assert "m2" not in result

    def test_filter_by_status(self, tmp_path):
        from core.routing.registry import Registry

        m1 = _sample_model()
        m1["status"] = "stable"
        m2 = _sample_model()
        m2["status"] = "preview"
        _write_models(tmp_path, {"m1": m1, "m2": m2})
        reg = Registry(root_dir=tmp_path)
        stable = reg.models_by_status("stable")
        assert "m1" in stable
        assert "m2" not in stable

    def test_filter_capability_no_matches(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"m1": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        assert reg.models_for_capability("nonexistent") == []

    def test_filter_status_no_matches(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"m1": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        assert reg.models_by_status("deprecated") == []


class TestCapabilityProperties:
    """Capability properties must be queryable."""

    def test_is_mutating(self, tmp_path):
        from core.routing.registry import Registry

        cap = _sample_capability()
        cap["mutating"] = True
        _write_capabilities(tmp_path, {"files": cap})
        reg = Registry(root_dir=tmp_path)
        assert reg.get_capability("files")["mutating"] is True

    def test_is_privacy_sensitive(self, tmp_path):
        from core.routing.registry import Registry

        cap = _sample_capability()
        cap["privacy_sensitive"] = True
        _write_capabilities(tmp_path, {"search": cap})
        reg = Registry(root_dir=tmp_path)
        assert reg.get_capability("search")["privacy_sensitive"] is True

    def test_mutating_actions_exposed(self, tmp_path):
        from core.routing.registry import Registry

        cap = _sample_capability()
        cap["mutating"] = True
        cap["mutating_actions"] = ["create", "delete"]
        _write_capabilities(tmp_path, {"cache": cap})
        reg = Registry(root_dir=tmp_path)
        assert reg.get_capability("cache")["mutating_actions"] == ["create", "delete"]

    def test_is_preview(self, tmp_path):
        from core.routing.registry import Registry

        cap = _sample_capability()
        cap["preview"] = True
        _write_capabilities(tmp_path, {"image_gen": cap})
        reg = Registry(root_dir=tmp_path)
        assert reg.get_capability("image_gen")["preview"] is True


class TestEdgeCases:
    """Cover edge cases found during review."""

    def test_null_default_model(self, tmp_path):
        from core.routing.registry import Registry

        cap = _sample_capability()
        cap["default_model"] = None
        _write_capabilities(tmp_path, {"streaming": cap})
        reg = Registry(root_dir=tmp_path)
        assert reg.get_capability("streaming")["default_model"] is None

    def test_get_model_returns_deep_copy(self, tmp_path):
        from core.routing.registry import Registry

        _write_models(tmp_path, {"test-model": _sample_model()})
        reg = Registry(root_dir=tmp_path)
        model = reg.get_model("test-model")
        model["pricing"]["input_per_1m"] = 999.0
        # Internal state should be unaffected
        model2 = reg.get_model("test-model")
        assert model2["pricing"]["input_per_1m"] == 0.15

    def test_get_capability_returns_deep_copy(self, tmp_path):
        from core.routing.registry import Registry

        _write_capabilities(tmp_path, {"text": _sample_capability()})
        reg = Registry(root_dir=tmp_path)
        cap = reg.get_capability("text")
        cap["command"] = "mutated"
        cap2 = reg.get_capability("text")
        assert cap2["command"] == "text"

    def test_model_missing_pricing_raises(self, tmp_path):
        from core.routing.registry import Registry
        from core.infra.errors import ModelNotFoundError

        model = _sample_model()
        del model["pricing"]
        _write_models(tmp_path, {"no-pricing": model})
        reg = Registry(root_dir=tmp_path)
        with pytest.raises(ModelNotFoundError, match="no pricing"):
            reg.get_model_pricing("no-pricing")

    def test_model_agnostic_capabilities_return_empty_models(self):
        """files, batch, token_count are model-agnostic (no model lists them)."""
        from core.routing.registry import Registry

        root = Path(__file__).parent.parent.parent.parent
        reg = Registry(root_dir=root)
        # These capabilities exist but are handled by their adapters directly
        for cap_name in ["files", "batch"]:
            cap = reg.get_capability(cap_name)
            assert cap["default_model"] is None
            # No model advertises these — adapters handle routing
            assert reg.models_for_capability(cap_name) == []


class TestRegistryWithRealFiles:
    """Registry must load from the actual registry/ directory."""

    def test_loads_real_models_json(self):
        from core.routing.registry import Registry

        root = Path(__file__).parent.parent.parent.parent
        reg = Registry(root_dir=root)
        models = reg.list_models()
        assert len(models) > 0
        assert "gemini-2.5-flash" in models

    def test_loads_real_capabilities_json(self):
        from core.routing.registry import Registry

        root = Path(__file__).parent.parent.parent.parent
        reg = Registry(root_dir=root)
        caps = reg.list_capabilities()
        assert len(caps) > 0
        assert "text" in caps

    def test_real_model_has_pricing(self):
        from core.routing.registry import Registry

        root = Path(__file__).parent.parent.parent.parent
        reg = Registry(root_dir=root)
        pricing = reg.get_model_pricing("gemini-2.5-flash")
        assert pricing["input_per_1m"] > 0

    def test_real_capability_has_adapter(self):
        from core.routing.registry import Registry

        root = Path(__file__).parent.parent.parent.parent
        reg = Registry(root_dir=root)
        cap = reg.get_capability("text")
        assert "adapter" in cap
