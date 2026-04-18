# Architecture — Installer

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

The install pipeline: payload manifest, venv re-exec, settings merge, legacy
migration, and SHA-256 integrity verification.

---

## Install Pipeline Overview

There are two supported install entry points:

- `setup/install.py` for source checkouts and release tarballs
- `gemini-skill-install` for `uvx` / `pipx` bootstrap installs

Both delegate to the same install core (`core/cli/install_main.py`) and shared payload manifest.

![Install flow](diagrams/install-flow.svg)
<sub>Source: [`docs/diagrams/install-flow.mmd`](diagrams/install-flow.mmd) — regenerate with `bash scripts/render_diagrams.sh`</sub>

The install flow runs six phases:

1. Resolve source + install directories.
2. If install dir exists: prompt `[O]verwrite / [S]kip?`.
3. Copy operational files (`copy_install_payload`).
4. Write SHA-256 integrity manifest (`.checksums.json`).
5. Create skill-local venv at `<install_dir>/.venv`; pip-install `setup/requirements.txt`.
6. Migrate legacy `.env` → `settings.json`; prompt for `GEMINI_API_KEY`; merge defaults into `~/.claude/settings.json`.

---

## Payload Manifest

Source: `core/cli/installer/payload.py`

The installer copies a fixed set of runtime files — no test files, full docs tree, or git history are included in the installed payload.

| Constant | Value |
|---|---|
| `INSTALL_ROOT_FILES` | `("SKILL.md", "VERSION")` |
| `INSTALL_DIRS` | `("core", "adapters", "reference", "registry", "scripts")` |
| `INSTALL_SETUP_FILES` | `("setup/update.py", "setup/requirements.txt")` |
| `INSTALL_COPY_IGNORE_PATTERNS` | `("__pycache__", "*.pyc")` |

`iter_install_payload_paths()` returns 9 paths total: 2 root files + 5 dirs + 2 setup files.

---

## Install Destination and `CLAUDE_SKILL_DIR` Semantics

The default install destination is `~/.claude/skills/gemini/` (resolved by `_get_install_dir()` in `install_main.py`).

The `gemini-skill-install` bootstrap entry point (`gemini_skill_install/cli.py`) materializes the packaged payload from the wheel/sdist into the install directory, then delegates to `install_main`. This means the same install logic runs whether invoked from a source checkout or a `uvx`/`pipx` bootstrap.

Entries preserved when overwriting an existing install:

| Constant | Value |
|---|---|
| `_PRESERVE_ON_OVERWRITE` | `frozenset({".venv", ".env"})` |

This prevents an overwrite from destroying an existing venv or local `.env` credentials.

---

## Venv Re-exec

The installer creates a skill-local virtual environment at `<install_dir>/.venv` and pip-installs the pinned SDK (`google-genai==1.33.0` from `setup/requirements.txt`).

At runtime, `scripts/gemini_run.py` checks for `.venv/` and re-execs itself under `.venv/bin/python` before dispatch. This makes the pinned SDK available without modifying the user's system Python or requiring a manual `pip install`. The CLI surface is unchanged.

---

## Settings Merge

After venv creation, the installer merges Gemini environment defaults into `~/.claude/settings.json` (the user-global Claude Code settings file). The merge key set is `_DEFAULT_ENV_KEYS` (an alias of `CANONICAL_ENV_DEFAULTS` from `core/infra/runtime_env.py`):

| Key | Default Value |
|---|---|
| `GEMINI_API_KEY` | `""` |
| `GEMINI_IS_SDK_PRIORITY` | `"true"` |
| `GEMINI_IS_RAWHTTP_PRIORITY` | `"false"` |
| `GEMINI_LIVE_TESTS` | `"0"` |

The merge is additive — existing values in `settings.json` are not overwritten. The installer also prompts for `GEMINI_API_KEY` if it is not already set.

---

## Legacy Migration

The installer migrates a legacy `.env` file (if present at the install root) into `~/.claude/settings.json` during Phase 6. This covers users who had previously stored their API key in `.env` before the settings-based env-var approach was introduced. After migration, `.env` is preserved in place (it is in `_PRESERVE_ON_OVERWRITE`) but no longer the primary source.

---

## SHA-256 Checksums

Source: `core/infra/checksums.py`

Phase 4 of the install writes a `.checksums.json` manifest with SHA-256 hashes of all installed runtime files.

- **Generation**: the installer writes `.checksums.json` with hashes of all installed runtime files
- **Verification**: `health_check.py` verifies hashes after install and on later health checks
- **Refusal**: If user modified files post-install, health check reports drift and refuses silent update

Directories excluded from the checksum manifest:

| Constant | Value |
|---|---|
| `_CHECKSUMS_EXCLUDED_DIRS` | `frozenset({".venv", "__pycache__"})` |

The checksum manifest filename is controlled by `_CHECKSUMS_FILENAME = ".checksums.json"`.

---

## File Locking and Atomic Writes

The skill uses platform-agnostic file locking to prevent data corruption under concurrent access (Claude Code can parallelize tool calls):

- **POSIX (macOS/Linux):** `fcntl.flock()`
- **Windows:** `msvcrt.locking()`

Atomic writes use `os.replace()` with retry logic (catching `PermissionError` from antivirus scanners on Windows).

This ensures that if Claude Code invokes `gemini` twice in parallel, state files don't get corrupted.

---

## Dependencies

**Runtime:**

- Python 3.9+ standard library
- `google-genai==1.33.0` (installed into the skill venv at `~/.claude/skills/gemini/.venv` by the installer)
- Raw HTTP backend works without google-genai (fallback always available)

**Build/Development:**

- pytest, coverage (for testing)
- build / setuptools / wheel (for `gemini-skill-install` distributions)
- ruff (linting)
- jsdoc2md, madge (optional: docs generation)

**Deployment:**

- `setup/install.py` and `gemini-skill-install` copy the same runtime payload, create or reuse the skill-local venv, install the pinned SDK, and write the install manifest
- Release workflow builds a GitHub release tarball plus Python wheel/sdist artifacts for the bootstrap installer
- Install destination is the user-global skill directory at `~/.claude/skills/gemini/`
- No test files, full docs tree, or git history are shipped in the installed runtime payload

---

## Key Design Principles (Installer)

1. **Fail closed:** Ambiguity or missing data → error. Never proceed silently.
2. **Pinned SDK + stdlib fallback:** google-genai is pinned exactly in `setup/requirements.txt` for reproducible installs; raw HTTP backend uses stdlib only and remains the always-available fallback.
3. **Atomic state:** All reads/writes use file locking and atomic swaps.
4. **Layered auth:** Shell env (from settings.json) > .env > error.

---

## See also

- [install.md](install.md) — setup instructions and install walkthrough
- [architecture.md](architecture.md) — module map and runtime path
- [architecture-transport.md](architecture-transport.md) — dual-backend transport
- [update-sync.md](update-sync.md) — update and sync mechanism
