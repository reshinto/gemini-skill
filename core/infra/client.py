"""Backward-compatibility shim — re-exports the raw HTTP client.

The real implementation lives at ``core/transport/raw_http/client.py``. This
shim exists so the existing adapters (and ``core/auth/auth.py``,
``core/cli/health_main.py``) keep working without import-path edits while the
dual-backend transport refactor lands.

In a future PR, adapter imports may be migrated to
``from core.transport import api_call, ...`` (the public facade), at which
point this shim can be deleted.

What you'll learn from this file:
    - A "shim" is a thin module whose only job is to forward names from
      another module so callers don't have to update their imports. Python's
      ``from X import Y`` statement copies the binding into the importing
      module, so re-exporting is as simple as importing here and listing the
      names in ``__all__``.
"""

from __future__ import annotations

from core.transport.raw_http.client import (
    BASE_URL,
    api_call,
    stream_generate_content,
    upload_file,
)

__all__ = ["BASE_URL", "api_call", "stream_generate_content", "upload_file"]
