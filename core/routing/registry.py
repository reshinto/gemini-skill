"""JSON capability and model registry loader.

Loads model catalog (registry/models.json) and capability manifest
(registry/capabilities.json) from the project root. Provides lookup,
listing, and filtering functions.

The registry is an advisory offline baseline — preview adapters probe
the live API at runtime. This module provides the static reference data.

Dependencies: core/infra/errors.py (ModelNotFoundError, CapabilityUnavailableError)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from core.infra.errors import CapabilityUnavailableError, ModelNotFoundError


class Registry:
    """Loads and queries the model and capability registries.

    Reads JSON files once at construction. Provides lookup by ID,
    listing, filtering by capability or status, and pricing access.
    All returned dicts are deep copies to prevent caller mutation
    of the internal cache.

    Args:
        root_dir: Project root directory containing registry/ subdirectory.
    """

    def __init__(self, root_dir: Path) -> None:
        self._root = Path(root_dir)
        self._models = self._load_json("models.json", "models")
        self._capabilities = self._load_json("capabilities.json", "capabilities")

    def _load_json(self, filename: str, key: str) -> dict[str, Any]:
        """Load a registry JSON file and extract the top-level key.

        Returns empty dict on missing file, invalid JSON, or missing key.
        """
        path = self._root / "registry" / filename
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and key in data:
                return data[key]
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    # --- Model operations ---

    def list_models(self) -> list[str]:
        """Return all registered model IDs."""
        return list(self._models.keys())

    def get_model(self, model_id: str) -> dict[str, Any]:
        """Get full model info by ID.

        Returns a deep copy of the model dict with an added 'id' field.

        Raises:
            ModelNotFoundError: If the model ID is not in the registry.
        """
        if model_id not in self._models:
            raise ModelNotFoundError(f"Model not found in registry: {model_id}")
        model = copy.deepcopy(self._models[model_id])
        model["id"] = model_id
        return model

    def get_model_pricing(self, model_id: str) -> dict[str, float]:
        """Get pricing info for a model.

        Returns dict with input_per_1m, output_per_1m, cached_per_1m.

        Raises:
            ModelNotFoundError: If the model ID or pricing is not in the registry.
        """
        model = self.get_model(model_id)
        if "pricing" not in model:
            raise ModelNotFoundError(
                f"Model {model_id} has no pricing data in the registry"
            )
        return model["pricing"]

    def models_for_capability(self, capability: str) -> list[str]:
        """Return model IDs that support a given capability."""
        return [
            mid for mid, info in self._models.items()
            if capability in info.get("capabilities", [])
        ]

    def models_by_status(self, status: str) -> list[str]:
        """Return model IDs with a given status (stable, preview, etc.)."""
        return [
            mid for mid, info in self._models.items()
            if info.get("status") == status
        ]

    # --- Capability operations ---

    def list_capabilities(self) -> list[str]:
        """Return all registered capability names."""
        return list(self._capabilities.keys())

    def get_capability(self, name: str) -> dict[str, Any]:
        """Get full capability info by name.

        Returns a deep copy of the capability dict.

        Raises:
            CapabilityUnavailableError: If the capability is not registered.
        """
        if name not in self._capabilities:
            raise CapabilityUnavailableError(
                f"Capability not found in registry: {name}"
            )
        return copy.deepcopy(self._capabilities[name])
