# Commands

**Last Updated:** 2026-04-14

A human-facing index of all gemini-skill commands, organized by capability family.

For detailed usage, flags, and examples, see the per-command reference files under `/reference/`.

## Text Generation

Basic text and conversation commands.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `text` | Single-turn and multi-turn text generation | [text.md](../reference/text.md) |
| `streaming` | Stream text output as it generates | [streaming.md](../reference/streaming.md) |

## Multimodal Input

Accept images, PDFs, audio, video, and URLs alongside text.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `multimodal` | Process files (images, PDFs, audio, video) with text | [multimodal.md](../reference/multimodal.md) |

## Structured Output

Generate JSON and constrained output.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `structured` | Generate JSON schema-constrained output | [structured.md](../reference/structured.md) |

## Data & Embeddings

Search, embeddings, and token counting.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `embed` | Generate vector embeddings for semantic search | [embed.md](../reference/embed.md) |
| `token_count` | Count tokens in a prompt before sending | [token_count.md](../reference/token_count.md) |

## Tool Use

Code execution and function calling.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `function_calling` | Invoke tools and functions via the model | [function_calling.md](../reference/function_calling.md) |
| `code_exec` | Execute Python code in Gemini's sandbox | [code_exec.md](../reference/code_exec.md) |

## Grounding

Ground responses in real-time web and map data.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `search` | Ground text in Google Search results (privacy-sensitive) | [search.md](../reference/search.md) |
| `maps` | Ground text in Google Maps data (privacy-sensitive) | [maps.md](../reference/maps.md) |

## File Management

Upload and manage files via the Files API.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `files` | Upload/list/get/delete files | [files.md](../reference/files.md) |

## Caching & Batch

Context caching and batch processing.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `cache` | Create/list/get/delete context caches | [cache.md](../reference/cache.md) |
| `batch` | Submit and manage batch jobs | [batch.md](../reference/batch.md) |

## File Search (RAG)

Host documents in File Search for semantic retrieval.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `file_search` | Create/manage hosted RAG (File Search) | [file_search.md](../reference/file_search.md) |

## Media Generation

Generate images, videos, and music (preview, requires `--execute`).

| Command | Purpose | Reference |
|---------|---------|-----------|
| `image_gen` | Generate images using Nano Banana | [image_gen.md](../reference/image_gen.md) |
| `video_gen` | Generate videos using Veo | [video_gen.md](../reference/video_gen.md) |
| `music_gen` | Generate music using Lyria 3 (30s max) | [music_gen.md](../reference/music_gen.md) |

## Advanced / Experimental

Specialized and preview-stage capabilities.

| Command | Purpose | Reference |
|---------|---------|-----------|
| `computer_use` | Enable model to see and control your screen (preview, privacy-sensitive) | [computer_use.md](../reference/computer_use.md) |
| `deep_research` | Conduct multi-step research via Interactions API | [deep_research.md](../reference/deep_research.md) |

## Utility

System commands (not adapters).

| Command | Purpose |
|---------|---------|
| `help` | List all commands |
| `models` | List available models from registry |

---

## Command Categories

### By safety level

**Safe (read-only, no special flags):**
- `text`, `streaming`, `multimodal`, `structured`
- `embed`, `token_count`, `function_calling`, `code_exec`

**Mutating (require `--execute`):**
- `files upload`, `files delete`
- `files download`
- `cache create`, `cache delete`
- `batch create`, `batch cancel`
- `file_search` (create, upload, delete)
- `image_gen`, `video_gen`, `music_gen`
- `deep_research`

**Privacy-sensitive (dispatcher auto-applies internal opt-in):**
- `search` — sends queries to Google Search
- `maps` — sends location queries to Google Maps
- `computer_use` — captures your screen
- `deep_research` — long-running background task with server-side storage; still requires `--execute` because it is mutating

### By latency

**Fast (< 2s typical):**
- `text`, `embed`, `token_count`, `code_exec`, `structured`

**Medium (2–10s typical):**
- `streaming`, `multimodal`, `function_calling`
- `search`, `maps`
- `batch status check`

**Slow (10s–5min+):**
- `file_search` (long-running operations)
- `video_gen` (1–2 min)
- `image_gen` (5–10s)
- `music_gen` (5–15s)
- `deep_research` (30s–5min)

### By cost

**Free tier included:**
- `text`, `multimodal`, `structured`, `streaming`
- `embed`, `token_count`

**Quoted per-request:**
- `function_calling`, `code_exec`
- `search`, `maps`

**High cost (specialty):**
- `image_gen`, `video_gen`, `music_gen` (billed per generation)
- `deep_research` (billed per research task)
- `file_search` (billed per upload + query)

See [Google Gemini pricing](https://aistudio.google.com/pricing) for current rates.

### By model

**Text/Chat models:**
- `text`, `streaming`, `multimodal`, `structured`
- `function_calling`, `code_exec`
- Default: `gemini-2.5-flash`

**Embedding model:**
- `embed`
- Default: `gemini-embedding-2-preview` (only model in [registry/models.json](../registry/models.json) declaring the `embed` capability)

**Specialty models:**
- `image_gen` → `gemini-3.1-flash-image-preview` (Nano Banana 2)
- `video_gen` → `veo-3.1-generate-preview`
- `music_gen` → `lyria-3-clip-preview`
- `computer_use` → `gemini-3-flash-preview` (default); `gemini-2.5-computer-use-preview-10-2025` also available
- `deep_research` → no fixed default; set `--model` explicitly
- `search`, `maps` → use the text default (`gemini-2.5-flash`) with grounding tools enabled

---

## Quick recipes

### Simple text interaction

```bash
/gemini text "What is machine learning?"
```

### Multi-turn conversation

```bash
/gemini text --session chat "Hello"
/gemini text --continue "What's 2+2?"
/gemini text --continue "Now add 3"
```

### Process a file

```bash
/gemini multimodal "Summarize this PDF" --file report.pdf
```

### Generate structured output

```bash
/gemini structured "Extract names from the text" --schema schema.json
```

### Get embeddings for search

```bash
/gemini embed "dense passage of text" --task-type RETRIEVAL_DOCUMENT
```

### Execute code

```bash
/gemini code_exec "Generate 100 random numbers and compute statistics"
```

### Upload a file

```bash
/gemini files upload dataset.csv --execute
/gemini files list
```

### Create a hosted RAG store

```bash
/gemini file_search create research-library --execute
/gemini files upload document.pdf --execute
/gemini file_search upload "fileSearchStores/store-id" "files/abc123" --execute
/gemini file_search query "What are the key findings?" --store "fileSearchStores/store-id"
```

### Generate an image

```bash
/gemini image_gen "A serene mountain landscape" --execute
```

### Count tokens before sending

```bash
/gemini token_count "This is a long prompt that I want to check the token cost for"
```

---

## Need help?

- **Command overview:** This file
- **Per-command docs:** `/reference/<command>.md`
- **How it works:** `docs/how-it-works.md`
- **Capabilities:** `docs/capabilities.md`
- **Security:** `docs/security.md`
- **Installation:** `docs/install.md`

For more details, see the [README](../README.md).
