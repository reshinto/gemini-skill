"""Health check — validate API key and connectivity.

Calls the Gemini models list endpoint to verify the API key
works and the network is reachable. Reports success or actionable
error messages.

Dependencies: core/auth/auth.py, core/infra/client.py
"""
from __future__ import annotations

from core.infra.sanitize import safe_print


def main(argv: list[str]) -> None:
    """Run the health check."""
    safe_print("Checking gemini-skill health...")

    # Check API key resolution
    try:
        from core.auth.auth import resolve_key
        resolve_key()
        safe_print("[OK] API key resolved")
    except Exception as e:
        safe_print(f"[FAIL] API key: {e}")
        return

    # Check API connectivity
    try:
        from core.infra.client import api_call
        response = api_call("models", method="GET")
        models = response.get("models", [])
        safe_print(f"[OK] API reachable ({len(models)} models visible)")
    except Exception as e:
        safe_print(f"[FAIL] API connectivity: {e}")
        return

    safe_print("All checks passed.")
