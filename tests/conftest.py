"""Global pytest configuration shared across the whole test suite."""

from __future__ import annotations

import warnings

from pydantic.warnings import PydanticDeprecatedSince212

_GENAI_PYDANTIC_WARNING = (
    "ignore:Using `@model_validator` with mode='after' on a classmethod is deprecated.*:"
    "pydantic.warnings.PydanticDeprecatedSince212"
)


def pytest_configure(config: object) -> None:
    """Mirror the project warning filter for direct ``pytest`` runs.

    The repository's canonical config lives in ``setup/pytest.ini``,
    but local runs like ``pytest tests/...`` do not automatically load
    that file. Register the same filter here so direct runs stay clean.
    """
    getattr(config, "addinivalue_line")("filterwarnings", _GENAI_PYDANTIC_WARNING)


# google-genai currently emits this deprecation during import on
# Pydantic 2.12+. It's third-party noise rather than a warning from
# this repository's code, so filter it for local test runs too.
warnings.filterwarnings(
    "ignore",
    message=r"Using `@model_validator` with mode='after' on a classmethod is deprecated.*",
    category=PydanticDeprecatedSince212,
)
