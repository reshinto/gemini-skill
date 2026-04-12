"""Model selection logic for the gemini-skill.

Selects the appropriate Gemini model based on task type, complexity,
user override, and preview preference. Uses the registry as an
advisory baseline — specialty tasks (embed, image_gen, video_gen, etc.)
route to their dedicated models regardless of complexity or preview settings.

General text/chat/code tasks use a complexity-based decision tree:
    high   → pro model
    medium → flash model (default)
    low    → flash-lite model

Dependencies: core/routing/registry.py, core/infra/errors.py
"""
from __future__ import annotations

from pathlib import Path

from core.infra.errors import CapabilityUnavailableError, ModelNotFoundError
from core.routing.registry import Registry

# Task types that route to a dedicated model via capability default_model.
# These ignore complexity and preview settings.
_SPECIALTY_TASKS = frozenset({
    "embed", "image_gen", "video_gen", "music_gen",
    "computer_use", "file_search", "maps",
})

# Complexity → model mapping for general tasks (text, multimodal, etc.)
_STABLE_MODELS = {
    "high": "gemini-2.5-pro",
    "medium": "gemini-2.5-flash",
    "low": "gemini-2.5-flash-lite",
}

_PREVIEW_MODELS = {
    "high": "gemini-3.1-pro-preview",
    "medium": "gemini-2.5-flash",
    "low": "gemini-2.5-flash-lite",
}

# Fallback when task type is unknown
_FALLBACK_MODEL = "gemini-2.5-flash"


class Router:
    """Selects models based on task type, complexity, and preferences.

    Args:
        root_dir: Project root containing registry/ directory.
        prefer_preview: If True, use preview model variants for general tasks.
    """

    def __init__(
        self,
        root_dir: Path,
        prefer_preview: bool = False,
    ) -> None:
        self._registry = Registry(root_dir=root_dir)
        self._prefer_preview = prefer_preview

    def select_model(
        self,
        task_type: str,
        complexity: str = "medium",
        user_override: str | None = None,
    ) -> str:
        """Select the best model for a given task.

        Args:
            task_type: The capability/task name (e.g., "text", "embed", "image_gen").
            complexity: Task complexity — "low", "medium", or "high".
            user_override: If set, this model is used (validated against registry).

        Returns:
            The selected model ID string.

        Raises:
            ModelNotFoundError: If user_override specifies an unknown model.
        """
        # User override always wins (but must be valid)
        if user_override is not None:
            self._registry.get_model(user_override)  # Raises if not found
            return user_override

        # Specialty tasks use their dedicated model from the capability registry
        if task_type in _SPECIALTY_TASKS:
            return self._select_specialty(task_type)

        # General tasks use complexity-based routing
        return self._select_by_complexity(complexity)

    def _select_specialty(self, task_type: str) -> str:
        """Route specialty tasks to their dedicated model."""
        try:
            cap = self._registry.get_capability(task_type)
            default_model = cap.get("default_model")
            if default_model is not None:
                return default_model
        except CapabilityUnavailableError:
            pass
        return _FALLBACK_MODEL

    def _select_by_complexity(self, complexity: str) -> str:
        """Route general tasks by complexity level and preview preference."""
        model_map = _PREVIEW_MODELS if self._prefer_preview else _STABLE_MODELS
        return model_map.get(complexity, _FALLBACK_MODEL)

    def get_pricing(self, model_id: str) -> dict[str, float]:
        """Get pricing info for a model.

        Raises:
            ModelNotFoundError: If the model is not in the registry.
        """
        return self._registry.get_model_pricing(model_id)

    def is_mutating(self, capability: str) -> bool:
        """Check if a capability requires --execute flag.

        Raises:
            CapabilityUnavailableError: If the capability is not registered.
        """
        cap = self._registry.get_capability(capability)
        return bool(cap.get("mutating", False))

    def is_privacy_sensitive(self, capability: str) -> bool:
        """Check if a capability requires explicit opt-in.

        Raises:
            CapabilityUnavailableError: If the capability is not registered.
        """
        cap = self._registry.get_capability(capability)
        return bool(cap.get("privacy_sensitive", False))
