"""Dual-backend Gemini transport package.

This package owns the ``TransportCoordinator`` and its two backends
(``sdk`` via google-genai, ``raw_http`` via urllib). Adapters import the
public facade (``api_call``, ``stream_generate_content``, ``upload_file``)
from this package — they never touch a backend module directly, so the
choice of backend (and the fallback behavior) stays a single
implementation detail behind the facade.

The package layout is intentionally flat for now and gains submodules as
later phases land:

- ``base``        — Transport protocol + shared exceptions + TypedDicts
- ``policy``      — pure fallback-eligibility decision table
- ``normalize``   — SDK response → REST envelope conversion
- ``coordinator`` — primary/fallback execution logic
- ``raw_http/``   — RawHttpTransport implementation
- ``sdk/``        — SdkTransport implementation
"""
