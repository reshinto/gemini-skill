# Source-Truth Snapshot — gemini-skill

Generated: 2026-04-18  
Branch: docs/overhaul  
Purpose: Ground-truth reference for downstream docs-audit tasks. Do not editorialize — record exact names, defaults, signatures.

---

## Commands

Source: `core/cli/dispatch.py` — `ALLOWED_COMMANDS` dict (lines 25–53), plus two meta-commands handled inline in `main()` (lines 78–84).

### Dispatch whitelist (23 commands)

| Command | Adapter module |
|---|---|
| `batch` | `adapters.data.batch` |
| `cache` | `adapters.data.cache` |
| `code_exec` | `adapters.tools.code_exec` |
| `computer_use` | `adapters.experimental.computer_use` |
| `deep_research` | `adapters.experimental.deep_research` |
| `embed` | `adapters.data.embeddings` |
| `file_search` | `adapters.data.file_search` |
| `files` | `adapters.data.files` |
| `function_calling` | `adapters.tools.function_calling` |
| `image_gen` | `adapters.media.image_gen` |
| `imagen` | `adapters.generation.imagen` |
| `live` | `adapters.generation.live` |
| `maps` | `adapters.tools.maps` |
| `multimodal` | `adapters.generation.multimodal` |
| `music_gen` | `adapters.media.music_gen` |
| `plan_review` | `adapters.generation.plan_review` |
| `search` | `adapters.tools.search` |
| `streaming` | `adapters.generation.streaming` |
| `structured` | `adapters.generation.structured` |
| `text` | `adapters.generation.text` |
| `token_count` | `adapters.data.token_count` |
| `video_gen` | `adapters.media.video_gen` |

### Meta-commands (handled in dispatch.main(), not in ALLOWED_COMMANDS)

| Token | Aliases | Behaviour |
|---|---|---|
| `help` | `--help`, `-h` | Prints usage + command list; exits 0 |
| `models` | — | Lists all models from registry; exits 0 |

**Note:** `core/routing/registry.py` defines a `Registry` class backed by JSON files (`registry/models.json`, `registry/capabilities.json`). There is no `COMMANDS` dict in `registry.py`; the Python import in Step 1 returned empty because the expected attribute does not exist. The authoritative command list is `ALLOWED_COMMANDS` in `dispatch.py`.

---

## Flags

Source: `core/cli/dispatch.py` and each adapter's `get_parser()`.

### Dispatch-layer policy flags (not passed to adapters)

Defined in `dispatch.py` lines 56–58. These are intercepted by the dispatcher before the adapter sees the argument list.

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--execute` | boolean | absent = dry-run | Required to proceed on mutating commands; checked via `--execute" not in args` |
| `--i-understand-privacy` | boolean | absent / auto-injected | Required (or auto-injected) for privacy-sensitive commands |
| `--continue` | boolean | — | Listed in `_BOOLEAN_FLAGS`; consumed by action-token extraction |
| `--model` | value (next token) | — | Listed in `_FLAGS_WITH_VALUES`; consumed by action-token extraction |
| `--session` | value (next token) | — | Listed in `_FLAGS_WITH_VALUES`; consumed by action-token extraction |

### Per-adapter flags (from each adapter's `get_parser()`)

#### `text` (`adapters/generation/text.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Text prompt to send |
| `--system` | — | str | `None` | System instruction |
| `--max-tokens` | — | int | — | Max output tokens |
| `--temperature` | — | float | — | Sampling temperature |

#### `multimodal` (`adapters/generation/multimodal.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Text prompt accompanying the media |
| `--file` | — | append | — | File path(s); repeatable |
| `--mime` | — | str | `None` | Override MIME type |

#### `streaming` (`adapters/generation/streaming.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Text prompt |

#### `structured` (`adapters/generation/structured.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Text prompt |
| `--schema` | — | str | required | JSON schema |

#### `plan_review` (`adapters/generation/plan_review.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `proposal` | — | positional str | nargs=`?` | Plan proposal (optional) |
| `--thinking` | — | choices | — | Enable/disable thinking (`on`/`off`) |

#### `imagen` (`adapters/generation/imagen.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Image generation prompt |
| `--num-images` | — | `_positive_int` | — | Number of images to generate |
| `--aspect-ratio` | — | str | `None` | Aspect ratio |
| `--output-dir` | — | str | `None` | Output directory |

#### `live` (`adapters/generation/live.py`, IS_ASYNC=True)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `prompt` | — | positional str | — | Initial prompt for Live session |
| `--modality` | — | str | `TEXT` | Output modality |

#### `embed` (`adapters/data/embeddings.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `text` | — | positional str | — | Text to embed |
| `--task-type` | — | str | `None` | Embedding task type |

#### `token_count` (`adapters/data/token_count.py`)

| Flag | Short | Type/Action | Default | Description |
|---|---|---|---|---|
| `text` | — | positional str | — | Text to count tokens for |

#### `files` (`adapters/data/files.py`)

Subcommands: `upload`, `get`, `list`, `delete`, `download`

| Subcommand | Flag | Default | Description |
|---|---|---|---|
| `upload` | `path` (positional) | — | Path to file |
| `upload` | `--mime` | `None` | Override MIME type |
| `upload` | `--display-name` | `None` | Display name |
| `get` | `name` (positional) | — | File resource name |
| `list` | — | — | No extra flags |
| `delete` | `name` (positional) | — | File resource name |
| `download` | `name` (positional) | — | File resource name |
| `download` | `out_path` (positional) | — | Local write path |

#### `cache` (`adapters/data/cache.py`)

Subcommands: `create`, `get`, `list`, `delete`

| Subcommand | Flag | Default | Description |
|---|---|---|---|
| `create` | `content` (positional) | — | Content to cache |
| `create` | `--ttl` | `3600s` | Time-to-live |
| `get` | `name` (positional) | — | Cache resource name |
| `list` | — | — | No extra flags |
| `delete` | `name` (positional) | — | Cache resource name |

#### `batch` (`adapters/data/batch.py`)

Subcommands: `create`, `get`, `list`, `cancel`

| Subcommand | Flag | Required | Description |
|---|---|---|---|
| `create` | `--src` | yes | Source file URI (JSONL) |
| `create` | `--dest` | yes | Destination file URI |
| `get` | `name` (positional) | — | Batch job resource name |
| `list` | — | — | No extra flags |
| `cancel` | `name` (positional) | — | Batch job resource name |

#### `file_search` (`adapters/data/file_search.py`)

Subcommands: `create`, `upload`, `query`, `list`, `delete`

| Subcommand | Flag | Required | Description |
|---|---|---|---|
| `create` | `name` (positional) | — | Display name for the store |
| `upload` | `store` (positional) | — | Store resource name |
| `upload` | `file_uri` (positional) | — | Gemini file URI to import |
| `query` | `prompt` (positional) | — | Search query |
| `query` | `--store` | yes | Store resource name |
| `list` | — | — | No extra flags |
| `delete` | `name` (positional) | — | Store resource name |

#### `function_calling` (`adapters/tools/function_calling.py`)

| Flag | Required | Description |
|---|---|---|
| `prompt` (positional) | — | Text prompt |
| `--tools` | yes | Tools JSON |

#### `code_exec` (`adapters/tools/code_exec.py`)

| Flag | Description |
|---|---|
| `prompt` (positional) | Prompt (may include code) |

#### `search` (`adapters/tools/search.py`)

| Flag | Action | Description |
|---|---|---|
| `prompt` (positional) | — | Text prompt |
| `--show-grounding` | store_true | Emit grounding metadata as JSON |

#### `maps` (`adapters/tools/maps.py`)

| Flag | Description |
|---|---|
| `prompt` (positional) | Text prompt |

#### `image_gen` (`adapters/media/image_gen.py`)

| Flag | Default | Description |
|---|---|---|
| `prompt` (positional) | — | Image generation prompt |
| `--output-dir` | `None` | Output directory |
| `--aspect-ratio` | `None` | Aspect ratio |
| `--image-size` | `None` | Image size |

#### `video_gen` (`adapters/media/video_gen.py`)

| Flag | Type | Default | Description |
|---|---|---|---|
| `prompt` (positional) | — | — | Video generation prompt |
| `--output-dir` | str | `None` | Output directory |
| `--poll-interval` | int | — | Poll interval seconds |
| `--max-wait` | int | — | Maximum wait seconds |

#### `music_gen` (`adapters/media/music_gen.py`)

| Flag | Default | Description |
|---|---|---|
| `prompt` (positional) | — | Music generation prompt |
| `--output-dir` | `None` | Output directory |

#### `computer_use` (`adapters/experimental/computer_use.py`)

| Flag | Description |
|---|---|
| `prompt` (positional) | Task description for the model |

#### `deep_research` (`adapters/experimental/deep_research.py`)

| Flag | Type | Default | Description |
|---|---|---|---|
| `prompt` (positional) | — | — | Research query |
| `--resume` | str | `None` | Resume token |
| `--max-wait` | int | — | Maximum wait seconds |

---

## Models

Source: `registry/models.json`

12 models registered. Families: Gemini, Veo, Lyria, Imagen.

| Model ID | Display Name | Status | api_version | Capabilities | input/1M | output/1M | cached/1M |
|---|---|---|---|---|---|---|---|
| `gemini-2.5-flash` | Gemini 2.5 Flash | stable | v1beta | text, multimodal, structured, streaming, function_calling, code_exec, search, cache, token_count | $0.15 | $0.60 | $0.0375 |
| `gemini-2.5-pro` | Gemini 2.5 Pro | stable | v1beta | text, multimodal, structured, streaming, function_calling, code_exec, search, cache, token_count | $1.25 | $10.00 | $0.3125 |
| `gemini-2.5-flash-lite` | Gemini 2.5 Flash Lite | stable | v1beta | text, multimodal, streaming, file_search, token_count | $0.075 | $0.30 | $0.01875 |
| `gemini-embedding-2-preview` | Gemini Embedding 2 Preview | preview | v1beta | embed | $0.00 | $0.00 | $0.00 |
| `gemini-3-flash-preview` | Gemini 3 Flash Preview | preview | v1beta | text, multimodal, structured, streaming, function_calling, code_exec, search, maps, file_search, computer_use, token_count | $0.15 | $0.60 | $0.0375 |
| `gemini-3.1-flash-image-preview` | Gemini 3.1 Flash Image Preview | preview | v1beta | image_gen | $0.15 | $0.60 | $0.0375 |
| `gemini-3.1-pro-preview` | Gemini 3.1 Pro Preview | preview | v1beta | text, multimodal, structured, streaming, function_calling, code_exec, search, token_count | $1.25 | $10.00 | $0.3125 |
| `gemini-2.5-computer-use-preview-10-2025` | Gemini 2.5 Computer Use Preview | preview | v1beta | computer_use | $1.25 | $10.00 | $0.3125 |
| `gemini-live-2.5-flash-preview` | Gemini Live 2.5 Flash Preview | preview | v1beta | live | $0.15 | $0.60 | $0.0375 |
| `imagen-3.0-generate-002` | Imagen 3.0 Generate | preview | v1beta | imagen | $0.00 | $0.00 | $0.00 |
| `veo-3.1-generate-preview` | Veo 3.1 Generate Preview | preview | v1beta | video_gen | $0.00 | $0.00 | $0.00 |
| `lyria-3-clip-preview` | Lyria 3 Clip Preview | preview | v1beta | music_gen | $0.00 | $0.00 | $0.00 |

### By status

- **stable (3):** gemini-2.5-flash, gemini-2.5-pro, gemini-2.5-flash-lite
- **preview (9):** gemini-embedding-2-preview, gemini-3-flash-preview, gemini-3.1-flash-image-preview, gemini-3.1-pro-preview, gemini-2.5-computer-use-preview-10-2025, gemini-live-2.5-flash-preview, imagen-3.0-generate-002, veo-3.1-generate-preview, lyria-3-clip-preview

### By family

- **Gemini:** gemini-2.5-flash, gemini-2.5-pro, gemini-2.5-flash-lite, gemini-embedding-2-preview, gemini-3-flash-preview, gemini-3.1-flash-image-preview, gemini-3.1-pro-preview, gemini-2.5-computer-use-preview-10-2025, gemini-live-2.5-flash-preview
- **Imagen:** imagen-3.0-generate-002
- **Veo:** veo-3.1-generate-preview
- **Lyria:** lyria-3-clip-preview

---

## Env Keys

Source: `core/infra/runtime_env.py` (lines 29–41) and `core/auth/auth.py` (lines 5, 12, 71–76).

### CANONICAL_ENV_DEFAULTS (dict, line 29)

| Key | Default Value | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | `""` | Gemini API authentication key |
| `GEMINI_IS_SDK_PRIORITY` | `"true"` | Use google-genai SDK backend when available |
| `GEMINI_IS_RAWHTTP_PRIORITY` | `"false"` | Force raw HTTP backend |
| `GEMINI_LIVE_TESTS` | `"0"` | Enable live (network) tests |

### CANONICAL_ENV_KEYS (tuple, line 36)

Same four keys: `GEMINI_API_KEY`, `GEMINI_IS_SDK_PRIORITY`, `GEMINI_IS_RAWHTTP_PRIORITY`, `GEMINI_LIVE_TESTS`.

### Resolution precedence (lowest → highest, from `resolve_runtime_env`)

1. `~/.claude/settings.json` (`env` block)
2. `./.claude/settings.json` (`env` block)
3. `./.claude/settings.local.json` (`env` block)
4. `./.env` (key=value format)
5. Existing process environment (`os.environ`)

### Explicitly NOT honored

`GOOGLE_API_KEY` — documented in `core/auth/auth.py` lines 12: "The skill deliberately does NOT honor `GOOGLE_API_KEY`."

---

## Installer

Source: `core/cli/installer/payload.py` and `core/cli/install_main.py`.

### payload.py — install payload manifest

| Constant | Value |
|---|---|
| `INSTALL_ROOT_FILES` | `("SKILL.md", "VERSION")` |
| `INSTALL_DIRS` | `("core", "adapters", "reference", "registry", "scripts")` |
| `INSTALL_SETUP_FILES` | `("setup/update.py", "setup/requirements.txt")` |
| `INSTALL_COPY_IGNORE_PATTERNS` | `("__pycache__", "*.pyc")` |

Total payload entries returned by `iter_install_payload_paths()`: 9 paths (2 root files + 5 dirs + 2 setup files).

### install_main.py — key constants

| Constant | Value | Purpose |
|---|---|---|
| `_CHECKSUMS_FILENAME` | `".checksums.json"` | SHA-256 integrity manifest filename written into install dir |
| `_CHECKSUMS_EXCLUDED_DIRS` | `frozenset({".venv", "__pycache__"})` | Dirs excluded from checksum manifest |
| `_DEFAULT_ENV_KEYS` | alias of `CANONICAL_ENV_DEFAULTS` | Env defaults merged into `~/.claude/settings.json` |
| `_PRESERVE_ON_OVERWRITE` | `frozenset({".venv", ".env"})` | Entries preserved when overwriting an existing install |

### install_main.py — install flow (from `main()` docstring, lines 70–88)

1. Resolve source + install directories.
2. If install dir exists: prompt `[O]verwrite / [S]kip?`.
3. Copy operational files (`copy_install_payload`).
4. Write SHA-256 integrity manifest (`.checksums.json`).
5. Create skill-local venv at `<install_dir>/.venv`; pip-install `setup/requirements.txt`.
6. Migrate legacy `.env` → `settings.json`; prompt for `GEMINI_API_KEY`; merge defaults into `~/.claude/settings.json`.

### install_main.py — accepted CLI flags

| Flag | Short | Behaviour |
|---|---|---|
| `--yes` | `-y` | Skip interactive prompts (non-interactive / CI mode) |

### install destination

`~/.claude/skills/gemini/` (from `_get_install_dir()`, line 302).

---

## Adapter Imports

Source: `grep -rnE "from core\.transport import|from core\.infra\.client import" adapters/`

All 20 adapter files import from `core.infra.client`. No adapter uses `core.transport`. The coordinator facade is `core.infra.client`.

| Adapter file | Import |
|---|---|
| `adapters/data/batch.py` | `from core.infra.client import api_call` |
| `adapters/data/cache.py` | `from core.infra.client import api_call` |
| `adapters/data/embeddings.py` | `from core.infra.client import api_call` |
| `adapters/data/file_search.py` | `from core.infra.client import api_call` |
| `adapters/data/files.py` | `from core.infra.client import api_call, upload_file` |
| `adapters/data/token_count.py` | `from core.infra.client import api_call` |
| `adapters/experimental/computer_use.py` | `from core.infra.client import api_call` |
| `adapters/experimental/deep_research.py` | `from core.infra.client import api_call` |
| `adapters/generation/multimodal.py` | `from core.infra.client import api_call` |
| `adapters/generation/plan_review.py` | `from core.infra.client import api_call` |
| `adapters/generation/streaming.py` | `from core.infra.client import stream_generate_content` |
| `adapters/generation/structured.py` | `from core.infra.client import api_call` |
| `adapters/generation/text.py` | `from core.infra.client import api_call` |
| `adapters/media/image_gen.py` | `from core.infra.client import api_call` |
| `adapters/media/music_gen.py` | `from core.infra.client import api_call` |
| `adapters/media/video_gen.py` | `from core.infra.client import api_call` |
| `adapters/tools/code_exec.py` | `from core.infra.client import api_call` |
| `adapters/tools/function_calling.py` | `from core.infra.client import api_call` |
| `adapters/tools/maps.py` | `from core.infra.client import api_call` |
| `adapters/tools/search.py` | `from core.infra.client import api_call` |

**SDK-direct adapters (not in grep output):** `adapters/generation/imagen.py` and `adapters/generation/live.py` intentionally bypass `core.infra.client` and call `get_client()` from `core.transport.sdk.client_factory` directly. Both adapters document this explicitly: the Imagen response shape (`response.generated_images[i].image.image_bytes`) and the Live session shape do not fit the `GeminiResponse` dict envelope that the transport normalize layer is built around, and both capabilities are SDK-only with no raw HTTP fallback.

| Adapter file | Import |
|---|---|
| `adapters/generation/imagen.py` | `from core.transport.sdk.client_factory import get_client` (direct SDK) |
| `adapters/generation/live.py` | `from core.transport.sdk.client_factory import get_client` (direct SDK, IS_ASYNC=True) |

### Unique facade functions used

| Function | Used by |
|---|---|
| `api_call` | 18 adapters (all except streaming) |
| `upload_file` | `adapters/data/files.py` only |
| `stream_generate_content` | `adapters/generation/streaming.py` only |

---

## Investigation Notes

1. **`registry.py` has no `COMMANDS` dict.** The Python import `core.routing.registry.COMMANDS` fails silently (no such attribute). The module defines a `Registry` class backed by JSON. The canonical command list is `ALLOWED_COMMANDS` in `core/cli/dispatch.py`.

2. **`dispatch.py` has no `add_argument` calls.** There are no shared argparse flags at the dispatcher level. Policy flags (`--execute`, `--i-understand-privacy`) are handled via raw `in args` string checks, not argparse. Per-adapter flags are defined in each adapter's `get_parser()`.

3. **`imagen` and `live` adapters intentionally bypass `core.infra.client`.** Both use `core.transport.sdk.client_factory.get_client()` directly. Reason documented in each adapter's module docstring: the response shapes (Imagen image bytes; Live async session) do not fit the `GeminiResponse` envelope, and both are SDK-only with no raw HTTP fallback. `live` also declares `IS_ASYNC = True` — dispatched via `asyncio.run(adapter.run_async(**kwargs))`.

4. **`gemini-embedding-2-preview` pricing is $0.00** — recorded as-is from `registry/models.json`. This may be intentional (free tier) or a placeholder.
