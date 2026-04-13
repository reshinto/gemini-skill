"""Installer subpackage — Phase 5.

This subpackage holds the installer's discrete responsibilities, split
out of the monolithic ``install_main.py`` so each piece has a clear
test surface:

- ``venv``: skill-local virtual environment creation, pip install of
  pinned runtime dependencies, SDK importability verification.

Future Phase 5 follow-ups will add:
- ``settings_merge``: ~/.claude/settings.json env-block merge with
  duplicate-key conflict resolution.
- ``api_key_prompt``: interactive GEMINI_API_KEY setup.
- ``legacy_migration``: one-time ~/.claude/skills/gemini/.env →
  settings.json migration.

The orchestrator in ``core/cli/install_main.py`` stitches these
together into the end-to-end install flow.
"""
