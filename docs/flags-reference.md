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

### --dry-run

**Default:** Implied unless --execute is passed

**Applies to:** All mutation commands

**Rationale:** Explicit flag to opt into dry-run mode. In dry-run, the skill parses your arguments, validates them, and prints a summary of what would happen (model chosen, parameters, estimated cost) without making any API call. Useful for testing your command-line syntax.

---

### --validate-only

**Default:** Not set

**Applies to:** All commands

**Rationale:** Parse arguments, validate them, and exit without making any API call or I/O. Useful for shell scripts that want to validate a command before executing it in a pipeline.

---

## Privacy & Cost

### --search

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling

**Rationale:** Enable search grounding for the request. The Gemini API will search the web for current information and ground the response in those results. Search grounding incurs extra API quota (typically 2x the token cost of the base request). Omit this flag to skip search. See `reference/search.md` for when search is worth the extra cost.

---

### --show-grounding

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling (when --search is passed)

**Rationale:** In the response, include the grounding sources (URLs, snippets) that the search results provided. This helps you verify that the model used current information. Omit to see only the generated text.

---

### --no-cache

**Default:** Cache is enabled if available for the model and region**

**Applies to:** All commands that support context caching

**Rationale:** Disable context caching for this request, even if the model supports it. Caching is beneficial for large repetitive prompts (e.g., analyzing the same 100-page document multiple times), but adds latency on the first request. Pass `--no-cache` to opt out for one-off queries. See `reference/cache.md` for the economics of when caching is worth it.

---

### --cost-breakdown

**Default:** Not set

**Applies to:** All commands that consume quota

**Rationale:** After the command completes, print a detailed cost breakdown: input tokens, output tokens, cached tokens (if any), and the total cost in USD. Useful for understanding which operations are expensive. Redirect to a file if you want to log cost per request.

---

## Session & State

### --session <id>

**Default:** Each command is stateless unless --session is passed

**Applies to:** text, multimodal, structured, function_calling, code_exec

**Rationale:** Start or continue a multi-turn conversation. On first use with a new ID, the skill creates a session directory under `~/.claude/gemini-skill/sessions/` and stores the conversation history there. Subsequent calls with the same ID append to the history and include all prior messages in the context. Useful for back-and-forth reasoning or iterative refinement. See `reference/text.md` for session examples.

---

### --continue

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling, code_exec

**Rationale:** Shorthand for `--session <most_recent_id>`. Continues the most recently used session without needing to recall its ID. Useful for quick follow-ups in the REPL.

---

### --new-session

**Default:** Not set

**Applies to:** text, multimodal, structured, function_calling, code_exec

**Rationale:** Explicitly start a fresh conversation, discarding any prior history even if --session would have found one. Use when you want to reset context.

---

### --list-sessions

**Default:** Not set

**Applies to:** All commands (usually called alone)

**Rationale:** Print a table of all stored sessions: ID, timestamp of last use, number of turns, approx. context size. Useful for housekeeping and deciding which sessions to delete.

---

### --delete-session <id>

**Default:** Not set

**Applies to:** All commands (usually called alone)

**Rationale:** Delete the session directory for a given ID, freeing disk space. The conversation history is lost. Useful after finishing a long project.

---

## Model Selection

### --model <name>

**Default:** gemini-2.5-flash (fastest/cheapest all-rounder)

**Applies to:** All generation commands

**Rationale:** Override the default model. Common choices: gemini-2.5-pro for complex reasoning, gemini-2.5-flash-lite for simple tasks. See `docs/models-reference.md` for a complete list of available models and when to pick each. Pass `models` command to list all options.

---

### --list-models

**Default:** Not set

**Applies to:** All commands (usually called alone)

**Rationale:** Print a table of all available models in the registry: name, cost (input/output per 1M tokens), capabilities, and recommended use cases. Equivalent to running the `models` command.

---

## I/O & Formatting

### --file <path> / -f

**Default:** Not set

**Applies to:** multimodal, function_calling, file_search, batch (for input batches)

**Rationale:** Pass a file to include in the request. For multimodal, the file is analyzed alongside your text prompt (PDF, image, audio, video, etc.). For batch, the file is a JSONL of requests. You can pass --file multiple times to include multiple files. The skill auto-detects the MIME type; override with `--content-type <type>` if needed.

---

### --output <path> / -o

**Default:** Not set; responses print to stdout

**Applies to:** All commands that produce large responses

**Rationale:** Write the response to a file instead of stdout. Useful for piping output to another tool or saving large responses (e.g., generated images, videos). If the response is large (>50KB), the skill automatically saves it to a temp file and prints the path; use --output to specify the location.

---

### --format <type>

**Default:** Depends on command (text=text, image_gen=json with image path, etc.)

**Applies to:** text, structured, function_calling, batch

**Rationale:** Override the output format. Common choices: `text` (raw markdown), `json` (structured JSON), `jsonl` (JSON Lines for batch), `csv` (for tabular data). Not all formats are valid for all commands; invalid combinations are rejected at parse time.

---

### --stream / -s

**Default:** Not set (buffered response)

**Applies to:** text, multimodal, structured, function_calling

**Rationale:** Stream the response to stdout as it's generated instead of waiting for the full response. Useful for long-running generation where you want to see output as it arrives. Cannot be combined with --output (streamed responses don't buffer to a file).

---

### --show-metadata

**Default:** Not set

**Applies to:** All commands

**Rationale:** Include metadata in the output: timestamp, model used, backend (SDK or raw HTTP), tokens consumed, cache stats. Useful for debugging or logging what actually happened.

---

### --timeout <seconds>

**Default:** 30 seconds

**Applies to:** All commands

**Rationale:** Override the default request timeout. Increase for slow network or large files; decrease if you want to fail fast on an unresponsive API. If a request exceeds the timeout, it's retried on the fallback backend if available.

---

## Advanced / Tuning

### --temperature <float>

**Default:** 0.8 (varies by model)

**Applies to:** All generation commands

**Rationale:** Control the randomness of the output (0.0 = deterministic, 1.0 = creative). Lower values make the model more conservative and repetitive; higher values make it more creative and varied. For reasoning tasks, lower temperatures are better; for creative tasks, higher temperatures help. See your command's `reference/*.md` for recommended ranges.

---

### --max-output-tokens <int>

**Default:** 8192 (varies by model and region)

**Applies to:** All generation commands

**Rationale:** Limit the length of the response. The model stops generating once it reaches this count. Useful for keeping responses concise or bounding the cost of an expensive operation.

---

### --top-p <float>

**Default:** Varies by model (typically 0.95)

**Applies to:** All generation commands

**Rationale:** Alternative to temperature: limit generation to the top P% of probable tokens (nucleus sampling). Works well with low P values (0.1–0.5) to get coherent, diverse responses.

---

### --top-k <int>

**Default:** Varies by model

**Applies to:** All generation commands

**Rationale:** Limit generation to the top K most probable tokens at each step. Similar to top-p but simpler and sometimes more predictable. Values like 20–100 are common.

---

### --raw-http-only

**Default:** Not set (both backends available if configured)

**Applies to:** All commands

**Rationale:** Force the skill to use the raw HTTP backend and skip the SDK backend, even if it's installed. Useful for debugging, avoiding SDK bugs, or running in environments where the SDK isn't compatible.

---

### --sdk-only

**Default:** Not set (both backends available if configured)

**Applies to:** All commands

**Rationale:** Force the skill to use the SDK backend only. Fails if the SDK is not installed or not available. Useful for testing or preferring the SDK's behavior for a particular operation.

---

### --verbose / -v

**Default:** Not set

**Applies to:** All commands

**Rationale:** Print detailed diagnostics: which backend is running, retries, policy decisions, API call details (redacted to never show secrets). Useful for debugging why a command behaves unexpectedly.

---

### --quiet / -q

**Default:** Not set

**Applies to:** All commands

**Rationale:** Suppress non-essential output (progress messages, metadata). Print only the result and errors. Useful for parsing output in shell scripts.

---

## Installation & Maintenance

### --yes / -y

**Default:** Not set (interactive mode)

**Applies to:** install (setup/install.py)

**Rationale:** Run the installer non-interactively. Automatically answers "yes" to all prompts (venv creation, SDK installation, settings merge, API key setup). Useful for automation and CI/CD.

---

### --no-sdk

**Default:** Not set (SDK is installed)

**Applies to:** install (setup/install.py)

**Rationale:** Skip the google-genai SDK installation. The skill will work in raw HTTP mode only. Use if you have a conflicting version of the SDK or want to minimize dependencies.

---

### --reinstall

**Default:** Not set

**Applies to:** install (setup/install.py)

**Rationale:** Force a fresh venv creation and reinstall, even if the skill is already installed. Useful for fixing a broken installation or upgrading to a new SDK version.

---

### --health-check

**Default:** Not set

**Applies to:** All commands; often run standalone

**Rationale:** Run diagnostic checks: verify the venv is active, SDK is importable, settings.json exists and is readable, API key is set, and the API is reachable with a small test request. Print a summary and exit. Useful for troubleshooting installation issues.

---

## Navigation

- **Previous:** [Home](../README.md)
- **Next:** [Models Reference](models-reference.md)
