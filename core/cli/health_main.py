"""Health check — validate API key, connectivity, backend selection, venv state.

Originally this module just confirmed the API key worked and the API was
reachable. Phase 5 extends it to also report the dual-backend transport
state so users can answer "is my installation healthy?" with one
command:

- Primary backend (sdk vs raw_http) per Config flags
- Fallback backend (raw_http when SDK is primary, ``(none)`` otherwise)
- Skill venv path + existence
- Pinned google-genai version (parsed from setup/requirements.txt)
- Installed google-genai version (probed by running the venv python)
- Drift warning when pinned ≠ installed (signal that someone bypassed
  the install flow with an out-of-band ``pip install --upgrade``)

The backend / venv reporting runs BEFORE the API connectivity check so
users see the full picture even if the network call fails.

Dependencies: core/auth/auth.py, core/infra/client.py, core/infra/config.py,
core/cli/installer/venv.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.infra.sanitize import safe_print


def _install_dir() -> Path:
    """Return the user-global skill install directory.

    Wrapped in a function (instead of a module-level constant) so tests
    can ``patch.object(core.cli.health_main, "_install_dir", ...)`` to
    point at a tmp_path without affecting other tests.
    """
    return Path.home() / ".claude" / "skills" / "gemini"


def _read_pinned_version(install_dir: Path) -> str | None:
    """Parse the pinned google-genai version from setup/requirements.txt.

    Returns the version string (e.g. ``"1.33.0"``) or ``None`` if the
    file is missing or the pin can't be parsed. Defensive parsing —
    a malformed manifest reports ``None`` instead of crashing the
    health check.
    """
    req = install_dir / "setup" / "requirements.txt"
    if not req.is_file():
        return None
    # Match ``google-genai==<version>`` ignoring any leading whitespace
    # and inline comments. The regex anchors on the line start so a
    # commented-out reference won't trip us.
    pattern = re.compile(r"^\s*google-genai\s*==\s*([^\s#]+)", re.MULTILINE)
    match = pattern.search(req.read_text())
    if match is None:
        return None
    return match.group(1)


def _report_backend_and_venv(install_dir: Path) -> None:
    """Print the dual-backend + venv + SDK pin/install summary lines."""
    # Backend selection — read directly from Config so the report
    # reflects whatever env / config file the user has set.
    from core.infra.config import load_config

    cfg = load_config()
    primary = cfg.primary_backend
    fallback = cfg.fallback_backend if cfg.fallback_backend is not None else "(none)"
    safe_print(f"Primary backend: {primary}")
    safe_print(f"Fallback backend: {fallback}")

    # Venv path + existence.
    venv_dir = install_dir / ".venv"
    state = "exists" if venv_dir.exists() else "missing"
    safe_print(f"Venv: {venv_dir} ({state})")

    # Pinned vs installed SDK version.
    pinned = _read_pinned_version(install_dir) or "unknown"
    installed: str | None
    if venv_dir.exists():
        try:
            from core.cli.installer import venv as venv_helper

            installed = venv_helper.verify_sdk_importable(venv_dir)
        except Exception as exc:  # pragma: no cover - defensive
            installed = f"probe-failed ({exc})"
    else:
        installed = "unknown"
    safe_print(f"google-genai: pinned={pinned}, installed={installed}")

    # Drift warning — only fires when both versions are concrete and
    # differ. ``unknown`` on either side means we can't confirm a
    # mismatch, so we stay quiet rather than emitting a noisy warning.
    if pinned != "unknown" and installed not in (None, "unknown") and pinned != installed:
        safe_print(
            f"[WARN] SDK version drift: pinned {pinned} but installed {installed}. "
            "Re-run setup/install.py to reset the pin."
        )


def main(argv: list[str]) -> None:
    """Run the health check.

    Args:
        argv: Command-line arguments (unused, kept for launcher contract).
    """
    del argv  # Unused — kept for launcher contract consistency.
    safe_print("Checking gemini-skill health...")

    # Backend / venv / SDK report runs FIRST so users see the full
    # picture even if subsequent network checks fail.
    install_dir = _install_dir()
    _report_backend_and_venv(install_dir)

    # Check API key resolution.
    try:
        from core.auth.auth import resolve_key

        resolve_key()
        safe_print("[OK] API key resolved")
    except Exception as e:
        safe_print(f"[FAIL] API key: {e}")
        return

    # Check API connectivity.
    try:
        from core.infra.client import api_call

        response = api_call("models", method="GET")
        models = response.get("models", [])
        safe_print(f"[OK] API reachable ({len(models)} models visible)")
    except Exception as e:
        safe_print(f"[FAIL] API connectivity: {e}")
        return

    safe_print("All checks passed.")
