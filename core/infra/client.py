"""Backward-compatibility shim — re-exports the dual-backend transport facade.

Every adapter in ``adapters/`` (and a handful of CLI / auth helpers) imports
``api_call`` / ``stream_generate_content`` / ``upload_file`` from this module
path. The Phase 3 dual-backend refactor lands a public facade at
``core/transport/__init__.py`` that owns the primary/fallback coordinator;
this shim simply re-exports those names so the 19 adapter call sites need
ZERO edits.

Pre-Phase 3 history: this shim previously re-exported from
``core/transport/raw_http/client.py`` (the legacy single-backend code). The
re-target to ``core.transport`` is the moment the dual-backend behavior
goes live for every adapter. Same function names, same signatures, new
routing.

**Direct-key bypass**: this module's ``api_call`` thin wrapper accepts a
legacy ``api_key`` kwarg that the public ``core.transport.api_call`` facade
deliberately does NOT carry. When ``api_key`` is provided, the shim routes
directly to ``core/transport/raw_http/client.api_call`` with the explicit
key forwarded through, bypassing the coordinator entirely. This preserves
the explicit-key escape hatch the canonical plan documents while keeping
the backend-agnostic facade free of raw-HTTP-specific concepts (the SDK
backend has no equivalent ``api_key`` parameter at all).

The ``BASE_URL`` constant is also re-exported because legacy tests (and the
auth test file) assert on it.

In a future PR, adapter imports may be migrated to
``from core.transport import api_call, ...`` directly, at which point this
shim can be deleted. The ``api_key=`` bypass is the only behavior on this
file that is not a pure re-export.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from core.transport import (
    BASE_URL,
    stream_generate_content,
    upload_file,
)
from core.transport import api_call as _facade_api_call
from core.types import JSONObject

__all__ = ["BASE_URL", "api_call", "stream_generate_content", "upload_file"]


def api_call(
    endpoint: str,
    body: Mapping[str, object] | None = None,
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
    api_key: str | None = None,
) -> JSONObject:
    """Legacy ``api_call`` signature with the ``api_key`` bypass.

    When ``api_key`` is None, forwards to the public facade in
    ``core.transport`` which routes through the dual-backend coordinator.
    When ``api_key`` is provided, calls the raw HTTP client directly with
    the key forwarded through, bypassing the coordinator entirely. The
    bypass exists because the SDK backend has no equivalent direct-key
    parameter and would not honor it; the only callers that pass this
    kwarg today live in test fixtures and a small set of legacy code
    paths that need to override the resolved key.

    Args:
        endpoint: REST endpoint path.
        body: JSON request body, or None for GET.
        method: HTTP method.
        api_version: API version segment.
        timeout: Request timeout in seconds.
        api_key: Optional explicit API key. When set, bypasses the
            coordinator and routes directly to the raw HTTP client.

    Returns:
        The parsed JSON response dict.
    """
    if api_key is not None:
        # Direct-key bypass — lazy import so the shim stays cheap when
        # no caller exercises the bypass.
        from core.transport.raw_http import client as _raw

        return _raw.api_call(
            endpoint=endpoint,
            body=dict(body) if body is not None else None,
            method=method,
            api_version=api_version,
            timeout=timeout,
            api_key=api_key,
        )
    return cast(
        JSONObject,
        _facade_api_call(
            endpoint=endpoint,
            body=body,
            method=method,
            api_version=api_version,
            timeout=timeout,
        ),
    )
