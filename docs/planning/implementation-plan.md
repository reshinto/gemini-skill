# Plan: gemini-skill

## Context

Build a standalone GitHub repository containing a **Claude Code skill** (SKILL.md + Python scripts) providing broad Gemini REST API coverage (excluding Live/WebSocket features). Claude Code only — Claude Desktop SKILL.md loading is unverified and not claimed. Modular adapter architecture, managed local install with sync/update, strong security defaults.

---

## 1. Verification Summary

**Official docs checked:**
- Claude Code skills: https://code.claude.com/docs/en/skills
- Gemini Developer API: https://ai.google.dev/gemini-api/docs
- Gemini REST API reference: https://ai.google.dev/api/all-methods (v1 and v1beta endpoints)
- Gemini auth: `x-goog-api-key` header
- Files API: `upload/v1beta/files` for upload, `v1beta/files` for metadata, 48hr/2GB/20GB limits
- File Search: long-running operations via `operations` resource
- Interactions API: beta, for stateful orchestration (noted, not first-class in v1)

**Confirmed:**
- SKILL.md + `${CLAUDE_SKILL_DIR}` is the standard Claude Code skill entrypoint
- Skills install to `~/.claude/skills/<name>/` (personal) or `.claude/skills/<name>/` (project)
- Gemini API uses `x-goog-api-key` HTTP header for auth
- API versions: prefer `v1` where the capability is documented there; use `v1beta` where the capability is only documented there. v1beta includes early features subject to breaking changes. SDKs default to v1beta.
- Fine-tuning: with Gemini 1.5 Flash-001 deprecated, there is no model currently available that supports tuning in the Gemini API or AI Studio. Tuning is supported in Vertex AI.
- File Search: current hosted RAG product (long-running operations, polling required)
- Live API: WebSocket-based — excluded (stdlib incompatible)
- Tool-combination state: provider-returned state blocks (including `id`, `tool_type`, `thought_signature`) must be preserved exactly as returned in multi-turn flows
- `.env` support: skill reads optional `.env` from install dir (convenience); shell env vars always take precedence

**Uncertain:**
- Gemini 3.1 pricing (preview, may change)
- Exact official model IDs for Nano Banana family / Veo / Lyria (use registry, probe at runtime)

**Note:** All non-GitHub official doc links referenced in this plan were verified at review time (April 2026). Pages may move over time — `ecc:docs-lookup` runs before each merge/release to revalidate. The GitHub repo URL (`reshinto/gemini-skill`) is not yet live — created during Phase 0.

---

## 2. Architecture Decisions

### Claude Code skill only (SKILL.md + scripts)
No MCP server. Claude Desktop not claimed.

### Python (stdlib only)
No Python package dependencies. Requires `python3` 3.9+ on PATH (explicit prerequisite in README, not hidden).

### JSON everywhere (not YAML)
Python stdlib has no YAML parser. All registries, config, and state files use JSON.

### `x-goog-api-key` header auth
API key sent exclusively via HTTP header. Never in URL query string.

### Per-adapter API version routing
Each adapter uses the documented API version for its capability. The client defaults to `v1beta` when unspecified. v1beta features may have breaking changes. The exact v1/v1beta split evolves — verify against current docs during implementation.

### Fail closed
Auth failure, unsupported model, missing pricing, ambiguity → error. Never proceed silently.

### Two-tier operation policy
1. **Mutating** (uploads, deletes, cache creation, batch submission) → require `--execute` flag (dry-run default)
2. **Cost/privacy-sensitive** (search grounding, maps grounding, URL context, inline file send) → require explicit opt-in even if non-mutating

### Pre-approved tools via allowed-tools
`allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/gemini_run.py *)` — **pre-approves** the launcher script so Claude can run it without per-use permission prompts. Note: `allowed-tools` does NOT restrict other tools — it only pre-approves listed tools. To actually block unwanted tools, use permission settings in `.claude/settings.json`. The `allowed-tools` line is a convenience, not a security boundary.

### Thin launchers → dedicated entry modules
Each entry script is a 2.7-safe launcher importing its own module:
- `scripts/gemini_run.py` → `core.cli.dispatch.main()` (CLI dispatcher + policy enforcement)
- `setup/install.py` → `core.cli.install_main.main()`
- `setup/update.py` → `core.cli.update_main.main()`
- `scripts/health_check.py` → `core.cli.health_main.main()`

`core/cli/dispatch.py` is the policy boundary for the skill CLI: whitelist of subcommands, per-subcommand flag validation, path/URL argument validation, file size limits, dry-run vs execute enforcement.

### File locking for concurrent access
Claude Code can parallelize tool calls. `cost.py` and `state.py` use `fcntl.flock` (POSIX) / `msvcrt.locking` (Windows) to prevent data loss from concurrent read-modify-write cycles.

### UTC timestamps for state
All timestamps in `state.py` and `cost.py` use `time.time()` (POSIX epoch, timezone-independent). No `datetime.now()` (affected by timezone/DST changes).

### Socket timeouts for streaming
All `urllib.request.urlopen()` calls pass explicit `timeout` parameter. SSE streaming loop has a dead-connection guard (no data for 30s → fail closed with network error).

### Atomic writes with retry
`os.replace()` for atomic file swaps. On Windows, wrapped with retry (3 attempts, 0.1/0.2/0.4s backoff) catching `PermissionError` (antivirus scanner interference).

### `.env` support (auto-read)
The skill reads `.env` from the installed skill directory if present (`~/.claude/skills/gemini/.env`). Shell environment variables always take precedence. `.env` is a convenience for users who prefer not to set env vars in their shell profile.

**Parser rules (deliberately simple):**
- Accept `KEY=VALUE` lines
- Split on the first `=` only (values may contain `=`)
- Trim surrounding whitespace from key and value
- Strip quotes from value **only** when first and last character are the same quote type (`"` or `'`). Users commonly paste `KEY="value"` — this makes that work correctly.
- Ignore blank lines and lines starting with `#`
- No inline comment support (a `#` in a value is part of the value)

This narrow parser is easy to reason about, hard to get wrong, and won't corrupt secrets containing special characters.

**Install behavior:**
- If `.env` doesn't exist → create from template with empty values and inline documentation
- If `.env` already exists → run the merge logic below (same as update)

**Update behavior (non-destructive merge):**
1. Parse existing `.env` keys (only keys, values are opaque)
2. Parse template `.env.example` keys from the new release
3. **New keys** (in template but not in user's `.env`) → append at bottom with empty value, commented explanation, and a `# Added by gemini-skill update vX.Y.Z` marker
4. **Existing keys** → never touched (values preserved exactly)
5. **Removed keys** (in user's `.env` but no longer in template) → left in place, never deleted. A comment is appended: `# Note: KEY_NAME is no longer used by gemini-skill vX.Y.Z`
6. Print summary: "Added N new variable(s), M variable(s) deprecated — review your .env file"

**Result:** user's existing values are always preserved. New vars appear automatically. Old vars are flagged but never deleted. Zero manual work required for the common case.

### Tool-combination state in shared core
`core/tool_state.py` preserves the entire provider-returned content parts and state blocks exactly as received — including `id`, `tool_type`, `thought_signature`, and any additional provider-defined fields or nested structures. The implementation treats these as opaque blobs (round-trip the full JSON), not a fixed field list. All adapters in multi-turn tool loops (code_exec, function_calling, future adapters) use this shared module.

### Registry as advisory baseline
`models.json` and `capabilities.json` are offline hints, not truth. Preview adapters probe the live API at runtime with graceful fallback when a model exists in registry but is unavailable. `refresh_capabilities.py` shows diff and requires review before any write.

### Interactions API awareness
`deep_research.py` uses the Interactions API exclusively (not generateContent). Tool-heavy flows may also benefit from Interactions in the future. Both are preview with explicit churn risk.

### Install/update in Python (not shell)
`setup/install.py` and `setup/update.py` use only stdlib. macOS and Linux supported. Windows: best-effort (documented).

### Checksum-verified atomic updates
SHA-256 checksums verify download integrity (not authenticity). Signing planned for future. Documented limitation.

### Secure file permissions
Config dirs: `0o700`. Files: `0o600`. Best-effort on Windows (documented).

---

## 3. Project Name

The project and repository will be named **`gemini-skill`**.

---

## 4. Repository Tree

```
gemini-skill/
├── SKILL.md                          # Claude Code skill entrypoint (ultra-lean ~30 lines)
├── README.md
├── LICENSE                           # MIT
├── VERSION                           # e.g., 0.1.0
├── .env.example                      # Template for .env
├── .gitignore
│
├── setup/                            # Install, update, and dev tooling
│   ├── install.py                    # Install to ~/.claude/skills/gemini/
│   ├── update.py                     # Checksum-verified atomic sync
│   ├── checksums.txt                 # SHA-256 for release verification
│   ├── requirements-dev.txt          # Dev dependencies (pytest, pytest-cov, pytest-split)
│   ├── run_tests.sh                  # Auto-setup venv + run tests (macOS/Linux)
│   └── pytest.ini                    # pytest config
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Syntax check + unit tests + coverage on push/PR
│       └── release.yml               # Build checksums + create release on tag push
│
├── core/
│   ├── __init__.py
│   │
│   ├── auth/                         # Authentication & secrets
│   │   ├── __init__.py
│   │   ├── auth.py                   # API key resolution (env var + .env)
│   │   ├── sanitize.py               # Output scrubbing + global exception hook
│   │   └── config.py                 # JSON config (~/.config/gemini-skill/config.json)
│   │
│   ├── infra/                        # Infrastructure & plumbing
│   │   ├── __init__.py
│   │   ├── client.py                 # REST client (urllib.request, x-goog-api-key header)
│   │   ├── errors.py                 # Error types, fail-closed, retry classification
│   │   ├── filelock.py               # Cross-platform file locking (fcntl/msvcrt)
│   │   ├── cost.py                   # Pre-flight estimate + post-response tracking (file-locked)
│   │   ├── mime.py                   # guess_mime_for_path(): 3.13+ guess_file_type, 3.9-3.12 guess_type
│   │   └── timeouts.py              # install_timeout_guard(): signal.alarm (POSIX main thread) or watchdog
│   │
│   ├── state/                        # State management
│   │   ├── __init__.py
│   │   ├── file_state.py             # Files API upload state (48hr expiry, canonical identity)
│   │   ├── store_state.py            # File Search store state (persistent, no expiry)
│   │   ├── session_state.py          # Multi-turn conversation sessions
│   │   └── identity.py               # Shared canonical document identity (SHA-256 + MIME + path)
│   │
│   ├── routing/                      # Model selection & capability registry
│   │   ├── __init__.py
│   │   ├── router.py                 # Model selection logic
│   │   ├── registry.py               # JSON capability/model registry loader
│   │   └── tool_state.py             # Shared id/tool_type/thought_signature preservation
│   │
│   ├── adapter/                      # Adapter framework
│   │   ├── __init__.py
│   │   ├── contract.py               # Protocol defining the adapter interface
│   │   └── helpers.py                # Shared adapter lifecycle (parse → validate → call → track → emit)
│   │
│   └── cli/                          # CLI & entry points
│       ├── __init__.py
│       ├── dispatch.py               # CLI dispatcher + policy enforcement
│       ├── install_main.py           # Install logic
│       ├── update_main.py            # Update logic
│       └── health_main.py            # Health check logic
│
├── adapters/
│   ├── __init__.py
│   │
│   ├── generation/                   # Content generation adapters
│   │   ├── __init__.py
│   │   ├── text.py                   # Text generation
│   │   ├── multimodal.py             # Image/audio/video/PDF/URL input
│   │   ├── structured.py             # JSON schema output
│   │   └── streaming.py              # SSE streaming (text models, timeout-guarded)
│   │
│   ├── media/                        # Media generation adapters (preview)
│   │   ├── __init__.py
│   │   ├── image_gen.py              # Image generation — Nano Banana family
│   │   ├── video_gen.py              # Video generation — Veo (long-running)
│   │   └── music_gen.py              # Music generation — Lyria 3 (30s, SynthID)
│   │
│   ├── tools/                        # Tool-based adapters
│   │   ├── __init__.py
│   │   ├── function_calling.py       # Function/tool calling
│   │   ├── code_exec.py              # Code execution
│   │   ├── search.py                 # Google Search grounding
│   │   └── maps.py                   # Google Maps grounding
│   │
│   ├── data/                         # Data management adapters
│   │   ├── __init__.py
│   │   ├── files.py                  # File API (generator-based chunked upload)
│   │   ├── cache.py                  # Context caching
│   │   ├── batch.py                  # Batch API
│   │   ├── embeddings.py             # Embedding generation
│   │   ├── file_search.py            # File Search / hosted RAG (long-running)
│   │   └── token_count.py            # Token counting
│   │
│   └── experimental/                 # Preview/experimental adapters (high churn risk)
│       ├── __init__.py
│       ├── computer_use.py           # Computer use (verify transport at impl time)
│       └── deep_research.py          # Deep research (Interactions API only)
│
├── reference/                         # Per-command reference files — FLAT (no subdirs)
│   │                                  # Claude maps command → reference/<command>.md directly
│   │                                  # Template: Synopsis, Usage, Flags, Examples, API Reference,
│   │                                  #   Troubleshooting, Limitations
│   ├── index.md                      # Command index: name, purpose, mutating?, preview?
│   ├── text.md
│   ├── multimodal.md
│   ├── structured.md
│   ├── streaming.md
│   ├── image_gen.md
│   ├── video_gen.md
│   ├── music_gen.md
│   ├── function_calling.md
│   ├── code_exec.md
│   ├── search.md
│   ├── maps.md
│   ├── files.md
│   ├── cache.md
│   ├── batch.md
│   ├── embed.md
│   ├── file_search.md
│   ├── token_count.md
│   ├── computer_use.md
│   ├── deep_research.md
│   ├── models.md
│   ├── health.md
│   ├── refresh.md
│   └── abort.md                      # Manual-only: force-kill stuck processes
│
├── registry/
│   ├── capabilities.json             # Capability manifest (advisory baseline)
│   └── models.json                   # Model catalog with pricing (advisory baseline)
│
├── scripts/
│   ├── gemini_run.py                 # Thin 2.7-safe launcher → core/cli/dispatch.py
│   ├── refresh_capabilities.py       # Fetch live models, diff, review before write
│   └── health_check.py              # Validate API key + connectivity
│
├── docs/
│   ├── planning/
│   │   └── implementation-plan.md    # This plan (project history/reference)
│   ├── diagrams/
│   │   ├── architecture.mmd          # Mermaid sources + rendered PNGs
│   │   ├── architecture.png
│   │   ├── data-flow.mmd
│   │   ├── data-flow.png
│   │   ├── dependency-graph.mmd
│   │   ├── dependency-graph.png
│   │   ├── execution-trace.mmd
│   │   ├── execution-trace.png
│   │   ├── file-upload-lifecycle.mmd
│   │   ├── file-upload-lifecycle.png
│   │   ├── model-routing.mmd
│   │   └── model-routing.png
│   ├── architecture.md               # System design, module boundaries, data flow
│   ├── how-it-works.md               # End-to-end execution trace (command → API → result)
│   ├── code-map.md                   # Every file, its purpose, dependency graph
│   ├── install.md                    # Step-by-step install
│   ├── update-sync.md               # Update/sync/merge workflow
│   ├── security.md                   # Threat model, secret handling, permissions
│   ├── commands.md                   # Lightweight command index linking to reference/<command>.md
│   ├── capabilities.md              # Capability matrix, status, limitations
│   ├── model-routing.md             # Model selection, overrides, cost
│   ├── usage.md                     # Getting started, workflows, tips
│   ├── python-guide.md              # Stdlib patterns, conventions
│   ├── contributing.md              # Adding adapters, updating registry
│   └── testing.md                   # Running tests, writing tests
│
├── tests/                            # pytest = dev dependency only
│   ├── __init__.py
│   ├── conftest.py                   # Root fixtures (mock urllib, fake API key, temp dirs)
│   │
│   ├── core/                         # Tests mirror core/ subdirectory structure
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_sanitize.py
│   │   │   └── test_config.py
│   │   ├── infra/
│   │   │   ├── __init__.py
│   │   │   ├── test_client.py
│   │   │   ├── test_errors.py
│   │   │   ├── test_filelock.py
│   │   │   ├── test_cost.py
│   │   │   ├── test_mime.py              # Assert: 3.13+ uses guess_file_type, 3.9-3.12 uses guess_type, no cgi
│   │   │   └── test_timeouts.py          # Assert: POSIX main-thread signal, Windows watchdog, non-main-thread guard
│   │   ├── state/
│   │   │   ├── __init__.py
│   │   │   ├── test_file_state.py
│   │   │   ├── test_store_state.py
│   │   │   ├── test_session_state.py
│   │   │   └── test_identity.py
│   │   ├── routing/
│   │   │   ├── __init__.py
│   │   │   ├── test_router.py
│   │   │   ├── test_registry.py
│   │   │   └── test_tool_state.py        # Must assert: id, tool_type, thought_signature preserved + unknown fields round-trip
│   │   ├── adapter/
│   │   │   ├── __init__.py
│   │   │   ├── test_contract.py
│   │   │   └── test_helpers.py
│   │   └── cli/
│   │       ├── __init__.py
│   │       ├── test_dispatch.py
│   │       ├── test_install_main.py
│   │       ├── test_update_main.py
│   │       └── test_health_main.py
│   │
│   ├── adapters/                     # Tests mirror adapters/ subdirectory structure
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── generation/
│   │   │   ├── __init__.py
│   │   │   ├── test_text.py          # Includes multi-turn session tests
│   │   │   ├── test_multimodal.py
│   │   │   ├── test_structured.py
│   │   │   └── test_streaming.py
│   │   ├── media/
│   │   │   ├── __init__.py
│   │   │   ├── test_image_gen.py
│   │   │   ├── test_video_gen.py
│   │   │   └── test_music_gen.py
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── test_function_calling.py
│   │   │   ├── test_code_exec.py
│   │   │   ├── test_search.py
│   │   └── test_maps.py              # Must assert: sources follow content, title displayed, uri/googleMapsUri linked
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── test_files.py
│   │   │   ├── test_cache.py
│   │   │   ├── test_batch.py
│   │   │   ├── test_embeddings.py
│   │   │   ├── test_file_search.py
│   │   │   └── test_token_count.py
│   │   └── experimental/
│   │       ├── __init__.py
│   │       ├── test_computer_use.py
│   │       └── test_deep_research.py
│   │
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── test_gemini_run.py
│   │   ├── test_health_check.py
│   │   └── test_refresh_capabilities.py
│   │
│   ├── fixtures/                     # Recorded API response mocks (sanitized JSON)
│   │   ├── v1/                       # Stable endpoint fixtures
│   │   └── v1beta/                   # Preview endpoint fixtures
│   │
│   └── integration/                  # Optional live tests (GEMINI_LIVE_TESTS=1)
│       ├── __init__.py
│       ├── conftest.py               # Skip unless GEMINI_LIVE_TESTS=1
│       ├── test_live_text.py
│       └── test_live_models.py
│
└── (uses setup/pytest.ini from repo)
```

---

## 5. Implementation Plan

### Python compatibility

**Target: Python 3.9+** (ships with macOS Monterey+, Ubuntu 20.04+).

**Entry script separation:** Each launcher uses only Python 2.7-compatible syntax and imports its own entry module:

```python
# scripts/gemini_run.py
import sys
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(*sys.version_info[:2]))
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from core.cli.dispatch import main
main(sys.argv[1:])

# setup/install.py → from core.cli.install_main import main
# setup/update.py → from core.cli.update_main import main
# scripts/health_check.py → from core.cli.health_main import main
```

No `from __future__`, no f-strings, no dataclasses in entry scripts. All 3.9+ code in `core/` and `adapters/`, imported only after guard. Even Python 2.7 gets a readable error.

Internal modules use `from __future__ import annotations` and modern type hints.

**Type hints are mandatory on all internal code (core/, adapters/):**
- All function parameters and return types must be annotated
- **Runtime trap**: `str | None` syntax works in annotations (deferred by `from __future__`), but **NOT at runtime** (e.g., in `isinstance()`, `argparse type=`, or non-annotated contexts). Use `typing.Optional[str]` or `typing.Union[str, None]` for any runtime-evaluated types. This applies to Python 3.9.
- `-> None` for functions that don't return
- Built-in generics: `list[str]`, `dict[str, int]`
- Union: `str | None` (enabled by `from __future__ import annotations`)
- All `@dataclass` fields must be typed
- Entry scripts (2.7-safe launchers) are exempt from type hints

**Python 3.13 hard rules (enforced in code and tests, not just docs):**
- **Never use `cgi`** — removed in 3.13. Use `email.mime` / `email.message` for multipart construction.
- **MIME detection**: `mimetypes.guess_file_type(path)` on 3.13+, `mimetypes.guess_type(str(path))` on 3.9-3.12. Implement as version-gated helper in `core/infra/`.
- **Timeouts**: `signal.alarm()` only on POSIX main thread (check `threading.current_thread() is threading.main_thread()`). Windows uses daemon watchdog thread. Never install signal handlers from worker threads.
- These are verified by the CI Python 3.9/3.11/3.13 matrix.

### Execution Strategy

Each phase specifies: model, agents, and parallelism.

**Phase 0: Repository setup**
- Model: Opus
- Agents: 1 `general-purpose` — create repo, initial files, git init, push, create branch
- Skills: none
- Rules: none

**Phase 1: Core infrastructure**
- Model: Opus (security-critical)
- Step 1: 1 `ecc:architect` agent — validate module boundaries, data flow, dependency graph before coding
- Step 2: 1 `ecc:tdd-guide` agent — writes failing tests for each module, then implements
  - Module order (sequential): errors → filelock → sanitize → auth → config → client → state → tool_state → cost
- Step 3 (after implementation, run in parallel):
  - 1 `ecc:python-reviewer` agent — Python conventions, DRY, SRP
  - 1 `ecc:security-reviewer` agent — auth.py, sanitize.py, filelock.py, client.py
  - 1 `ecc:comment-analyzer` agent — verify all docstrings are present and useful
  - 1 `ecc:code-simplifier` agent — identify unnecessary complexity, suggest simplifications
- Rules: 500-line file limit, SOLID principles, GoF patterns where applicable, code documentation standard, no subprocess shelling

**Phase 2: Registry**
- Model: Sonnet
- Step 1: 1 `general-purpose` agent — create JSON data files (models.json, capabilities.json) + registry.py
- Step 2: 1 `ecc:tdd-guide` agent — write tests for registry.py, verify pass
- Step 3: 1 `ecc:python-reviewer` agent — review
- Rules: 500-line file limit, code documentation standard

**Phase 3: Router + cost**
- Model: Opus (routing logic is critical)
- Step 1: 1 `ecc:planner` agent — validate routing decision tree against capability matrix
- Step 2: 1 `ecc:tdd-guide` agent — write tests for router.py + cost.py, then implement
- Step 3: 1 `ecc:python-reviewer` agent — review
- Rules: 500-line file limit, DRY, single responsibility

**Phase 4: Core adapters**
- Model: Sonnet
- Step 1: 3 `general-purpose` agents in parallel (worktree isolation), each using TDD:
  - `adapter-text`: text.py, multimodal.py, structured.py
  - `adapter-embed`: embeddings.py, streaming.py, token_count.py
  - `adapter-tool`: function_calling.py, code_exec.py
- Step 2 (parallel):
  - 1 `ecc:python-reviewer` agent — review all Phase 4 code
  - 1 `ecc:code-simplifier` agent — check for duplicate patterns across adapters, suggest shared helpers
  - 1 `ecc:comment-analyzer` agent — verify docstrings
- Rules: uniform adapter pattern, 500-line limit, code documentation standard

**Phase 5: Advanced adapters**
- Model: Sonnet
- Step 1: 2 `general-purpose` agents in parallel (worktree isolation), each using TDD:
  - `adapter-file`: files.py, cache.py, batch.py
  - `adapter-grounding`: search.py, maps.py, file_search.py
- Step 2 (parallel):
  - 1 `ecc:python-reviewer` agent — review all Phase 5 code
  - 1 `ecc:code-simplifier` agent — check for duplicate patterns with Phase 4 adapters
- Rules: uniform adapter pattern, long-running op handling, 500-line limit

**Phase 6: Preview adapters**
- Model: Sonnet
- Step 1: 2 `general-purpose` agents in parallel (worktree isolation), each using TDD:
  - `adapter-media`: image_gen.py, video_gen.py, music_gen.py
  - `adapter-preview`: computer_use.py, deep_research.py
- Step 2 (parallel):
  - 1 `ecc:python-reviewer` agent — review all Phase 6 code
  - 1 `ecc:security-reviewer` agent — review deep_research.py (Interactions API) for security
- Rules: v1beta only, large response guard, Interactions API for deep_research, 500-line limit

**Phase 7: CLI + SKILL.md**
- Model: Opus (dispatch is the policy boundary)
- Step 1: 1 `ecc:tdd-guide` agent — write tests for dispatch.py, then implement
- Step 2: 1 `general-purpose` agent — write SKILL.md with all command documentation
- Step 3 (parallel):
  - 1 `ecc:python-reviewer` agent — review dispatch.py
  - 1 `ecc:security-reviewer` agent — review dispatch policy enforcement + SKILL.md allowed-tools + shell argument safety
- Rules: no subprocess shelling invariant

**Phase 8: Install/update**
- Model: Opus (security-sensitive)
- Step 1: 1 `ecc:tdd-guide` agent — write tests for install_main.py, update_main.py, health_main.py, .env merge logic, then implement
- Step 2 (parallel):
  - 1 `ecc:python-reviewer` agent — review code
  - 1 `ecc:security-reviewer` agent — review checksum verification, atomic operations, permission handling
- Rules: atomic writes, checksum verification, no subprocess shelling, file permissions

**Phase 9: CI + test infrastructure**
- Model: Sonnet
- Step 1: 1 `general-purpose` agent — GitHub Actions ci.yml (lint + test matrix), release.yml (with `permissions: contents: write`, checksum generation)
- Step 2: 1 `general-purpose` agent — run_tests.sh, pytest.ini, conftest.py with record/playback fixtures
- Step 3: 1 `ecc:security-reviewer` agent — review CI workflows for secret exposure, permission escalation, unsafe actions
- Step 4: Push CI workflows and trigger a test run. If CI fails:
  - 1 `ecc:build-error-resolver` agent — diagnose and fix CI failures
- Rules: venv isolation for pytest, record mode opt-in only, no secrets in CI logs

Note: No dedicated DevOps agent exists in the agent library. `general-purpose` + `ecc:security-reviewer` + `ecc:build-error-resolver` cover the CI/CD needs.

**Phase 10: Documentation + diagrams**
- Model: Sonnet
- Step 1: 1 `ecc:architect` agent — review final architecture, validate code-map accuracy against actual code, produce architecture overview for docs
- Step 2: 1 `ecc:planner` agent — design documentation structure, outline each doc file's sections and flow, ensure nothing is missing
- Step 3: 3 `ecc:doc-updater` agents in parallel (documentation specialists):
  - `docs-architecture`: architecture.md, how-it-works.md, code-map.md
  - `docs-guides`: install.md, update-sync.md, security.md, capabilities.md
  - `docs-reference`: commands.md, model-routing.md, usage.md, python-guide.md, contributing.md, testing.md
- Step 4: 1 `general-purpose` agent — generate Mermaid diagram sources (.mmd) for all architecture, data flow, dependency, execution trace, file upload lifecycle, and model routing diagrams
- Step 5: 1 `general-purpose` agent — render Mermaid .mmd files to PNG using CLI tools, verify all images render correctly
- Step 6 (parallel):
  - 1 `ecc:code-reviewer` agent — review all documentation for accuracy against actual codebase
  - 1 `ecc:docs-lookup` agent — verify all external doc links (Gemini API, Claude Code) are working and correct
- Rules: every doc for zero-context readers, Mermaid for all diagrams, verified doc links, README updated with final feature list

Each phase commits to `feat/initial-implementation` after passing all checks. Phase transitions are gated — next phase cannot start until prior phase passes.

### Token optimization: Micro-Context Strategy

**Do NOT pass the full plan to implementation agents.** Instead, slice context per task:

**Global rules snippet (~150 words, always included):**
> Python 3.9+ stdlib only. No `cgi` module. Fail closed. NEVER `os.system()` or `shell=True`. 500-line limit. `from __future__ import annotations`. `os.replace()` for atomic writes. Type hints mandatory. SOLID principles. Docstrings on everything.

**Per-module context:** Only pass the global rules + that module's pseudocode from Section 12 + its specific architectural rules. Do not pass the full capability matrix or unrelated module specs.

**Adapter stub injection (Phases 4-6):** Before generating adapters, provide a stub of `core/client.py` and `core/router.py`. Instruct: "Assume `core.client.api_call` exists and handles auth/headers/retries. Your job: parse argparse, format JSON body, handle response."

**Reviewer context:** Pass only the generated code + test file. Do not pass the implementation plan. Prompt: "Review for SOLID, SRP, security, 3.9+ idioms."

**Final quality gate (after Phase 10, all run in parallel):**
- 1 `ecc:refactor-cleaner` agent — dead code, unused imports, duplicates across entire codebase
- 1 `ecc:performance-optimizer` agent — bottlenecks in core modules (client, state, filelock)
- 1 `ecc:code-reviewer` agent — full end-to-end review
- 1 `ecc:security-reviewer` agent — final security scan
- 1 `ecc:comment-analyzer` agent — final docstring/comment completeness check
- 1 `ecc:silent-failure-hunter` agent — find error paths that silently fail instead of raising, empty except blocks, swallowed errors
- 1 `ecc:pr-test-analyzer` agent — analyze test coverage, identify untested branches, verify test quality
- 1 `ecc:conversation-analyzer` agent — review SKILL.md conversation patterns, ensure Claude-Gemini interaction flows are well-structured

**Pre-PR checklist (before creating the pull request):**
- 1 `ecc:chief-of-staff` agent — triage all review findings, prioritize fixes, create action items
- 1 `ecc:docs-lookup` agent — verify all external doc links are still working (Gemini API docs, Claude Code docs)
- 1 `ecc:doc-updater` agent — final pass on all documentation, ensure consistency with implemented code

### Phase 0: Repository setup

1. Rename current directory: `mv /Users/springfield/dev/unamedproject /Users/springfield/dev/gemini-skill`
2. `cd /Users/springfield/dev/gemini-skill`
3. Copy this implementation plan to `docs/planning/implementation-plan.md`
4. Create initial files: `README.md` (stub), `LICENSE` (MIT), `VERSION` (0.1.0), `.env.example` (`.gitignore` already exists)
5. `git init && git add -A && git commit -m "Initial repository setup with implementation plan"`
6. Create GitHub repo + push:
   `gh repo create reshinto/gemini-skill --public --description "Claude Code skill for broad Gemini REST API access" --source . --remote origin --push`
7. `git checkout -b feat/initial-implementation`

### Phase 1: Core infrastructure (TDD: tests first → fail → implement → pass → 100% coverage)

**`.env.example`** — Template for `.env` (`setup/install.py` copies this as `.env` if none exists):
```
# Gemini API key (required — get one at https://aistudio.google.com/apikey)
GEMINI_API_KEY=

# Alternative env var name (optional — if set, takes precedence over GEMINI_API_KEY)
# GOOGLE_API_KEY=

# Enable live integration tests (optional, dev use only)
# GEMINI_LIVE_TESTS=1
```

The skill reads `.env` from its install directory using a simple stdlib parser. Shell env vars always take precedence.

**`core/auth.py`** — Loads `.env` from skill dir first (stdlib parser, no dependency). Parser uses the same rules as section 2: split on first `=`, trim whitespace, strip matching outer quotes (`"` or `'`), skip blank lines and `#` comments, no inline comment support. Shell env vars always override `.env`. Then resolves key: `GOOGLE_API_KEY` (if set) → `GEMINI_API_KEY` → fail closed. Consistent everywhere. Never construct strings containing key. `validate_key()` calls the models list endpoint (`GET /v1beta/models`).

**`core/config.py`** — JSON at `~/.config/gemini-skill/config.json`. Dirs `0o700`, files `0o600` (best-effort Windows). Fields: `default_model`, `prefer_preview_models`, `cost_limit_daily_usd`, `dry_run_default`, `deep_research_timeout_seconds` (default 3600, capped at 3600).

**`core/client.py`** — REST client:
- `x-goog-api-key` header only
- `api_call(endpoint, body, api_version="v1beta")` — adapters may override to `"v1"` where supported. Default is v1beta since most capabilities require it.
- Explicit `timeout` on all `urlopen()` calls
- Retry: 429, 503, transient network (exponential backoff). No retry: 400, 401, 403, 404.
- Never logs headers or auth-bearing URLs

**`core/cli/dispatch.py`** — CLI dispatcher + policy enforcement:
- Whitelist of allowed subcommands
- Per-subcommand flag validation
- Path/URL argument validation
- File size limit checks
- Dry-run vs execute enforcement
- No shell-interpolated subprocess calls — all values untrusted, never `os.system()` or `shell=True` (**repo-wide invariant**, not just dispatch)

**`core/sanitize.py`** — Last-resort defense. Primary boundary: never construct key-containing strings. Fallback: regex scrub, `sys.excepthook` override, stderr wrapper.

**`core/errors.py`** — Fail-closed. Clean messages for expected errors (no traceback). Retry classification:
- Retry (backoff, max 3: 1s/2s/4s): 429, 503, ConnectionError, TimeoutError, URLError with no HTTP status
- No retry: 400, 401, 403, 404
- 504 DEADLINE_EXCEEDED: one retry for idempotent reads only
- Idempotent-only: uploads, batch create, cache create (poll, don't re-submit)
- `ssl.SSLCertVerificationError`: macOS-specific fix message

**Network resilience (prevents wasted tokens on failures):**
- **429 (overloaded)**: retry with backoff. After max retries → clear error: "Gemini API rate-limited. Try again in {retry-after}s." No silent loops.
- **Connection lost mid-request**: retry with backoff. After max retries → short error message to stdout. Claude reads one response, decides to retry or inform user.
- **Connection lost mid-streaming**: 30s dead-connection guard. Returns partial result with `[STREAM INTERRUPTED]` marker. Claude sees marker, decides action.
- **Long-running op poll failure (Veo/File Search/Deep Research)**: retry the poll, not the whole operation. Server-side state is intact.
- **All failures → short, clear stdout error.** No large error dumps. No infinite retry loops. Minimal Claude token consumption even on network failures.

**Process-level safety guards (prevent hangs and memory leaks):**
- **Global execution timeout**: configurable max execution time (default: 300s normal, 600s long-running). POSIX: `signal.alarm()` (main thread only). Windows: daemon watchdog thread. On timeout → `[TIMEOUT] Operation exceeded {n}s limit. Exiting.` and `sys.exit(1)`. Note: `signal.alarm` is Unix-only and only works in the main thread of the main interpreter.
- **Polling timeout**: per-command configurable. Veo/File Search: default 30 minutes. Deep Research: 60 minutes (documented max; most tasks finish within 20 min). Timeout is resumable — prints operation/interaction ID so Claude can resume polling later. If exceeded → print `[POLL TIMEOUT] Operation did not complete within {n}s. Operation ID: {id}. You can resume polling later.` and exit with the operation ID so Claude can retry.
- **Memory guard**: for generator-based uploads, if memory usage exceeds a threshold (default: 500MB), abort with `[MEMORY LIMIT] Aborting to prevent resource exhaustion.`
- **Stuck connection detection**: all `urllib.request.urlopen()` calls have explicit `timeout` parameter. SSE streaming has 30s dead-connection guard. No blocking call without a timeout.
- **Graceful exit**: all timeouts and guards use `sys.exit(1)` with a clear message to stdout. Claude reads the message and can decide to retry, inform the user, or take alternative action. Never hangs silently.
- **Abort command**: force-kills any stuck gemini-skill process. Manual-only.
  - **How to trigger**: tell Claude "abort the gemini operation" or "kill the stuck gemini process". Claude reads `reference/abort.md` and runs: `python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" abort`
  - **Implementation**: PID file at `~/.config/gemini-skill/gemini.pid`. Written at process start, read by abort. SIGTERM (POSIX) / TerminateProcess (Windows).
  - **Safety**: validates a start-marker token written to the PID file by the original process (prevents PID reuse accidents — does not rely on process name matching). Handles stale PIDs (process already exited → clean up and report). PID file cleaned up on normal exit.
  - **Output**: `[ABORTED] Killed gemini-skill process {pid}.` or `[NO PROCESS] No running gemini-skill process found.`
  - **Docs**: full usage, examples, and edge cases in `reference/abort.md` and `docs/commands.md`

**`core/filelock.py`** — Cross-platform file locking: `fcntl.LOCK_EX | fcntl.LOCK_NB` (POSIX), `msvcrt.locking` (Windows). Non-blocking with timeout (5s max, tiny sleep interval). Context manager (`with filelock(path):`) guarantees release even on exception. Documented limitation: may not work reliably on network filesystems or cloud-synced folders.

**`core/state.py`** — Two separate state stores:

**Canonical document identity** (used by both state stores):
```json
{
  "content_sha256": "abc123...",
  "mime_type": "application/pdf",
  "source_path": "/absolute/normalized/path.pdf",
  "source_uri": null
}
```
- Local files: `source_path` = absolute real path (`pathlib.Path.resolve()`, resolves symlinks), `source_uri` = null
- Remote files: `source_path` = null, `source_uri` = original URI
- This identity is used for deduplication across both Files API and File Search stores

1. **Files API state** (`~/.config/gemini-skill/files.json`):
   - Canonical document identity → Gemini file URI + expiry (UTC epoch via `time.time()`)
   - 48hr retention, 2GB/file, 20GB/project limits
   - Lazy remote validation near expiry

2. **File Search store state** (`~/.config/gemini-skill/stores.json`):
   - Store name/ID → list of imported documents (canonical identity) + operation status + indexing completion
   - File Search stores persist indefinitely (unlike raw files which expire at 48hr)
   - Distinct from Files API state

3. **Conversation sessions** (`~/.config/gemini-skill/sessions/`):
   - `<session-id>.json` — conversation history as Gemini `contents` array (alternating user/model parts)
   - Created on first `--session <id>` call, appended per turn, cleared on `--end-session`
   - Enables Claude-Gemini iterative conversations (multi-turn review, research, drafting)

All state stores use: atomic writes (`os.replace()` with Windows retry), file-locked read-modify-write, UTC timestamps.

**`core/tool_state.py`** — Shared helper for preserving `id`, `tool_type`, `thought_signature` in multi-turn tool loops. Used by `code_exec.py`, `function_calling.py`, and future tool-using adapters.

**`core/cost.py`** — Two-phase, file-locked:
1. Pre-flight estimate from registry pricing
2. Post-response tracking from `usageMetadata`
- Cost numbers are estimates (local pricing table + provider metadata). Not guaranteed exact.
- Daily accumulator: `~/.config/gemini-skill/cost_today.json` (atomic, file-locked, UTC date key)

### Phase 2: Registry (TDD)

**`registry/models.json`** — Advisory offline baseline. Runtime probes live API for preview models. Updated by `refresh_capabilities.py` (review required).

**`registry/capabilities.json`** — Capability → adapter mapping with status, API version, supported models.

**`core/registry.py`** — Loads JSON. `get_model()`, `get_capability()`, `list_models()`, `list_capabilities()`. Caches successful live model probes in memory (per-process) to avoid calling `models.list` too frequently for preview adapters.

### Phase 3: Router + Cost (TDD)

**`core/router.py`** — Model selection by task type + complexity. `prefer_preview_models` config flag. User override always wins. Resolves against live model list when available, falls back to registry baseline.

### Phase 3.5: Adapter contract (before parallel adapters)

Before parallelizing adapter agents, create `core/adapter/contract.py` — a Python `Protocol` defining the exact adapter interface. This prevents parallel agents from inventing different patterns:

```python
class AdapterProtocol(Protocol):
    def get_parser(self) -> argparse.ArgumentParser: ...
    def run(self, **kwargs) -> None: ...
    # Standard flow: parse_args → build_request → call_api → parse_response → track_cost → emit_output
```

All adapter agents receive this file + `core/client.py` stub instead of English descriptions. Code is more token-efficient and unambiguous than prose.

### Phase 4: Core adapters (TDD)

`text.py`, `multimodal.py`, `structured.py`, `embeddings.py`, `streaming.py`, `function_calling.py`, `token_count.py`

Each adapter: `run()` + argparse `__main__`. Mutating → `--execute`. Cost/privacy-sensitive → explicit opt-in. Output as text to stdout.

**Multi-turn conversation support (`text.py`, `multimodal.py`):**

The Gemini API supports multi-turn conversations via a `contents` array with alternating `user`/`model` roles. This enables Claude to have iterative dialogues with Gemini — sending prompts, evaluating responses, and sending follow-ups until convergence.

Implementation:
- `--session <id>` flag: starts or continues a conversation session
- Session state stored at `~/.config/gemini-skill/sessions/<id>.json` (conversation history as `contents` array)
- `--continue` flag: shorthand for continuing the most recent session
- Each call appends the new user message, sends full `contents` array to API, appends model response, saves session
- `--end-session` flag: clears the session file
- Session files are atomic-written and file-locked (reuses `core/filelock.py`)
- Cost tracking accumulates across the session
- Session history is **not** sent to stdout (only the latest response is). Claude reads each response, decides whether to continue.

Example flow (Claude orchestrating a Gemini conversation):
```
# Claude starts a session
python3 scripts/gemini_run.py text --session review "Analyze this code for bugs: ..."
# Gemini responds with analysis
# Claude reads response, wants more detail
python3 scripts/gemini_run.py text --continue "Focus on the race condition you mentioned. What's the fix?"
# Gemini responds with fix
# Claude is satisfied, presents to user
```

**Note:** This is a **client-side conversation-history mechanism** for `generateContent`, not the Interactions API's server-side `previous_interaction_id` state. The Gemini generateContent endpoint is stateless — the skill manages the `contents` array locally and sends the full history with each request. This mirrors how the official SDKs implement chat sessions. For server-side state (agentic/long-running work), use the Interactions API path instead (used by `deep_research.py`).

This enables Claude-Gemini iterative workflows: code review convergence, multi-step research, collaborative drafting, etc.

**`files.py`:** Generator-based chunked reading (8MB chunks). Memory stays bounded (not zero — headers, retry buffers, multipart framing consume some memory, but never the full file). Upload endpoint: `upload/v1beta/files`. Resumable upload with `Content-Range`. Idempotent retry with operation polling.

**`streaming.py`:** SSE via chunked `urllib.request` with explicit `timeout`. Dead-connection guard (30s no data → fail closed). Text models only.

**`function_calling.py` and `code_exec.py`:** Use `core/tool_state.py` for state preservation in multi-turn flows.

### Phase 5: Advanced adapters (TDD)

`files.py`, `cache.py`, `batch.py`, `search.py`, `maps.py`, `file_search.py`

- `files.py`: v1beta (`upload/v1beta/files`). Generator-based chunked upload.

- `file_search.py`: v1beta. **Hard limits**: 100MB per document, project total by tier (1GB/10GB/100GB/1TB). **Recommendation**: keep each store under 20GB for latency. Long-running operations (`uploadToFileSearchStore` → poll). Idempotent. **Tool combination rule**: For direct generateContent requests, File Search may be combined with custom tools on Gemini 3 models, but not with Google Search grounding or URL Context in the same request. Deep Research (Interactions API) can separately use file_search alongside its default tools.
- `search.py`: Google Search grounding. Can combine with URL context, code execution, custom tools on Gemini 3 models. Outputs = untrusted external content.
- `maps.py`: Google Maps grounding. Off by default, explicit opt-in. Must validate model support before request. Outputs = untrusted external content.
  **Mandatory output schema (testable contract)**:
  1. Grounded answer text
  2. `Sources:` line immediately after answer (no intervening content)
  3. One line per source: `- [<title>](<uri or googleMapsUri>) — Google Maps`
  4. Attribution notice: `This answer uses Google Maps data.`
  Precedence: use `uri` if present, fall back to `googleMapsUri`. `test_maps.py` must assert: ordering, title presence, attribution line, and correct link-field precedence.

### Phase 6: Preview adapters (v1beta) (TDD)

`image_gen.py`, `video_gen.py`, `music_gen.py`, `computer_use.py`, `deep_research.py`

- All use v1beta. Registry is advisory; adapters probe live API with graceful fallback.
- **`image_gen.py`**: Nano Banana family. API returns base64-encoded image data inline in JSON (`candidates[0].content.parts[].inlineData`). The adapter **decodes base64 and saves to a file**, then returns only the file path + metadata (dimensions, format, file size) to stdout. **Never outputs raw base64 to stdout** — this would overflow Claude Code's token limit. Claude can use its Read tool to view the saved image. Output directory: (1) user-configured `output_dir` in config.json, (2) OS temp dir (`tempfile.gettempdir()`) as default. Never writes to the user's CWD by default (prevents workspace/git pollution). All returned file paths are **absolute** (`pathlib.Path(f).resolve()`). Route resolves to official model ID from live list or pinned registry.
- **`video_gen.py`**: Veo. API uses **long-running operations** — adapter calls `predictLongRunning` (raw REST path; SDKs expose `generate_videos` helpers, but we use REST directly for stdlib-only). Polls operation until done, extracts download URI, saves video to file, returns file path + metadata. 5-10 min generation time. Graceful 400 handling (strict safety filters).
- **`music_gen.py`**: Lyria 3. API returns base64-encoded audio inline in JSON (similar to images). Adapter decodes and saves to file, returns file path + metadata. 30s cap, SynthID watermark. Set `response_modalities: ["AUDIO", "TEXT"]` in request. Documented.
- **`deep_research.py`**: Uses the **Interactions API** (not generateContent). Three distinct implementation paths:
  1. **Background polling resume**: `background=true`, poll by interaction ID until completed/failed/cancelled
  2. **Stateful conversation**: use `previous_interaction_id` for follow-up interactions in the same research context
  3. **Stream reconnection**: if streaming was used and interrupted, reconnect using interaction ID + last event ID (client must persist both)
  Server-side state: `store=true` (default, enables retained state). `store=false` is incompatible with `background=true`.
  Preview with high churn risk. Requires its own Interactions-based client path.

### Phase 7: CLI + Skill entrypoint (TDD for dispatch)

**`scripts/gemini_run.py`** — 2.7-safe launcher → `core.cli.dispatch.main()`.

**`SKILL.md`** — Ultra-lean router (~30 lines). Minimizes context token usage.
```yaml
---
name: gemini
description: Gemini API — text gen, image/video/music gen, embeddings, search, cache, batch, code execution, and more.
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/gemini_run.py *)
argument-hint: "[command] [args]"
---

## Usage
Run: `python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`

See `${CLAUDE_SKILL_DIR}/reference/index.md` for the full command map.
For commands with flags or --execute, read `${CLAUDE_SKILL_DIR}/reference/<command>.md` first.


## Rules
- Mutating operations require --execute flag (dry-run default)
- Pass user input as single opaque argv values
- Use stdin or temp files for complex/multiline content
- Never reconstruct shell commands by concatenating user text
```

The skill uses a lean-router pattern: SKILL.md stays short, while detailed per-command instructions live in `reference/<command>.md`. This reduces routine context load because Claude loads the skill body only when the skill is used, and supporting files are referenced on demand. Exact context size depends on invoked content, referenced files, and conversation compaction behavior.

### Phase 8: Install/update

**`setup/install.py`** — 2.7-safe launcher. Checks 3.9+. Copies **only operational files**:

```
~/.claude/skills/gemini/
├── SKILL.md
├── VERSION
├── .env                              # Created on install; updated via non-destructive merge
├── setup/
│   └── update.py                     # Included so users can update from installed skill
├── core/ (all .py)
├── adapters/ (all .py)
├── reference/ (all .md)
├── registry/ (all .json)
└── scripts/ (gemini_run.py, health_check.py, refresh_capabilities.py)
```

**NOT installed** (GitHub repo only): `README.md`, `LICENSE`, `.gitignore`, `setup/checksums.txt`, `setup/install.py`, `.env.example`, `setup/requirements-dev.txt`, `setup/run_tests.sh`, `setup/pytest.ini`, `docs/`, `tests/`

Users run `python3 ~/.claude/skills/gemini/setup/update.py` to check for and apply updates.

**`setup/update.py`** — 2.7-safe launcher. Checksum-verified atomic updater:
1. Fetch latest release tag
2. Compare VERSION
3. Download to temp dir (same filesystem as target for atomic swap)
4. Verify SHA-256 checksums (fetched from the release's `checksums.txt` — integrity only, not authenticity)
5. Back up current install
6. Offer: overwrite / merge / skip
7. Merge: `difflib` (cross-platform)
8. Atomic swap: `os.replace()` (retry with backoff on Windows)
9. Rollback on failure
10. User config preserved (outside skill dir)

**`refresh_capabilities.py`** — Fetches live model list, diffs registry, shows review before write. Never auto-rewrites.

### Design pattern enforcement (applies to ALL code)

**SOLID principles are mandatory:**
- **S**ingle Responsibility: each class/function does one thing
- **O**pen/Closed: adapters are open for extension (new adapters), closed for modification (core doesn't change)
- **L**iskov Substitution: all adapters are interchangeable via the uniform adapter contract
- **I**nterface Segregation: adapters depend only on the core interfaces they need
- **D**ependency Inversion: adapters depend on abstractions (core/client.py), not concrete implementations

**If OOP is used — Gang of Four patterns where applicable:**
- **Strategy**: `core/router.py` — model selection varies by task type
- **Template Method**: adapter contract — `run()` follows a standard flow, adapters override steps
- **Factory**: `core/cli/dispatch.py` — creates the right adapter based on subcommand
- **Singleton**: `core/registry.py` — in-memory model cache (per-process)
- **Decorator**: `core/sanitize.py` — wraps output functions with sanitization

**If functional programming is used instead:**
- Pure functions where possible (no side effects except I/O)
- Composition over inheritance
- Higher-order functions for shared behavior (e.g., retry logic as a wrapper function)
- Immutable data structures preferred (`@dataclass(frozen=True)` where appropriate)
- Strategy → function dispatch (dict of functions keyed by task type)
- Factory → function lookup table
- Decorator → function wrapper / closure
- SOLID still applies: SRP per function/module, DI via function parameters, OCP via new adapter files

**The choice between OOP and FP is per-module.** Use whichever is cleaner for each case. Python supports both idioms well. The codebase should be consistent within each module.

### Code quality gates (applies to ALL phases)

**After every phase, run a code review** (via `ecc:python-reviewer` agent if available, or manual review) that checks:
- Modern Python conventions (3.9+ idioms where applicable)
- DRY compliance — no duplicated logic across files
- Single Responsibility Principle — every function/class does one thing
- **500-line hard limit per file** — if a file exceeds 500 lines, split it
- Updated design patterns (dataclasses, context managers, generators, type hints)
- No god functions, no god classes
- Clean imports (no circular, no unused)

If the reviewer flags issues, fix them before moving to the next phase.

**Code documentation standard (applies to ALL code):**
- Every file: module-level docstring explaining purpose, what this module does, and how it fits into the system
- Every class: class docstring explaining responsibility, key behaviors, and usage examples where helpful
- Every public function: docstring with purpose, parameters, return value, and any side effects or important behaviors
- Every private function: brief docstring explaining what it does
- Inline comments: used to explain **why** (not what) when the logic isn't self-evident
- Goal: a new developer can read any file and immediately understand its purpose, how it connects to other modules, and how to modify it — without consulting anyone

### TDD approach (applies to ALL phases)

**Every phase follows strict TDD: write tests first, watch them fail, then implement until they pass.**

Workflow per module:
1. Write unit tests for the module (tests must fail — no implementation yet)
2. Run `pytest` to confirm failure
3. Implement the module
4. Run `pytest` to confirm pass
5. Verify 100% coverage with `pytest --cov`
6. Move to next module

**Coverage target: 100% on security/policy-critical code** (auth, dispatch, sanitize, filelock, cost, state, errors, tool_state). High coverage on adapters and registry. 100% is the aspiration across the whole codebase but not a hard gate that blocks shipping — strict coverage on critical paths is the non-negotiable.

`pytest` and `pytest-cov` are dev dependencies. They are installed in a sandboxed venv that is **separate from the skill runtime** (the skill itself has zero dependencies and no venv).

**Dev environment setup:**
1. `python3 -m venv .venv` (created in repo root, gitignored)
2. `.venv/bin/pip install -r setup/requirements-dev.txt`
3. `.venv/bin/pytest -c setup/pytest.ini --cov`

**CRITICAL:** All pytest invocations MUST use the venv's Python/pytest binary, never the system `pytest`. This prevents dev dependencies from leaking into the system Python.

**`setup/run_tests.sh`** — Convenience shell script that handles everything automatically:
1. Check if `.venv/` exists in repo root
2. If not: create it (`python3 -m venv .venv`), activate, install from `setup/requirements-dev.txt`
3. If yes: activate the existing venv
4. Run `pytest -c setup/pytest.ini --cov` with any additional args passed through (`./setup/run_tests.sh -v -k test_auth`)
5. Deactivate on exit

This means running tests is always a single command: `./setup/run_tests.sh`

**`setup/requirements-dev.txt`** (not installed with skill):
```
pytest>=7.0
pytest-cov>=4.0
pytest-split>=0.8
```

This venv is for development/testing only. The installed skill at `~/.claude/skills/gemini/` never has a venv and never needs pip.

Default and CI tests mock `urllib.request.urlopen` — no network calls. Live/record mode (`GEMINI_LIVE_TESTS=1`, `GEMINI_RECORD_MOCKS=1`) is explicit opt-in only.

**Record/playback mock strategy for v1beta schemas:**
- `GEMINI_RECORD_MOCKS=1 .venv/bin/pytest` → explicit opt-in only, bypasses mock, hits live API, captures raw responses, sanitizes via `core/sanitize.py`, saves to `tests/fixtures/` as static JSON
- Default mode → mock reads from `tests/fixtures/` (no network)
- **Opt-in only**: never runs during normal test or CI. May incur API cost. May capture preview-only fields that later disappear. Documented in `docs/testing.md` with cost/churn warnings.
- Prevents hand-coding volatile preview response shapes

**`setup/run_tests.sh`** is macOS/Linux only. Windows contributors use:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r setup\requirements-dev.txt
pytest -c setup\pytest.ini --cov
```
Documented in `docs/testing.md`.

### CI: GitHub Actions

**`.github/workflows/ci.yml`** — Runs on every push and PR:
- Matrix: Python 3.9, 3.11, 3.13 on `ubuntu-latest`
- Steps:
  1. Checkout
  2. Setup Python
  3. Install dev deps: `pip install -r setup/requirements-dev.txt`
  4. Syntax check: `python -m py_compile` on all `.py` files (syntax validation, not linting)
  5. Run `pytest --cov` with coverage threshold on critical paths
  6. Fail CI if tests fail or critical-path coverage drops

**Test sharding (pytest-split):**
- Use `pytest --splits N --group G` to shard tests across parallel runners
- **Shard count is auto-calculated** based on total test count:
  - <50 tests: no sharding (single runner)
  - 50-150 tests: 2 shards
  - 150-300 tests: 3 shards
  - 300+: 4 shards (cap — beyond this, overhead outweighs benefit)
- A pre-job step counts tests via `pytest --collect-only -q | wc -l` and sets the shard count dynamically
- Each shard runs on a separate GitHub Actions matrix entry (parallel)
- Test timing data stored in `.test_durations` (committed) to balance shard workload
- **Justification**: the test suite will have ~20+ test files across core/, adapters/, scripts/. At initial launch (~50-80 tests), 2 shards halves wall-clock CI time. Sharding avoids wasting resources on overkill parallelism while scaling automatically as tests grow.
- `pytest-split` added to `requirements-dev.txt`

- Future enhancement: add `ruff` (linting) and `mypy` (type checking) as optional CI steps

**`.github/workflows/release.yml`** — Runs on tag push (`v*`):
- Must declare `permissions: contents: write` (GitHub Actions defaults to read-only)
- Checkout
- Generate `checksums.txt` (SHA-256 of all operational files)
- Create GitHub release with tarball + `checksums.txt` attached
- `update.py` fetches these artifacts during user-initiated updates

### Phase 10: Documentation

Every doc written for someone who knows nothing about this project.

**Diagrams:** Architecture, data flow, dependency, and sequence diagrams are authored in Mermaid (`.mmd` files). Rendered to PNG and stored in `docs/diagrams/`. Markdown docs reference the PNGs. Mermaid rendering is an **optional contributor tooling dependency** (not a runtime or install requirement). GitHub also renders Mermaid natively in markdown as a fallback.

```
docs/
├── diagrams/
│   ├── architecture.mmd              # Mermaid source
│   ├── architecture.png              # Rendered PNG (referenced by docs)
│   ├── data-flow.mmd
│   ├── data-flow.png
│   ├── dependency-graph.mmd
│   ├── dependency-graph.png
│   ├── execution-trace.mmd
│   ├── execution-trace.png
│   ├── file-upload-lifecycle.mmd
│   ├── file-upload-lifecycle.png
│   ├── model-routing.mmd
│   └── model-routing.png
```

**`README.md`** — Overview, quick-start (clone, set GEMINI_API_KEY via shell env or .env, run `python3 setup/install.py`), feature list, links to docs. Both auth paths documented with precedence.

**`docs/architecture.md`** — System design: SKILL.md → `scripts/gemini_run.py` → `core/cli/dispatch.py` → `adapters/**/*.py` → `core/infra/client.py` → Gemini REST API. Module boundaries, data flow, state management, API version routing, security architecture, cost tracking, file upload lifecycle.

Includes a dedicated section on the **ultra-lean router pattern**:
- How SKILL.md works as a ~30-line router
- How `reference/` files are loaded on demand per capability
- Why this design was chosen (token efficiency)
- Token efficiency rationale: supporting files reduce routine context load because only the router + the relevant reference file are pulled in when needed. A monolithic SKILL.md would load all capabilities on every invocation. Once invoked, skill content stays in the conversation for the session.
- How Claude reads only what it needs: router → identify command → read specific reference file → execute

**`docs/how-it-works.md`** — End-to-end execution trace from `/gemini text "hello"` through version guard → dispatch → auth → router → adapter → client → API → response → sanitize → stdout → Claude. Similar traces for image gen, file upload, search grounding.

**`docs/code-map.md`** — Every file, purpose, imports, callers. Dependency graph. `scripts/gemini_run.py` → `core/cli/dispatch.py` → `core/auth/auth.py` + `core/auth/config.py` → `core/routing/router.py` → `adapters/**/*.py` → `core/infra/client.py`. `core/routing/tool_state.py` used by tool adapters. `core/infra/filelock.py` used by `core/infra/cost.py` + `core/state/*.py`.

**`docs/install.md`** — Prerequisites (Python 3.9+, Gemini API key). Three install methods documented:

**Method 1: install.py (recommended)**
```bash
# Replace with actual repo URL after Phase 0 creates the repository
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

**Method 2: Manual copy (no install script)**
```bash
# Replace with actual repo URL after Phase 0 creates the repository
git clone https://github.com/reshinto/gemini-skill.git
mkdir -p ~/.claude/skills/gemini/setup
cp -r gemini-skill/SKILL.md gemini-skill/VERSION gemini-skill/core gemini-skill/adapters gemini-skill/reference gemini-skill/registry gemini-skill/scripts ~/.claude/skills/gemini/
cp gemini-skill/setup/update.py ~/.claude/skills/gemini/setup/
cp gemini-skill/.env.example ~/.claude/skills/gemini/.env
# Edit ~/.claude/skills/gemini/.env and set your GEMINI_API_KEY
```

**Method 3: Download + copy (no git)**
Download release tarball from GitHub, extract, copy the same operational files to `~/.claude/skills/gemini/`.

All three methods result in the same installed structure. Auth: (1) `GEMINI_API_KEY` in shell profile (preferred), (2) `.env` in installed skill dir (convenience). Precedence: shell > `.env`. Health check, troubleshooting (macOS SSL, Python version).

**`docs/update-sync.md`** — How update.py works, checksums (integrity vs authenticity), merge workflow, rollback, version pinning.

**`docs/security.md`** — Threat model, secret handling, sanitize.py scope, file permissions, update security (integrity vs authenticity), .env as optional on-disk secret storage (shell env takes precedence, `0o600` permissions, never committed), grounding safety.

**`docs/commands.md`** — Human-facing overview organized by capability family. Each command gets a one-line description and a link to its `reference/<command>.md` file. No duplicated syntax, flags, or examples. Full details live exclusively in the reference files.

Each `reference/<command>.md` file is the **canonical source** for: Synopsis, Usage, Flags, Examples, API Reference, Troubleshooting, Limitations, and representative output samples (success and failure).

**`docs/capabilities.md`** — Conceptual overview of every capability. Capability summary tables are **generated from `registry/capabilities.json`**. Conceptual prose (what, why, limitations) is hand-authored. No command syntax, flags, or examples — those live exclusively in `reference/<command>.md`.

**Hard ownership rule:** No command metadata may be hand-edited outside `registry/capabilities.json`. All generated artifacts (`reference/index.md`, `docs/commands.md`, capability tables) must be regenerated when the registry changes.
Scope note: "broad REST coverage, excluding Live/WebSocket features."

**`docs/model-routing.md`** — Decision tree, override guide, cost implications, `prefer_preview_models`, runtime probing vs registry baseline.

**`docs/usage.md`** — Getting started, common workflows, cost efficiency tips. Explains the lean-router + supporting-files design and why it reduces context overhead.

**`docs/python-guide.md`** — Why stdlib only, 3.9+ floor, entry script separation, `from __future__ import annotations`, `os.replace()`, generator I/O, file locking. Includes **hard rules** (not advisory):
- No `cgi` module (removed in 3.13; use `email.mime` / `email.message` for multipart)
- On 3.13+: use `mimetypes.guess_file_type(path)`
- On 3.9-3.12: use `mimetypes.guess_type(str(path))`
- `signal.alarm()` only on POSIX main thread; Windows uses watchdog thread
These rules are enforced in tests (CI matrix includes Python 3.13).

**`docs/contributing.md`** — Adding adapters (template), updating registry, running tests, code style.

**`docs/testing.md`** — Dev venv setup (`python3 -m venv .venv`, `pip install -r setup/requirements-dev.txt`), running tests (`./setup/run_tests.sh` or `.venv/bin/pytest -c setup/pytest.ini --cov`), Windows commands, how mocking works, writing new tests, live test profile, coverage reporting.

---

## 6. Capability Matrix (verified against official docs)

| Capability | Status | Adapter | API Ver | Default Model | Official Doc |
|-----------|--------|---------|---------|---------------|-------------|
| Text generation | supported | text.py | v1/v1beta | gemini-2.5-flash | [Text Generation Guide](https://ai.google.dev/gemini-api/docs/text-generation) |
| Multimodal input | supported | multimodal.py | v1beta | gemini-2.5-flash | [Document Processing Guide](https://ai.google.dev/gemini-api/docs/document-processing) |
| Structured output | supported | structured.py | v1beta | gemini-2.5-flash | [Structured Output Guide](https://ai.google.dev/gemini-api/docs/structured-output) |
| Function calling | supported | function_calling.py | v1beta | gemini-2.5-flash | [Function Calling Guide](https://ai.google.dev/gemini-api/docs/function-calling) |
| Embeddings | supported | embeddings.py | v1beta | gemini-embedding-2-preview | [Embeddings Guide](https://ai.google.dev/gemini-api/docs/embeddings) |
| File API | supported | files.py | v1beta | N/A | [Files API Guide](https://ai.google.dev/gemini-api/docs/files) |
| Context caching | supported | cache.py | v1beta | gemini-2.5-flash | [Caching Guide](https://ai.google.dev/gemini-api/docs/caching) |
| Batch API | supported | batch.py | v1beta | user-specified | [Batch Processing Guide](https://ai.google.dev/gemini-api/docs/batch-api) |
| Code execution | supported | code_exec.py | v1beta | gemini-2.5-flash | [Code Execution Guide](https://ai.google.dev/gemini-api/docs/code-execution) |
| Search grounding | supported | search.py | v1beta | gemini-2.5-flash | [Google Search Grounding](https://ai.google.dev/gemini-api/docs/google-search) |
| SSE streaming | supported | streaming.py | v1/v1beta | user-specified | [Text Generation (Streaming)](https://ai.google.dev/gemini-api/docs/text-generation) |
| Token counting | supported | token_count.py | v1/v1beta | user-specified | [Token Counting Guide](https://ai.google.dev/gemini-api/docs/tokens) |
| File Search / RAG | preview/high-churn | file_search.py | v1beta | basic: gemini-2.5-flash-lite; structured output/tool combos: gemini-3-flash-preview | [File Search Guide](https://ai.google.dev/gemini-api/docs/file-search) — 100MB/doc, project tier limits, <20GB/store recommended |
| Maps grounding | supported | maps.py | v1beta | router-selected | [Maps Grounding Guide](https://ai.google.dev/gemini-api/docs/maps-grounding) |
| Image generation | preview | image_gen.py | v1beta | gemini-3.1-flash-image-preview | [Image Generation Guide](https://ai.google.dev/gemini-api/docs/image-generation) |
| Video generation | preview | video_gen.py | v1beta | veo-3.1-generate-preview | [Video Generation Guide](https://ai.google.dev/gemini-api/docs/video) |
| Music generation | preview | music_gen.py | v1beta | lyria-3-clip-preview / lyria-3-pro-preview | [Music Generation Guide](https://ai.google.dev/gemini-api/docs/music-generation) |
| Computer use | preview/verify-transport | computer_use.py | v1beta | gemini-3-flash-preview (default), gemini-2.5-computer-use-preview-10-2025 (fallback) | [Computer Use Guide](https://ai.google.dev/gemini-api/docs/computer-use) |
| Deep research | preview | deep_research.py | Interactions API | Interactions-only | [Deep Research Guide](https://ai.google.dev/gemini-api/docs/deep-research) |
| Fine-tuning | disabled | — | — | — | [Model Tuning Guide](https://ai.google.dev/gemini-api/docs/model-tuning) — no tunable model |
| Complex reasoning | supported | text.py | v1/v1beta | gemini-2.5-pro | [Thinking Guide](https://ai.google.dev/gemini-api/docs/thinking) |
| Thinking control | supported | (core router) | v1/v1beta | gemini-2.5-pro | [Thinking Guide](https://ai.google.dev/gemini-api/docs/thinking) |
| Live API | excluded | — | — | — | WebSocket; stdlib incompatible |

**Primary versioning rule: each adapter uses the documented API version for its capability.** The client defaults to v1beta when the adapter does not specify. Verify each capability's version against current docs during implementation — version availability may change.

**Brand names are aliases; API calls must use concrete model IDs.** User-facing docs may say "Nano Banana family" or "Veo" as product names, but router, registry, tests, and API calls must always resolve to a concrete model ID (e.g., `gemini-3.1-flash-image-preview`).

**Preview model IDs are runtime-verified placeholders.** IDs like `gemini-3.1-flash-image-preview`, `veo-3.1-generate-preview`, `lyria-3-clip-preview`, `gemini-2.5-computer-use-preview-10-2025`, and `deep-research-pro-preview-12-2025` are current at plan time but may change. The router and registry treat them as defaults that are verified against the live model list at runtime. Do not hardcode them as permanent constants.

**`registry/capabilities.json` is the single source of truth.** Hard generation rules:
- **Generated from registry**: `reference/index.md`, `docs/commands.md`, capability tables in `README.md` and `docs/capabilities.md`
- **Hand-authored only**: `reference/<command>.md` (detailed usage), conceptual prose in `docs/capabilities.md`, `docs/usage.md`, `docs/architecture.md`
- Registry fields: command name, adapter path, status, API version, preview/stable, mutating/privacy-sensitive, official doc URL, reference filename
- `refresh_capabilities.py` uses registry doc URLs to check for API updates

---

## 7. Security Design

- **Auth**: `x-goog-api-key` header only. Never in URL, files, output, logs.
- **Primary boundary**: never construct key-containing strings. `sanitize.py` is last-resort.
- **Exception hook**: `sys.excepthook` scrubs keys from tracebacks.
- **File permissions**: dirs `0o700`, files `0o600` (best-effort Windows).
- **Fail closed**: ambiguity → error. Never proceed silently.
- **Two-tier ops**: mutating → `--execute`; cost/privacy-sensitive → explicit opt-in.
- **Update**: SHA-256 integrity (not authenticity; signing planned).
- **allowed-tools**: pre-approves launcher (convenience, not restriction). `core/cli/dispatch.py` is real policy enforcement.
- **Grounding**: search/maps outputs = untrusted external content.
- **No subprocess shelling (repo-wide invariant)**: no code anywhere may invoke a subprocess with user-influenced strings. No `os.system()`, no `subprocess.Popen(shell=True)`, no string concatenation into shell commands. If subprocesses are ever needed, use argument lists only.
- **Interactions API storage**: Deep Research uses Interactions with `background=true`. The Interactions API stores interactions by default (`store=true`). `store=false` is incompatible with `background=true`. Stored interactions are retained for 55 days (paid) or 1 day (free tier). Users must be warned at runtime that research data is persisted server-side.
- **`.env`**: optional convenience, shell env vars always take precedence. Created during install, non-destructive merge on update (new vars appended, existing values never touched, deprecated vars flagged). Gitignored. On-disk secrets with `0o600` permissions. Users who prefer env-only auth can delete `.env`.
- **Logging**: errors only, no secrets, no telemetry.
- **`.gitignore`**: includes `.env` to prevent accidental commits.

---

## 8. Token/Cost Efficiency

- Claude as **thin orchestrator**, Gemini does heavy work
- **Two-phase cost**: pre-flight estimate + `usageMetadata` tracking (estimates, not guaranteed exact)
- **Context caching** (significant cost reduction (model-dependent))
- **Batch API** (currently documented at 50% cost reduction per docs)
- **Model routing**: cheapest capable model by default
- **File state tracking**: hash + MIME + expiry, avoids redundant uploads
- **Generator-based uploads**: memory stays bounded (not zero — framing/retry overhead exists)
- **Dry-run default**: prevents accidental cost
- **Lean install**: no docs/tests in installed skill → minimal context token usage
- **Large response guard**: media adapters (image/video/music) save output to file, return only path + metadata to stdout (prevents Claude Code token overflow). Text responses exceeding 50KB are saved to a stable, user-visible file path. Summary to stdout includes: the file path, the reason for truncation, and the response size. Never silently truncates.

---

## 9. Merge/Update Flow

1. Fetch latest release tag
2. Compare VERSION
3. Download to temp dir (same filesystem for atomic swap)
4. Verify SHA-256 checksums
5. Fail if mismatch
6. Back up to `~/.claude/skills/gemini.bak/`
7. Offer: overwrite / merge / skip
8. Merge: `difflib` (cross-platform)
9. Atomic swap: `os.replace()` (retry on Windows `PermissionError`)
10. Rollback on failure
11. User config always preserved

---

## 10. Acceptance Checklist

- [ ] `setup/install.py` works on macOS/Linux with Python 3.9+
- [ ] Readable error if Python < 3.9 (even on 2.7: no SyntaxError)
- [ ] `GEMINI_API_KEY` resolves (precedence: GOOGLE_API_KEY > GEMINI_API_KEY), clear error if missing
- [ ] API key via `x-goog-api-key` header, never in URL
- [ ] `/gemini text "hello"` generates text
- [ ] `/gemini image_gen "a cat" --execute` routes to official model ID from live list or pinned registry (never sends brand alias to API)
- [ ] `/gemini embed "text"` returns embedding
- [ ] `/gemini models` lists models with status
- [ ] `/gemini health` validates connectivity
- [ ] `/gemini refresh` diffs, shows review before write
- [ ] `setup/update.py` verifies checksums, atomic swap, rollback on failure
- [ ] Tests pass (`pytest` = dev dependency)
- [ ] 100% coverage on critical paths (auth, dispatch, sanitize, filelock, cost, state, errors)
- [ ] High coverage on adapters
- [ ] Test structure mirrors source (tests/core/, tests/adapters/, tests/scripts/, tests/integration/)
- [ ] API key never in output, traceback, log
- [ ] Config files: `0o700`/`0o600` permissions
- [ ] Mutating ops → dry-run default; cost-sensitive → explicit opt-in
- [ ] Post-response cost uses `usageMetadata` (labeled as estimate)
- [ ] Each adapter uses the documented API version (v1 where supported, v1beta where required)
- [ ] CI passes on Python 3.9, 3.11, 3.13
- [ ] GitHub Actions release workflow generates checksums.txt
- [ ] File upload: generator-based, bounded memory
- [ ] State/cost writes: atomic + file-locked
- [ ] Uploads > threshold: no full-file memory load
- [ ] Reused files: validated near expiry
- [ ] 504 DEADLINE_EXCEEDED handled with clear timeout error
- [ ] File Search store imports not treated as 48hr-expiring (persistent vs temporary distinction)
- [ ] macOS SSL certificate error caught with actionable fix message
- [ ] `/gemini abort` kills stuck process via PID file with start-marker token, handles stale PIDs
- [ ] Maps output: grounded answer → Sources: block → `- [title](uri-or-googleMapsUri) — Google Maps` per source → attribution line. Uses `uri` when present, else `googleMapsUri`.
- [ ] File Search store size warnings at documented limits
- [ ] Deep Research: polling resume uses interaction ID; stream resume requires interaction ID + last event ID
- [ ] Deep Research: runtime warning about server-side persistence (store=true, 55d paid / 1d free)
- [ ] Only operational files installed (no docs/tests)

---

## 11. Known Risks

- **Preview model churn**: IDs/surface may change. Registry is advisory; runtime probes.
- **Free tier limits**: model-specific limits. Router degrades on 429.
- **Gemini 3.1 pricing**: preview, may change.
- **File API**: 48hr/2GB/20GB. State tracks with lazy validation.
- **Live API**: excluded (WebSocket). Optional module later.
- **urllib limitations**: adequate for REST/SSE/chunked upload. Not WebSocket.
- **Python**: explicit prerequisite. Windows best-effort.
- **Registry drift**: advisory baseline + runtime probing + `refresh_capabilities.py`.
- **Update authenticity (TOP SECURITY LIMITATION)**: checksums verify integrity only, not origin authenticity. Compromised release channel = compromised update. Release signing (Sigstore/cosign) is the #1 future security task.
- **Windows permissions**: best-effort.
- **Cost estimates**: not guaranteed exact for preview/evolving pricing.
- **Interactions API**: beta, subject to breaking changes. `deep_research.py` uses it from day one. Churn risk documented.
- **Concurrent access**: file-locked, but edge cases possible under extreme parallelism.

---

## 12. Pseudocode Reference

**Path mapping (pseudocode uses short names, actual paths use subdirectories):**
| Short name | Actual path |
|-----------|-------------|
| `core/auth.py` | `core/auth/auth.py` |
| `core/sanitize.py` | `core/auth/sanitize.py` |
| `core/config.py` | `core/auth/config.py` |
| `core/client.py` | `core/infra/client.py` |
| `core/errors.py` | `core/infra/errors.py` |
| `core/filelock.py` | `core/infra/filelock.py` |
| `core/cost.py` | `core/infra/cost.py` |
| `core/state.py` | `core/state/` (split into file_state, store_state, session_state, identity) |
| `core/tool_state.py` | `core/routing/tool_state.py` |
| `core/router.py` | `core/routing/router.py` |
| `core/registry.py` | `core/routing/registry.py` |
| `core/cli/dispatch.py` | `core/cli/dispatch.py` |
| `adapters/text.py` | `adapters/generation/text.py` |
| `adapters/image_gen.py` | `adapters/media/image_gen.py` |
| `adapters/video_gen.py` | `adapters/media/video_gen.py` |
| `adapters/deep_research.py` | `adapters/experimental/deep_research.py` |
| `install.py` | `setup/install.py` |
| `update.py` | `setup/update.py` |
| `run_tests.sh` | `setup/run_tests.sh` |
| `requirements-dev.txt` | `setup/requirements-dev.txt` |
| `pytest.ini` | `setup/pytest.ini` |

### core/errors.py
```
class GeminiSkillError(Exception): base error
class AuthError(GeminiSkillError): API key missing or invalid
class ModelNotFoundError(GeminiSkillError): requested model doesn't exist
class CapabilityUnavailableError(GeminiSkillError): capability not supported
class CostLimitError(GeminiSkillError): daily cost limit exceeded
class APIError(GeminiSkillError): Gemini API returned an error

def classify_retry(status_code) -> Literal["retry", "no_retry", "timeout"]:  # from typing import Literal
    429, 503 → retry with backoff
    504 → timeout (one retry for idempotent reads)
    400, 401, 403, 404 → no_retry
    
def handle_error(error):
    if expected error: print clean message, no traceback
    if unexpected: sanitize traceback via sys.excepthook, then print
```

### core/filelock.py
```
class FileLock:
    __init__(path, timeout=5.0)
    __enter__(): acquire non-blocking lock (fcntl.LOCK_EX|LOCK_NB on POSIX, msvcrt on Windows)
        retry loop with tiny sleep until timeout
    __exit__(): release lock, always (even on exception)
    
    # Documented limitation: may not work on network filesystems
```

### core/sanitize.py
```
KEY_PATTERN = re.compile(r'AIza[0-9A-Za-z_-]{35}')

def sanitize(text): return KEY_PATTERN.sub('[REDACTED]', text)

def install_exception_hook():
    original_hook = sys.excepthook
    def safe_hook(type, value, tb):
        # sanitize traceback string before printing
        # call original_hook with sanitized output
    sys.excepthook = safe_hook

def safe_print(*args): print(sanitize(' '.join(str(a) for a in args)))

# Install hook on module import
install_exception_hook()
```

### core/auth.py
```
def parse_env_file(path) -> dict:
    for each line in file:
        skip blank lines, lines starting with #
        split on first '='
        trim whitespace from key and value
        strip matching outer quotes (" or ') from value
        if key not already in os.environ: set it

def resolve_key(env_dir=None) -> str:
    if env_dir: parse_env_file(env_dir / '.env')
    if GOOGLE_API_KEY in env: return it
    if GEMINI_API_KEY in env: return it
    raise AuthError("No API key found...")

def validate_key(key) -> bool:
    request = Request(f"{BASE_URL}/v1beta/models")
    request.add_header("x-goog-api-key", key)
    try: urlopen(request, timeout=10) → return True
    except HTTPError 401: raise AuthError
    except SSLCertVerificationError: raise with macOS-specific fix message
```

### core/config.py
```
@dataclass
class Config:
    default_model: str = "gemini-2.5-flash"
    prefer_preview_models: bool = False
    cost_limit_daily_usd: float = 5.00
    dry_run_default: bool = True
    output_dir: Optional[str] = None  # None = tempdir
    deep_research_timeout_seconds: int = 3600  # documented max: 60 min, capped at 3600

CONFIG_DIR = Path.home() / ".config" / "gemini-skill"
CONFIG_FILE = CONFIG_DIR / "config.json"

def load_config() -> Config:
    ensure_dir(CONFIG_DIR, mode=0o700)
    if CONFIG_FILE exists: read JSON, merge with defaults
    else: return defaults

def save_config(config):
    write to temp file, os.replace(), chmod 0o600
```

### core/client.py
```
BASE_URL = "https://generativelanguage.googleapis.com"

def api_call(endpoint, body=None, method="POST", api_version="v1beta", timeout=30):
    url = f"{BASE_URL}/{api_version}/{endpoint}"
    headers = {"x-goog-api-key": resolve_key(), "Content-Type": "application/json"}
    # NEVER put key in URL
    request = Request(url, data=json.dumps(body).encode() if body else None, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=timeout)
        return json.loads(response.read())
    except HTTPError as e:
        action = classify_retry(e.code)
        if action == "retry": exponential_backoff_retry(...)
        else: raise APIError with sanitized message

def stream_generate_content(model, body, api_version="v1beta", timeout=30):
    url = f"{BASE_URL}/{api_version}/models/{model}:streamGenerateContent?alt=sse"
    # chunked SSE reading with dead-connection guard

def create_interaction(body):
    return api_call("interactions", body)

def create_interaction_stream(body, timeout=60):
    stream_body = dict(body)
    stream_body["stream"] = True  # always injected — docs require stream=true for SSE
    url = f"{BASE_URL}/v1beta/interactions?alt=sse"
    # Returns parsed SSE events. Caller must aggregate content.delta events to reconstruct outputs.

def get_interaction(interaction_id):
    return api_call(f"interactions/{interaction_id}", method="GET")

def resume_interaction_stream(interaction_id, last_event_id, timeout=60):
    url = f"{BASE_URL}/v1beta/interactions/{interaction_id}?stream=true&last_event_id={last_event_id}&alt=sse"
    # resume interrupted stream
```

### core/state.py
```
FILES_STATE = CONFIG_DIR / "files.json"
STORES_STATE = CONFIG_DIR / "stores.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"

@dataclass
class DocumentIdentity:
    content_sha256: str
    mime_type: str
    source_path: Optional[str]  # absolute real path via Path.resolve()
    source_uri: Optional[str]

def compute_identity(file_path) -> DocumentIdentity:
    sha256 hash of file contents
    from core.infra.mime import guess_mime_for_path
    mime_type = guess_mime_for_path(file_path)  # shared helper, version-gated
    # Allow user override via --mime flag
    source_path = str(Path(file_path).resolve())

def get_cached_file_uri(identity) -> Optional[str]:
    with FileLock(FILES_STATE):
        load state, check if identity exists and not expired (UTC time.time())
        if near expiry: lazy validate via API (GET file metadata)
        return URI or None

def save_file_uri(identity, uri, expiry_time):
    with FileLock(FILES_STATE):
        load, update, atomic write

# Similar for File Search stores (stores.json) — persistent, no expiry
# Similar for sessions (sessions/<id>.json) — conversation history
```

### core/tool_state.py
```
def extract_tool_state(response_parts) -> list:
    """Preserve entire provider-returned parts that contain tool state.
    Treats id, tool_type, thought_signature, and any other fields as opaque.
    Returns the parts exactly as received for round-tripping."""
    return [part for part in parts if has_tool_state_fields(part)]

def inject_tool_state(request_contents, preserved_parts) -> list:
    """Merge preserved tool state parts back into the next request's contents."""
    # Append preserved parts exactly as-is
```

### core/cost.py
```
COST_FILE = CONFIG_DIR / "cost_today.json"

def estimate_cost(model, input_tokens, output_tokens, cached_tokens=0) -> float:
    pricing = registry.get_model(model).pricing
    return (input_tokens * pricing.input_per_1m / 1e6) + ...

def record_actual_cost(model, usage_metadata):
    actual = compute from usage_metadata fields
    with FileLock(COST_FILE):
        load today's total (UTC date key), add actual, atomic write
    return actual

def check_daily_limit(config) -> bool:
    with FileLock(COST_FILE):
        load today's total
    return total < config.cost_limit_daily_usd
```

### core/cli/dispatch.py
```
ALLOWED_COMMANDS = {
    "text": adapters.text,
    "multimodal": adapters.multimodal,
    "structured": adapters.structured,
    "embed": adapters.embeddings,
    "image_gen": adapters.image_gen,
    ...
}

def main(argv):
    if not argv: print help, exit
    command = argv[0]
    if command not in ALLOWED_COMMANDS: fail closed
    adapter = ALLOWED_COMMANDS[command]
    # parse remaining args with adapter's argparse
    # validate: paths exist, URLs look safe, file sizes within limits
    # enforce dry-run vs --execute
    # call adapter.run(**parsed_args)

# INVARIANT: never os.system(), never shell=True, never concatenate user text into shell commands
```

### core/registry.py
```
def load_models() -> dict:
    read registry/models.json, parse, return
    cache in memory (per-process)

def load_capabilities() -> dict:
    read registry/capabilities.json, parse, return

def get_model(model_id) -> dict:
    models = load_models()
    if model_id in models: return models[model_id]
    # try live probe: api_call("models/" + model_id, method="GET")
    raise ModelNotFoundError

def list_models() -> list: return all from registry + live probe cache
def list_capabilities() -> list: return all from capabilities.json
```

### core/router.py
```
def select_model(task_type, complexity="medium", user_override=None, config=None):
    if user_override: validate exists, return it
    
    if task_type == "embedding": return "gemini-embedding-2-preview"
    if task_type == "image_gen": return "gemini-3.1-flash-image-preview"
    if task_type == "video_gen": return "veo-3.1-generate-preview"
    if task_type == "music_gen": return "lyria-3-clip-preview"
    
    # text/chat/code/structured:
    if complexity == "high": return pro_model(config)
    if complexity == "low": return lite_model(config)
    return flash_model(config)  # default

def pro_model(config):
    if config.prefer_preview_models: return "gemini-3.1-pro-preview"
    return "gemini-2.5-pro"
# similar for flash_model, lite_model
```

### adapters/generation/text.py (uniform pattern for all adapters)
```
"""Text generation adapter for Gemini API.
Called by dispatch.py. Uses core/client.py for API access.
Supports multi-turn sessions via --session/--continue flags."""

def run(prompt, model=None, system=None, max_tokens=8192, temperature=1.0,
        session=None, continue_session=False, execute=False):
    model = model or router.select_model("text")
    
    # Build contents array
    if session or continue_session:
        contents = load_session(session_id)
        contents.append({"role": "user", "parts": [{"text": prompt}]})
    else:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
    
    body = {"contents": contents, "generationConfig": {...}}
    if system: body["systemInstruction"] = {"parts": [{"text": system}]}
    
    response = client.api_call(f"models/{model}:generateContent", body)
    
    # Extract text from response
    text = response["candidates"][0]["content"]["parts"][0]["text"]
    
    # Cost tracking
    cost.record_actual_cost(model, response.get("usageMetadata", {}))
    
    # Session: save updated history
    if session: save_session(session_id, contents + [response_content])
    
    # Large response guard
    if len(text) > 50_000:
        path = save_to_file(text)
        safe_print(f"Response saved to {path} ({len(text)} chars, truncation reason: exceeds 50KB stdout limit)")
    else:
        safe_print(text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(...)
    parser.add_argument("prompt")
    parser.add_argument("--model")
    parser.add_argument("--session")
    parser.add_argument("--continue", dest="continue_session", action="store_true")
    parser.add_argument("--execute", action="store_true")
    # ... parse and call run()
```

### adapters/media/image_gen.py
```
"""Image generation adapter. Nano Banana family.
Returns base64 inline → decode → save to file → return path + metadata."""

def run(prompt, model=None, execute=False, output_dir=None):
    if not execute:
        safe_print(f"[DRY RUN] Would generate image: {prompt}")
        return
    
    model = model or "gemini-3.1-flash-image-preview"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
    
    response = client.api_call(f"models/{model}:generateContent", body, api_version="v1beta")
    
    for part in response["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            image_bytes = base64.b64decode(part["inlineData"]["data"])
            mime = part["inlineData"]["mimeType"]
            ext = mime.split("/")[1]  # e.g., "png"
            
            output_path = create_output_file(f".{ext}", output_dir)
            Path(output_path).write_bytes(image_bytes)
            
            # Return absolute path + metadata only (NEVER raw bytes to stdout)
            safe_print(json.dumps({
                "path": str(Path(output_path).resolve()),
                "mime_type": mime,
                "size_bytes": len(image_bytes)
            }))

def create_output_file(suffix, output_dir=None):
    """Secure unique file creation — no overwrite/race risk from concurrent runs."""
    directory = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="gemini-skill-", suffix=suffix, dir=str(directory))
    os.close(fd)
    return Path(path).resolve()
```

### adapters/media/video_gen.py
```
"""Video generation via Veo. Long-running operation with polling."""

def run(prompt, model=None, execute=False, output_dir=None):
    if not execute:
        safe_print(f"[DRY RUN] Would generate video: {prompt}")
        return
    
    model = model or "veo-3.1-generate-preview"
    # Step 1: Submit long-running operation
    body = {"instances": [{"prompt": prompt}]}
    op = client.api_call(f"models/{model}:predictLongRunning", body, api_version="v1beta")
    operation_name = op["name"]
    
    # Step 2: Poll until done
    while True:
        status = client.api_call(operation_name, method="GET", api_version="v1beta")
        if status.get("done"): break
        time.sleep(10)
    
    # Step 3: Download video from URI
    # MANDATORY: verify exact REST response JSON path at implementation time
    # SDK equivalent: operation.response.generated_videos[0].video
    # The path below is a placeholder — confirm against live REST reference before shipping
    video_uri = extract_video_uri(status)  # implementation must verify actual JSON structure
    video_bytes = download_with_auth(video_uri)
    
    # Step 4: Save to file, return path
    output_path = create_output_file(".mp4", output_dir)
    Path(output_path).write_bytes(video_bytes)
    safe_print(json.dumps({"path": str(Path(output_path).resolve()), ...}))
```

### adapters/experimental/deep_research.py
```
"""Deep Research via Interactions API (not generateContent).
Requires background=true, polling for completion."""

def run(prompt, execute=False):
    if not execute:
        safe_print(f"[DRY RUN] Would start deep research: {prompt}")
        safe_print("WARNING: Deep Research uses the Interactions API with background execution. Interaction data may be stored server-side.")
        return
    
    safe_print("NOTE: Deep Research uses background Interactions (stored by default, 55d paid / 1d free tier).")
    
    # Uses Interactions API endpoint, not generateContent
    body = {"input": prompt, "agent": "deep-research-pro-preview-12-2025", "background": True}
    interaction = client.create_interaction(body)
    interaction_id = interaction["id"]
    
    # Poll until terminal state or client-side timeout
    start = time.time()
    max_poll = config.deep_research_timeout_seconds  # default 3600s (documented max: 60 min, most tasks ~20 min)
    while time.time() - start < max_poll:
        interaction = client.get_interaction(interaction_id)
        status = interaction.get("status")
        if status in ("completed", "failed", "cancelled"):
            break
        time.sleep(15)
    else:
        # Client-side timeout — research still running server-side
        safe_print(f"[POLL TIMEOUT] Research still in progress after {max_poll}s.")
        safe_print(f"Poll resume: /gemini deep_research --resume {interaction_id}")
        # Note: stream reconnection (if streaming was used) requires both interaction_id + last_event_id
        # The adapter stores both in session state for stream recovery
        return
    
    if status == "failed":
        raise APIError(f"Deep research failed: {interaction.get('error', 'unknown')}")
    if status == "cancelled":
        raise APIError("Deep research was cancelled")
    
    # For polling path: read result from interaction.outputs
    result_text = interaction["outputs"][-1]["text"]
    
    # NOTE: For streaming path (create_interaction_stream / resume_interaction_stream):
    # Final content is reconstructed exclusively from content.start / content.delta / content.stop events.
    # interaction.complete is metadata-only (outputs=None).
    # Adapter must maintain outputs_by_index accumulator keyed by stream index.
    # Persist for reconnection: interaction_id, last_event_id, partial accumulated outputs.
    # Large response guard applies
    ...
```

### scripts/gemini_run.py (2.7-safe launcher)
```
import sys
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(*sys.version_info[:2]))
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.cli.dispatch import main
main(sys.argv[1:])
```

### setup/install.py (2.7-safe launcher)
```
import sys
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(*sys.version_info[:2]))
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (parent of setup/)
from core.cli.install_main import main
main(sys.argv[1:])
```

### core/install_main.py
```
INSTALL_DIR = Path.home() / ".claude" / "skills" / "gemini"
SOURCE_DIR = Path(__file__).parent.parent.parent  # core/cli/install_main.py → core/cli → core → repo root
OPERATIONAL_FILES = ["SKILL.md", "VERSION"]
OPERATIONAL_DIRS = ["core", "adapters", "reference", "registry", "scripts"]
SETUP_FILES = ["setup/update.py"]  # included for in-place updates

def main(argv):
    if INSTALL_DIR.exists():
        choice = prompt_user("Skill already installed. [O]verwrite / [M]erge / [S]kip?")
        if choice == "S": return
        if choice == "M": merge_install()
        else: clean_install()
    else:
        clean_install()
    
    # Create .env from template if not exists
    env_file = INSTALL_DIR / ".env"
    if not env_file.exists():
        shutil.copy(SOURCE_DIR / ".env.example", env_file)
        os.chmod(str(env_file), 0o600)
    else:
        merge_env(env_file, SOURCE_DIR / ".env.example")
    
    # Run health check
    ...
```

### core/update_main.py
```
def main(argv):
    current_version = (INSTALL_DIR / "VERSION").read_text().strip()
    
    # Fetch latest release from GitHub API
    release = fetch_latest_release(REPO_URL)
    if release["tag"] <= current_version:
        print("Already up to date.")
        return
    
    # Download to temp dir (same filesystem for atomic swap)
    # Temp dir MUST be on same filesystem as INSTALL_DIR for atomic os.replace()
    temp_dir = INSTALL_DIR.parent / ".gemini-update-temp"
    download_and_extract(release["tarball_url"], dest=temp_dir)
    
    # Verify checksums from release's checksums.txt
    checksums = fetch_checksums(release)
    if not verify_checksums(temp_dir, checksums):
        print("ERROR: Checksum verification failed. Aborting.")
        return
    
    # Backup current
    backup_dir = INSTALL_DIR.with_suffix(".bak")
    shutil.copytree(INSTALL_DIR, backup_dir)
    
    # Offer choice
    choice = prompt_user("[O]verwrite / [M]erge / [S]kip?")
    
    try:
        if choice == "O": overwrite(temp_dir, INSTALL_DIR)
        elif choice == "M": merge(temp_dir, INSTALL_DIR)  # difflib-based
        
        # Merge .env (non-destructive)
        merge_env(INSTALL_DIR / ".env", temp_dir / ".env.example")
        
        print(f"Updated to {release['tag']}")
    except Exception:
        # Rollback
        shutil.rmtree(INSTALL_DIR)
        shutil.move(backup_dir, INSTALL_DIR)
        raise
```
