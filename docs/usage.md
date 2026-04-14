# Usage

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-14

Getting started with gemini-skill and common workflows.

## Quick Start

### 1. Install

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

See [install.md](install.md) for detailed setup.

### 2. Set API key

```bash
export GEMINI_API_KEY="your_key_here"
```

### 3. Try a command

```bash
/gemini text "What is machine learning?"
```

---

## Common Workflows

### Single-turn Q&A

```bash
/gemini text "Explain quantum computing in 3 sentences"
```

### Multi-turn conversation

Start a session:
```bash
/gemini text --session chat "Hello, can you help me code?"
```

Continue the conversation:
```bash
/gemini text --continue "Write a Python function for fibonacci"
```

Continue with a specific session:
```bash
/gemini text --session chat "What about error handling?"
```

Sessions are stored in `~/.config/gemini-skill/sessions/<id>.json`.

### Analyze a document

```bash
/gemini multimodal "Summarize this document" --file report.pdf
```

Supports: PDF, images (JPEG/PNG/GIF/WebP), audio (WAV/MP3/FLAC/Opus), video (MP4/MPEG/MOV/AVI).

### Generate structured output

Define a schema:
```bash
cat > schema.json << 'EOF'
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer"},
    "email": {"type": "string"}
  },
  "required": ["name", "age"]
}
EOF
```

Extract data (the same `--schema` flag accepts either inline JSON or a file path — the adapter detects which):
```bash
/gemini structured "Extract contact info from this text: ..." --schema schema.json
```

### Embeddings for semantic search

Generate embeddings for a document:
```bash
/gemini embed "The quick brown fox jumps over the lazy dog" --task-type RETRIEVAL_DOCUMENT
```

Store the returned `values` array in a vector database for later similarity search.

### Execute code

```bash
/gemini code_exec "Calculate the 50th Fibonacci number"
```

The model writes Python code and Gemini executes it in a sandbox.

### Count tokens

Before sending expensive requests:
```bash
/gemini token_count "This is a long prompt that I want to estimate the cost for"
```

Returns the token count (useful for budgeting).

### Ground in current information

`search` and `maps` are privacy-sensitive. The dispatcher auto-applies the internal privacy opt-in flag when you intentionally invoke those commands.

Get latest news:
```bash
/gemini search "Latest developments in quantum computing"
```

Find nearby restaurants:
```bash
/gemini maps "Best coffee shops near downtown"
```

**Privacy note:** These send your query to Google Search / Google Maps. Use only for non-sensitive queries and only when the user explicitly asked for grounded results.

### Upload and reuse a file

Upload:
```bash
/gemini files upload dataset.csv --execute
# Returns: fileId-12345
```

Use in future requests:
```bash
/gemini multimodal "Analyze this data" --file fileId-12345
```

List uploaded files:
```bash
/gemini files list
```

### Generate an image

Uses the Nano Banana family (`gemini-3.1-flash-image-preview` — the default for the `image_gen` capability):

```bash
/gemini image_gen "A serene mountain landscape at sunset" --execute
```

Returns: `{"path": "/tmp/image_12345.png", "mime_type": "image/png", "size_bytes": 245678}`

The decoded image is saved to your output directory (default: OS temp dir). Raw base64 is never printed to stdout.

Pin the model explicitly for reproducibility:

```bash
/gemini image_gen "A serene mountain landscape at sunset" \
  --model gemini-3.1-flash-image-preview \
  --execute
```

Save to a specific directory:

```bash
/gemini image_gen "Abstract geometric art in blue and gold" \
  --output-dir ~/Pictures/gemini \
  --execute
```

`--model` accepts any model registered in [registry/models.json](../registry/models.json) whose `capabilities` list includes `"image_gen"`. See [reference/image_gen.md](../reference/image_gen.md) for adding new image-capable models.

### Create a knowledge base (File Search)

Create a store:
```bash
/gemini file_search create research-library --execute
# Returns: store-id-abc123
```

Upload documents:
```bash
/gemini files upload article1.pdf --execute
# Returns: files/abc123
/gemini file_search upload fileSearchStores/store-id-abc123 files/abc123 --execute
```

Query the store:
```bash
/gemini file_search query "What are the key findings?" --store fileSearchStores/store-id-abc123
```

List stores:
```bash
/gemini file_search list
```

### Batch processing

For high-volume requests, use batch:

Create `requests.jsonl`:
```json
{"custom_id": "req-1", "params": {"contents": [{"role": "user", "parts": [{"text": "Summarize the industrial revolution"}]}]}}
{"custom_id": "req-2", "params": {"contents": [{"role": "user", "parts": [{"text": "Summarize World War II"}]}]}}
```

Submit:
```bash
/gemini batch create --src requests.jsonl --dest results.jsonl --execute
```

Check status:
```bash
/gemini batch list
/gemini batch get batch-xyz
```

Results are written to `results.jsonl` when complete.

### Context caching

Cache a large document to reuse:

```bash
/gemini cache create "System prompt text" --ttl 7200 --execute
# Returns: cache-abc123
```

The cache stores large system instructions or documents for 2 hours (7200 seconds).

Use in subsequent requests by checking cache docs (implementation may vary by adapter).

---

## Choosing a Backend

The skill internally uses a dual-backend transport layer:

- **Default (SDK):** Uses `google-genai==1.33.0` SDK for primary backend
- **Fallback (Raw HTTP):** Uses `urllib` if SDK is unavailable or disabled

**Most users never need to touch this.** The dispatcher automatically picks the right backend based on availability and configuration.

### Advanced Configuration

For advanced users, override backend priority via `~/.claude/settings.json` environment block:

```json
{
  "env": {
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false"
  }
}
```

- `GEMINI_IS_SDK_PRIORITY=true` — Prefer SDK (default if available)
- `GEMINI_IS_RAWHTTP_PRIORITY=true` — Force raw HTTP (useful for testing or if SDK has issues)

Both backends produce identical output. Four capabilities (`maps`, `music_gen`, `computer_use`, `file_search`) automatically route via raw HTTP at runtime because the pinned SDK version does not expose those surfaces.

See [install.md](install.md) for environment setup details.

---

## Sessions

Multi-turn conversations are stored in local session files.

### Session files

Located in: `~/.config/gemini-skill/sessions/<id>.json`

Example session file:
```json
{
  "id": "chat",
  "messages": [
    {
      "role": "user",
      "parts": [{"text": "What is Python?"}]
    },
    {
      "role": "model",
      "parts": [{"text": "Python is a high-level programming language..."}]
    },
    {
      "role": "user",
      "parts": [{"text": "What are its key features?"}]
    }
  ]
}
```

### Session limits

- No hard limit on message count
- Conversations can accumulate tokens
- Use `--max-tokens` on the `text` command to cap response length (only `text` exposes this flag; `streaming`, `multimodal`, `structured`, and the tool commands do not)

### Clearing sessions

Delete a session:
```bash
rm ~/.config/gemini-skill/sessions/chat.json
```

Delete all sessions:
```bash
rm -rf ~/.config/gemini-skill/sessions/
```

---

## Large Response Handling

### Automatic file saving

Responses exceeding 50KB are automatically saved to a file:

```bash
/gemini text "Write a 10,000-word essay on machine learning"
# Output: [Response saved to /tmp/response_xyz123.txt]
```

Claude Code receives only the file path (not the full response).

### Specifying output directory

Control where large responses are saved:

```bash
/gemini text "Long response" --output-dir ~/Documents/gemini-responses
```

Default: OS temp directory (e.g., `/tmp/` on macOS/Linux, `C:\Temp` on Windows).

### Media output

Images, videos, and music always save to file:

```bash
/gemini image_gen "A sunset over the ocean" --execute
# Output: {"path": "/tmp/image_12345.png", "mime_type": "image/png"}
```

### Handling generated files

After generation, files are saved to disk. You can:
- View them: `/Users/you/Downloads/image_xyz.png`
- Move them: `mv /tmp/image_xyz.png ~/Pictures/`
- Analyze them: `/gemini multimodal "Analyze this" --file ~/Pictures/image_xyz.png`

---

## Model Selection

### Default models

The skill automatically selects models based on task complexity:

- **Simple tasks:** `gemini-2.5-flash-lite` (cheapest)
- **Balanced tasks:** `gemini-2.5-flash` (default)
- **Complex tasks:** `gemini-2.5-pro` (best reasoning)

### Override the model

Use `--model` to pick a specific model:

```bash
/gemini text "Complex problem" --model gemini-2.5-pro
```

List available models:

```bash
/gemini models
```

See [model-routing.md](model-routing.md) for decision tree.

---

## Dry-Run Mode

Mutating operations default to dry-run:

```bash
/gemini files upload data.csv
# Output: [DRY RUN] 'files' is a mutating operation. Pass --execute to actually run it.
```

Use `--execute` to actually run:

```bash
/gemini files upload data.csv --execute
```

This prevents accidental uploads, deletions, and generations.
Read-only commands and read-only subcommands do not accept `--execute`.

---

## Cost Tracking

The skill tracks daily API costs in `~/.config/gemini-skill/cost_today.json`.

View cost estimate before running expensive operations:

```bash
/gemini token_count "expensive prompt"
# Returns token count (multiply by per-token rate to estimate cost)
```

Check current day's costs:

```bash
cat ~/.config/gemini-skill/cost_today.json
# Output: {"date": "2026-04-13", "cost_cents": 12345}
```

Costs reset at UTC midnight.

---

## Streaming Responses

Stream long responses in real-time:

```bash
/gemini streaming "Write a detailed blog post on AI"
```

Output appears incrementally instead of waiting for the full response.

Useful for:
- Long text generation (articles, stories)
- Interactive dialogue
- Seeing early results while generation continues

---

## System Instructions

Add system instructions to guide the model:

```bash
/gemini text "Explain this concept" --system "Be concise and technical"
```

Works with:
- `text`, `streaming`, `multimodal`, `structured`
- Any task that uses the text generation API

---

## Help & Documentation

In-skill help:

```bash
/gemini help
```

Per-command help:

```bash
/gemini text --help
/gemini multimodal --help
```

Documentation:

- **Quick start:** [README](../README.md)
- **All commands:** [Commands guide](commands.md)
- **Per-command:** [Reference files](../reference/index.md)
- **Architecture:** [System design](architecture.md)
- **Security:** [Security guide](security.md)
- **Installation:** [Install guide](install.md)

---

## Troubleshooting

### Command not found

```bash
/gemini unknown_command
# [ERROR] Unknown command: unknown_command
```

Solution: Check available commands with `/gemini help`.

### API key error

```bash
# [ERROR] API key not found
```

Solution:
```bash
export GEMINI_API_KEY="your_key_here"
```

See [install.md](install.md) for detailed setup.

### Model not found

```bash
# [ERROR] Model not found in registry: fake-model-xyz
```

Solution:
1. Check available models: `/gemini models`
2. Use a valid model: `/gemini text "prompt" --model gemini-2.5-flash`

### Network timeout

```bash
# [ERROR] Timeout after 30 seconds
```

Solution:
- Wait and retry (API may be overloaded)
- Check your internet connection
- Check API status: https://status.ai.google.dev

### Large file upload fails

Files over 2GB are rejected by Gemini API.

Solution:
- Use file chunking (outside the skill)
- Use smaller files
- Use File Search for document corpus

---

## Next Steps

- **All commands:** [Commands guide](commands.md)
- **Detailed reference:** [Per-command docs](../reference/index.md)
- **Advanced:** [Architecture guide](architecture.md)
- **Installation:** [Install guide](install.md)
