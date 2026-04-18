# Architecture — Transport

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Dual-backend transport: SDK primary + raw HTTP fallback, coordinator-driven, with
capability gating and shared response normalization.

---

## Dual-Backend Transport

The `core/transport/` package implements a **coordinator pattern** that routes requests to either the SDK backend (primary by default) or the raw HTTP backend (fallback).

![Dual-backend transport architecture](diagrams/architecture-dual-backend.svg)
<sub>Source: [`docs/diagrams/architecture-dual-backend.mmd`](diagrams/architecture-dual-backend.mmd) — regenerate with `bash scripts/render_diagrams.sh`</sub>

![Coordinator decision flow](diagrams/coordinator-decision-flow.svg)
<sub>Source: [`docs/diagrams/coordinator-decision-flow.mmd`](diagrams/coordinator-decision-flow.mmd)</sub>

The **backend priority matrix** shows how the two env flags resolve into primary/fallback assignment at coordinator build time:

![Backend priority matrix](diagrams/backend-priority-matrix.svg)
<sub>Source: [`docs/diagrams/backend-priority-matrix.mmd`](diagrams/backend-priority-matrix.mmd)</sub>

### Configuration

Two environment variables control backend selection:

- `GEMINI_IS_SDK_PRIORITY` (default `true`) — SDK is primary
- `GEMINI_IS_RAWHTTP_PRIORITY` (default `false`) — raw HTTP is fallback

Resolution rules:

- Both true → SDK wins (SDK primary, raw HTTP fallback)
- Both false → `ConfigError` (must enable at least one)
- One true → that backend is exclusive, no fallback

### Capability Registry

`SdkTransport` declares an explicit `_SUPPORTED_CAPABILITIES` frozenset (e.g., `{'text', 'multimodal', 'embeddings'}`). Capabilities like `maps`, `music_gen`, `computer_use`, `file_search` are NOT in the set because SDK v1.33.0 doesn't expose those surfaces. The coordinator routes them straight to raw HTTP without probing the SDK.

### Fallback Policy

When primary backend raises an exception, the coordinator consults `policy.is_fallback_eligible(exc)`:

- **Eligible for fallback**: `BackendUnavailableError`, transport/network errors, 429 (rate limit), 5xx, `ImportError`
- **NOT eligible** (re-raise immediately): `AuthError`, 4xx (except 429), `ValueError`/`TypeError`/`AssertionError`, `CostLimitError`

### Async Path

`client.aio.*` methods use `SdkAsyncTransport` and do NOT fall back to raw HTTP (raw HTTP is sync-only). Async adapters are detected by `IS_ASYNC = True` on the adapter module; `core/cli/dispatch.py` runs them via `asyncio.run(run_async(...))`.

### Unified Response

Both backends normalize responses to the same `GeminiResponse` dict shape via `core/transport/normalize.py`, so adapters are backend-agnostic. Neither adapters nor dispatch code know which backend ran.

---

## Adapter-to-Facade Interface

All adapters call the transport facade via `core.infra.client` (a shim re-exporting from `core.transport`). Three public functions are exposed:

| Function | Used by |
|---|---|
| `api_call` | 18 adapters (all except streaming) |
| `stream_generate_content` | `adapters/generation/streaming.py` only |
| `upload_file` | `adapters/data/files.py` only |

Two adapters intentionally bypass the facade:

- `adapters/generation/imagen.py` — calls `core.transport.sdk.client_factory.get_client()` directly; the Imagen response shape (`response.generated_images[i].image.image_bytes`) does not fit the `GeminiResponse` envelope
- `adapters/generation/live.py` — calls `get_client()` directly (`IS_ASYNC = True`); the Live session shape is SDK-only with no raw HTTP fallback

### The Lean-Router Pattern

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

### Adapter Lifecycle

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

---

## Policy Enforcement

The dispatcher enforces two tiers of safety:

### Tier 1: Mutating Operations (Dry-Run by Default)

Commands that modify server state require `--execute`:

- `files upload`, `files delete`
- `files download`
- `cache create`, `cache delete`
- `batch create`, `batch cancel`
- `file_search` (create, upload, delete)
- `image_gen`, `video_gen`, `music_gen`
- `deep_research`

Without `--execute`, these print a dry-run message and exit. This prevents accidental resource creation.

### Tier 2: Cost/Privacy-Sensitive Operations (Dispatcher-Managed Opt-In)

Commands that send data outside the user's control or incur cost are marked privacy-sensitive:

- `search` — sends queries to Google Search
- `maps` — sends location queries to Google Maps
- `computer_use` — can capture full desktop screenshots
- `deep_research` — long-running background task with server-side storage

When the user explicitly invokes one of these commands, the dispatcher auto-applies the internal privacy opt-in flag before policy enforcement. `--execute` remains only for mutating operations.

---

## Authentication

![Auth resolution precedence](diagrams/auth-resolution.svg)
<sub>Source: [`docs/diagrams/auth-resolution.mmd`](diagrams/auth-resolution.mmd)</sub>

API key resolution chain (first-match wins):

1. Shell environment variable: `GEMINI_API_KEY` (set by Claude Code from `~/.claude/settings.json`)
2. `.env` file at repo root: `GEMINI_API_KEY` (local-development only, via `env_dir=` fallback)
3. Error if neither found

The skill **does NOT honor `GOOGLE_API_KEY`** — `GEMINI_API_KEY` is canonical.

The API key is **only sent via HTTP header** (`x-goog-api-key`), never in URL query strings.

---

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

---

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

---

## Error Handling

- **API errors:** Wrapped in `APIError` with HTTP status code and server response
- **Auth failure:** Clear error message with remediation steps
- **Model not found:** Error lists available models
- **Network errors:** Exponential backoff retry (max 3 attempts)
- **Timeout:** Different handling for GET (retry) vs POST (fail)

All errors are printed to stderr via `safe_print()` (no ANSI injection).

---

## See also

- [architecture.md](architecture.md) — module map and runtime path
- [architecture-installer.md](architecture-installer.md) — install pipeline
- [design-patterns.md](design-patterns.md) — pattern catalog
- [system-design.md](system-design.md) — reliability, availability, trade-offs (forward ref — created in a later task)
