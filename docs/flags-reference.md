# Flags Reference

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

This catalog lists every CLI flag the skill accepts, grouped by category. For each flag: full name, short form (if any), default, which commands accept it, and one-paragraph rationale.

## Execution & Safeguards

### --execute / -x

**Default:** Not set (dry-run mode)

**Applies to:** All mutation commands (image_gen, video_gen, music_gen, batch, file operations)

**Rationale:** By default, the skill runs in dry-run mode and prints what it *would* do without actually making the API call or writing files. This lets you validate your prompt and flags before spending quota. Pass `--execute` (or `-x`) to actually run the command. This discipline prevents accidental API calls, especially for expensive operations like video generation.

---

## Grounding

### --show-grounding

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling (when --search is passed)

**Rationale:** In the response, include the grounding sources (URLs, snippets) that the search results provided. This helps you verify that the model used current information. Omit to see only the generated text.

---

## Session & State

### --session <id>

**Default:** Each command is stateless unless --session is passed

**Applies to:** text, multimodal, structured, function_calling, code_exec

**Rationale:** Start or continue a multi-turn conversation. On first use with a new ID, the skill creates a session file under `~/.config/gemini-skill/sessions/<id>.json` and stores the conversation history there. Subsequent calls with the same ID append to the history and include all prior messages in the context. Useful for back-and-forth reasoning or iterative refinement. See `reference/text.md` for session examples.

---

### --continue

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling, code_exec

**Rationale:** Shorthand for `--session <most_recent_id>`. Continues the most recently used session without needing to recall its ID. Useful for quick follow-ups in the REPL.

---

## Model Selection

### --model <name>

**Default:** gemini-2.5-flash (fastest/cheapest all-rounder)

**Applies to:** All generation commands

**Rationale:** Override the default model. Common choices: gemini-2.5-pro for complex reasoning, gemini-2.5-flash-lite for simple tasks. See `docs/models-reference.md` for a complete list of available models and when to pick each. Pass `models` command to list all options.

---

## I/O & Formatting

### --file <path> / -f

**Default:** Not set

**Applies to:** multimodal, function_calling, file_search, batch (for input batches)

**Rationale:** Pass a file to include in the request. For multimodal, the file is analyzed alongside your text prompt (PDF, image, audio, video, etc.). For batch, the file is a JSONL of requests. You can pass --file multiple times to include multiple files. The skill auto-detects the MIME type; override with `--content-type <type>` if needed.

---

## Generation Tuning

### --temperature <float>

**Default:** 0.8 (varies by model)

**Applies to:** All generation commands

**Rationale:** Control the randomness of the output (0.0 = deterministic, 1.0 = creative). Lower values make the model more conservative and repetitive; higher values make it more creative and varied. For reasoning tasks, lower temperatures are better; for creative tasks, higher temperatures help. See your command's `reference/*.md` for recommended ranges.

---

### --max-tokens <int>

**Default:** 8192

**Applies to:** text

**Rationale:** Limit the length of the response from the `text` adapter. The model stops generating when it reaches this token count. Useful for keeping responses concise or bounding cost.

---

### --system <text>

**Default:** Not set

**Applies to:** text

**Rationale:** System instruction sent to the model before the user prompt. Sets tone, persona, or task constraints for the conversation. Passed as the `systemInstruction` field in the API request.

---

### --schema <json>

**Default:** Not set (required)

**Applies to:** structured

**Rationale:** JSON schema string the model must conform to for its output. Required by the `structured` adapter. The skill passes this schema via `responseSchema` in the API request body.

---

### --thinking <on|off>

**Default:** `on`

**Applies to:** plan_review

**Rationale:** Enable or disable extended thinking for plan-review iterations. When `on`, the model includes a thinking block before producing the VERDICT line. Dispatch handles this flag via raw string checks before passing it to the adapter.

---

### --task-type <type>

**Default:** Not set

**Applies to:** embed

**Rationale:** Embedding task type hint (e.g., `RETRIEVAL_DOCUMENT`, `SEMANTIC_SIMILARITY`). Controls how the embedding model weights token proximity. See the Gemini Embeddings API docs for valid values.

---

### --modality <modality>

**Default:** `TEXT`

**Applies to:** live

**Rationale:** Output modality for the Live session. Use `AUDIO` to receive synthesized speech, `TEXT` for text-only output. The Live adapter is async-only (IS_ASYNC=True).

---

### --num-images <int>

**Default:** Not set

**Applies to:** imagen

**Rationale:** Number of images to generate in a single Imagen request. Must be a positive integer. Higher values increase cost proportionally.

---

### --aspect-ratio <ratio>

**Default:** Not set

**Applies to:** imagen, image_gen

**Rationale:** Image aspect ratio (e.g., `1:1`, `16:9`). Supported choices are defined in the adapter; unsupported values are rejected at parse time.

---

### --output-dir <path>

**Default:** OS temp directory

**Applies to:** imagen, image_gen, video_gen, music_gen

**Rationale:** Directory where generated media files are written. When not set, files are saved to a temp directory and the path is printed to stdout. Specify a directory to control where output lands.

---

### --image-size <size>

**Default:** Not set

**Applies to:** image_gen

**Rationale:** Output image resolution for Gemini 3 image generation (e.g., `1024x1024`). When omitted, the model's default resolution is used.

---

### --poll-interval <seconds>

**Default:** Not set

**Applies to:** video_gen

**Rationale:** How frequently (in seconds) the adapter polls the long-running video generation operation for completion. Decrease for faster feedback on short jobs; increase to reduce API calls on long renders.

---

### --max-wait <seconds>

**Default:** Not set

**Applies to:** video_gen, deep_research

**Rationale:** Maximum total seconds to wait for a long-running operation. If the operation has not completed by this deadline, the adapter exits with an error. Useful in CI to prevent indefinite hangs.

---

### --resume <token>

**Default:** Not set

**Applies to:** deep_research

**Rationale:** Resume a previously started deep-research session using its resume token. Allows continuing a multi-step research job that was interrupted or timed out.

---

### --tools <json>

**Default:** Not set (required)

**Applies to:** function_calling

**Rationale:** JSON string describing the tool(s) available to the model. Required by the `function_calling` adapter. Format follows the Gemini `tools` API field.

---

### --display-name <name>

**Default:** Not set

**Applies to:** files (upload subcommand)

**Rationale:** Human-readable display name for the uploaded file in the Gemini Files API. If omitted, the API assigns a default name based on the filename.

---

### --ttl <duration>

**Default:** `3600s`

**Applies to:** cache (create subcommand)

**Rationale:** Time-to-live for the cached context (e.g., `3600s`, `86400s`). After expiry the cache entry is deleted automatically. Longer TTLs reduce re-caching overhead for frequently reused prompts.

---

### --src <uri>

**Default:** Not set (required)

**Applies to:** batch (create subcommand)

**Rationale:** Source file URI (JSONL) for the batch job. Must be a Gemini Files API URI pointing to the input requests.

---

### --dest <uri>

**Default:** Not set (required)

**Applies to:** batch (create subcommand)

**Rationale:** Destination file URI where batch output will be written. Must be a Gemini Files API URI.

---

### --store <name>

**Default:** Not set (required for query)

**Applies to:** file_search (query subcommand)

**Rationale:** File Search store resource name to query against. Required when running a RAG query via `file_search query`.

---

## Installation & Maintenance

### --yes / -y

**Default:** Not set (interactive mode)

**Applies to:** `gemini-skill-install`, `setup/install.py`

**Rationale:** Run the installer in non-interactive mode for settings merge and
legacy migration prompts. This is useful in CI or scripted installs. It does
not force overwrite of an existing install directory; overwrite vs skip remains
an explicit choice.

---

## Navigation

- **Previous:** [Home](../README.md)
- **Next:** [Models Reference](models-reference.md)
