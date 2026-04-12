# Architecture

**Last Updated:** 2026-04-13

## System Overview

The gemini-skill is a Claude Code skill providing REST API access to Google Gemini. It uses a modular adapter architecture with a policy-enforcing dispatcher.

```
SKILL.md (Claude Code launcher)
    ↓
scripts/gemini_run.py (2.7-safe launcher, version check)
    ↓
core/cli/dispatch.py (policy boundary: whitelist, flags, enforcement)
    ↓
adapters/ (19 adapters: generation, data, tools, media, experimental)
    ↓
core/routing/router.py (model selection: complexity tree + specialty tasks)
    ↓
core/infra/client.py (HTTP/REST using urllib, x-goog-api-key header)
    ↓
Gemini API (v1 and v1beta endpoints)
```

## Directory Layout

```
.
├── SKILL.md                  # Claude Code skill definition (launcher metadata)
├── scripts/
│   └── gemini_run.py         # Entry point (Python 3.9+ check, dispatches to dispatch.py)
├── setup/
│   ├── install.py            # Install to ~/.claude/skills/gemini/
│   └── update.py             # Sync operational files (no docs, no tests)
├── core/
│   ├── cli/
│   │   ├── dispatch.py       # Subcommand whitelist, policy enforcement
│   │   ├── install_main.py   # Setup/install handler
│   │   ├── update_main.py    # Update/sync handler
│   │   └── health_main.py    # Health check utility
│   ├── auth/
│   │   └── auth.py           # Resolve API key (shell env > .env > error)
│   ├── infra/
│   │   ├── client.py         # HTTP client (urllib, retry, SSE, multipart)
│   │   ├── config.py         # Load config (prefer_preview_models, output_dir)
│   │   ├── cost.py           # Track cost with file locking + atomic writes
│   │   ├── errors.py         # API errors, custom exceptions
│   │   ├── mime.py           # MIME type detection and validation
│   │   ├── sanitize.py       # Safe print (no ANSI injection)
│   │   ├── timeouts.py       # Timeout constants and helpers
│   │   ├── filelock.py       # Cross-platform file locking (fcntl/msvcrt)
│   │   └── atomic_write.py   # Atomic file writes (os.replace + retry)
│   ├── routing/
│   │   ├── router.py         # Model selection logic
│   │   └── registry.py       # Load model registry (JSON) from registry/
│   ├── state/
│   │   ├── session_state.py  # Multi-turn conversation storage
│   │   ├── file_state.py     # Files API tracking (48hr expiry)
│   │   └── store_state.py    # File Search store state
│   └── adapter/
│       ├── helpers.py        # Shared: build_base_parser, emit_output, etc.
│       └── contract.py       # Adapter interface (get_parser, run)
├── adapters/
│   ├── generation/
│   │   ├── text.py           # Text generation + sessions
│   │   ├── multimodal.py     # Files + text (inline base64)
│   │   ├── structured.py     # JSON schema output
│   │   └── streaming.py      # SSE streaming
│   ├── data/
│   │   ├── embeddings.py     # Vector embeddings
│   │   ├── token_count.py    # Token counting
│   │   ├── files.py          # Files API (upload/list/get/delete)
│   │   ├── cache.py          # Context caching (create/list/get/delete)
│   │   ├── batch.py          # Batch jobs (create/list/get/cancel)
│   │   └── file_search.py    # Hosted RAG (create/upload/query/list/delete)
│   ├── tools/
│   │   ├── function_calling.py  # Tool/function calling
│   │   ├── code_exec.py         # Sandboxed code execution
│   │   ├── search.py            # Google Search grounding
│   │   └── maps.py              # Google Maps grounding
│   ├── media/
│   │   ├── image_gen.py      # Image generation (Nano Banana)
│   │   ├── video_gen.py      # Video generation (Veo)
│   │   └── music_gen.py      # Music generation (Lyria 3)
│   └── experimental/
│       ├── computer_use.py   # Computer use (preview)
│       └── deep_research.py  # Deep Research via Interactions API
├── registry/
│   ├── models.json           # Available models and capabilities
│   └── capabilities.json     # Feature flags, deprecations
├── docs/
│   ├── architecture.md       # This file
│   ├── how-it-works.md       # Execution trace
│   ├── install.md            # Setup instructions
│   ├── commands.md           # Command index
│   ├── capabilities.md       # Feature overview
│   ├── model-routing.md      # Router decision tree
│   ├── security.md           # Threat model
│   ├── usage.md              # Getting started
│   ├── testing.md            # Test suite
│   ├── python-guide.md       # Python 3.9+ choices
│   ├── contributing.md       # Extension guide
│   └── update-sync.md        # Install mechanism
├── reference/
│   ├── index.md              # Command reference index
│   ├── text.md               # Per-command docs (18 files)
│   ├── multimodal.md
│   └── ... (one per command)
├── tests/                    # 574 tests, 100% coverage
├── .coverage                 # Coverage data
└── VERSION                   # Semantic version
```

## The Lean-Router Pattern

The `dispatch.py` module implements a **policy-enforcing dispatcher** that pre-approves certain operations:

1. **Whitelist by default:** Only commands in `ALLOWED_COMMANDS` can run.
2. **Per-adapter parser:** Each adapter defines its own argument parser (via `get_parser()`).
3. **Centralized enforcement:**
   - Flag validation
   - Mutating operation gating (`--execute` required)
   - Dry-run mode for safety
   - Input sanitization

The dispatcher is intentionally **lean** — it doesn't implement business logic. Instead:
- Adapters are **single-responsibility:** one adapter per command.
- Each adapter has a `get_parser()` and `run(**kwargs)` function.
- Adapters are imported dynamically via `importlib.import_module()`.
- The router (`core/routing/router.py`) handles model selection, not dispatch.

This design makes it easy to add new commands: implement a new adapter, add an entry to `ALLOWED_COMMANDS`, and you're done.

## Adapter Lifecycle

1. **Dispatcher invokes adapter:**
   ```python
   adapter_module = importlib.import_module(ALLOWED_COMMANDS[command])
   parser = adapter_module.get_parser()
   args = parser.parse_args(remaining)
   adapter_module.run(**vars(args))
   ```

2. **Adapter execution:**
   - Load config (auth, preferences)
   - Resolve model via router
   - Validate inputs
   - Call `api_call()` (HTTP wrapper)
   - Emit output or save to file

3. **Output handling:**
   - Text < 50KB → stdout
   - Text >= 50KB → file (return path only)
   - Media → always file
   - JSON → pretty-printed to stdout

## Model Routing

The `Router` class implements a two-tier decision tree:

1. **Specialty tasks** route to dedicated models:
   - `embed` → `gemini-embedding-2-preview`
   - `image_gen` → `gemini-3.1-flash-image-preview` (Nano Banana 2)
   - `video_gen` → `veo-3.1-generate-preview`
   - `music_gen` → `lyria-3-clip-preview`
   - `computer_use` → Computer-use specialist
   - `file_search`, `maps` → specialized endpoints

2. **General tasks** (text, multimodal, code_exec, etc.) use complexity-based routing:
   - **High complexity:** `gemini-2.5-pro` (reasoning)
   - **Medium complexity:** `gemini-2.5-flash` (default, balanced)
   - **Low complexity:** `gemini-2.5-flash-lite` (fast, cheap)

3. **Preview preference** (`prefer_preview_models=true` in config):
   - High complexity → `gemini-3.1-pro-preview` (latest features, may break)
   - Medium/Low → stable Flash models

4. **User override** (`--model MODEL`):
   - Validated against the registry
   - Skips complexity check entirely

See `docs/model-routing.md` for detailed decision tree.

## State Management

Three persistent state stores (all with atomic writes + file locking):

1. **Sessions** (`~/.config/gemini-skill/sessions/<id>.json`)
   - Multi-turn conversation history
   - Used by `text`, `streaming`, and other chat-like commands

2. **File state** (`~/.config/gemini-skill/files.json`)
   - Tracks uploaded files from the Files API
   - 48-hour expiry (matches Gemini API behavior)
   - Atomic updates prevent data loss under concurrent access

3. **Store state** (`~/.config/gemini-skill/stores.json`)
   - File Search store metadata (persistent, no expiry)

Cost tracking is per-day, stored in `~/.config/gemini-skill/cost_today.json` (resets at UTC midnight).

## Authentication

API key resolution chain (first-match wins):

1. Shell environment variable: `GOOGLE_API_KEY` or `GEMINI_API_KEY`
2. `.env` file in the installed skill directory: `~/.claude/skills/gemini/.env`
3. Error if not found

The API key is **only sent via HTTP header** (`x-goog-api-key`), never in URL query strings.

## Policy Enforcement

The dispatcher enforces two tiers of safety:

### Tier 1: Mutating Operations (Dry-Run by Default)

Commands that modify server state require `--execute`:

- `files upload`, `files delete`
- `cache create`, `cache delete`
- `batch create`, `batch cancel`
- `file_search` (create, upload, delete)
- `image_gen`, `video_gen`, `music_gen`
- `deep_research`

Without `--execute`, these print a dry-run message and exit. This prevents accidental resource creation.

### Tier 2: Cost/Privacy-Sensitive Operations (Explicit Opt-In)

Commands that send data outside the user's control or incur cost require explicit opt-in:

- `search` — sends queries to Google Search
- `maps` — sends location queries to Google Maps
- `computer_use` — can capture full desktop screenshots
- `deep_research` — long-running background task with server-side storage

These are non-mutating but flagged in `SKILL.md` as requiring caution. The `--execute` flag serves double duty for privacy-sensitive ops.

## Error Handling

- **API errors:** Wrapped in `APIError` with HTTP status code and server response
- **Auth failure:** Clear error message with remediation steps
- **Model not found:** Error lists available models
- **Network errors:** Exponential backoff retry (max 3 attempts)
- **Timeout:** Different handling for GET (retry) vs POST (fail)

All errors are printed to stderr via `safe_print()` (no ANSI injection).

## Dependencies

**Runtime:**
- Python 3.9+ standard library only
- No third-party packages

**Build/Development:**
- pytest, coverage (for testing)
- ruff (linting)
- jsdoc2md, madge (optional: docs generation)

**Deployment:**
- Install script copies operational files only (no tests, no docs, no .git)
- Install destination: `~/.claude/skills/gemini/` (personal) or `.claude/skills/gemini/` (project)

## File Locking and Atomic Writes

The skill uses platform-agnostic file locking to prevent data corruption under concurrent access (Claude Code can parallelize tool calls):

- **POSIX (macOS/Linux):** `fcntl.flock()`
- **Windows:** `msvcrt.locking()`

Atomic writes use `os.replace()` with retry logic (catching `PermissionError` from antivirus scanners on Windows).

This ensures that if Claude Code invokes `gemini` twice in parallel, state files don't get corrupted.

## Key Design Principles

1. **Fail closed:** Ambiguity or missing data → error. Never proceed silently.
2. **Stdlib only:** No external dependencies at runtime.
3. **Policy boundary:** Dispatcher enforces rules; adapters implement features.
4. **Dry-run by default:** Mutations require `--execute` flag.
5. **Atomic state:** All reads/writes use file locking and atomic swaps.
6. **Layered auth:** Shell env > .env > error (shell always wins).
7. **Lean routers:** Model selection is separate from dispatch.
8. **Modular adapters:** Each command is one file; easy to extend.
