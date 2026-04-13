# How It Works: Execution Trace

**Last Updated:** 2026-04-13

This document traces the complete execution path for a simple command: `gemini text "hello"`.

## Step 0: User invokes the skill

```bash
/gemini text "hello"
```

Claude Code recognizes the `/gemini` skill and invokes the registered allowed-tool:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/gemini_run.py text "hello"
```

From this point, execution is deterministic.

## Step 1: Launcher checks Python version

File: `scripts/gemini_run.py`

```python
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(...))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.cli.dispatch import main
main(sys.argv[1:])  # ["text", "hello"]
```

The launcher is **2.7-compatible syntax** so that even Python 2 or early 3.x versions get a readable error instead of a SyntaxError.

Once Python 3.9 is confirmed, the repo root is added to sys.path and `dispatch.main()` is called.

## Step 2: Dispatcher validates and routes

File: `core/cli/dispatch.py`

```python
def main(argv: list[str]) -> None:
    # argv = ["text", "hello"]
    command = argv[0]  # "text"
    remaining = argv[1:]  # ["hello"]
    
    if command not in ALLOWED_COMMANDS:
        # command is "text", which IS in ALLOWED_COMMANDS
        sys.exit("[ERROR] Unknown command: {command}")
    
    # Import the adapter
    adapter_module_path = ALLOWED_COMMANDS["text"]  # "adapters.generation.text"
    adapter_module = importlib.import_module(adapter_module_path)
    
    # Parse arguments
    parser = adapter_module.get_parser()  # ArgumentParser from text.py
    args = parser.parse_args(remaining)  # Parse ["hello"] → Namespace(prompt="hello", ...)
    
    # Invoke the adapter
    adapter_module.run(**vars(args))  # run(prompt="hello", model=None, system=None, ...)
```

The dispatcher is the **policy boundary**. It enforces:
- Command whitelist (only commands in `ALLOWED_COMMANDS` allowed)
- Argument parsing (each adapter's parser)
- Dry-run enforcement (mutating ops require `--execute`)

## Step 3: Adapter executes

File: `adapters/generation/text.py`

```python
def run(
    prompt: str,              # "hello"
    model: str | None = None, # None (use router default)
    system: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 1.0,
    session: str | None = None,
    **kwargs
) -> None:
    # Load config
    config = load_config()  # Reads prefer_preview_models, output_dir, etc.
    
    # Select model via router
    router = Router(root_dir=Path(...), prefer_preview=config.prefer_preview_models)
    resolved_model = model or router.select_model("text")  # Returns "gemini-2.5-flash"
    
    # Build request
    contents = [{"role": "user", "parts": [{"text": "hello"}]}]
    body = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        }
    }
    
    # Call API
    response = api_call(
        f"models/{resolved_model}:generateContent",
        body=body
    )
    
    # Extract and emit response
    text = response["candidates"][0]["content"]["parts"][0]["text"]
    emit_output(text, output_dir=config.output_dir)
```

The adapter is responsible for:
- Loading configuration (auth, preferences)
- Selecting the model
- Validating inputs
- Building the API request
- Calling the Gemini API
- Emitting output

## Step 4: Router selects model

File: `core/routing/router.py`

```python
def select_model(
    self,
    task_type: str = "text",
    complexity: str = "medium",
    user_override: str | None = None
) -> str:
    # Check if this is a specialty task
    if task_type in _SPECIALTY_TASKS:
        # Specialty tasks use their dedicated model from registry
        capability = self._registry.get_capability(task_type)
        return capability.default_model
    
    # General tasks use complexity tree
    models = _PREVIEW_MODELS if self._prefer_preview else _STABLE_MODELS
    model_id = models.get(complexity, _FALLBACK_MODEL)
    
    # Validate against registry
    if not self._registry.model_exists(model_id):
        raise ModelNotFoundError(...)
    
    return model_id
```

For task type `"text"` (a general task) and complexity `"medium"` (default):
- Not a specialty task, so use complexity tree
- `_prefer_preview` is `False` (from config)
- `_STABLE_MODELS["medium"]` = `"gemini-2.5-flash"`
- Validate that `"gemini-2.5-flash"` exists in the registry
- Return `"gemini-2.5-flash"`

## Step 5: API call

File: `core/infra/client.py`

```python
def api_call(
    endpoint: str = "models/gemini-2.5-flash:generateContent",
    body: dict = {...},
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
    api_key: str | None = None
) -> dict:
    # Resolve API key
    key = api_key or resolve_key()  # From GEMINI_API_KEY env var
    
    # Construct URL
    url = f"{BASE_URL}/{api_version}/{endpoint}"
    # = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    
    # Build request
    request = Request(url, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("x-goog-api-key", key)
    
    # Send request with retry logic
    response_json = _request_with_retry(request, body, timeout=30)
    return response_json
```

The client:
- Resolves the API key from environment
- Builds the request URL
- Sets authentication header (`x-goog-api-key`)
- Sends the request with exponential backoff retry
- Returns parsed JSON response

Retry logic handles:
- 429 (rate limited) — exponential backoff
- 5xx errors — exponential backoff
- Network errors — exponential backoff
- 504 timeout on GET — one retry (idempotent)
- 504 timeout on POST — fail immediately (may have side effects)

## Step 6: API response

Gemini API returns:

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "Hello! How can I help you today?"
          }
        ]
      }
    }
  ]
}
```

The adapter extracts:
```python
text = response["candidates"][0]["content"]["parts"][0]["text"]
# = "Hello! How can I help you today?"
```

## Step 7: Emit output

File: `core/adapter/helpers.py`

```python
def emit_output(text: str, output_dir: str | None = None) -> None:
    # Check size
    if len(text) > _LARGE_RESPONSE_THRESHOLD:  # 50KB
        # Save to file
        output_path = Path(output_dir or tempfile.gettempdir()) / f"response_{uuid}.txt"
        output_path.write_text(text)
        safe_print(f"[Response saved to {output_path}]")
    else:
        # Print to stdout
        safe_print(text)
```

For the response "Hello! How can I help you today?" (small):
```
Hello! How can I help you today?
```

This is printed to stdout and returned to Claude Code.

---

## Multi-turn example: sessions

If the user runs:

```bash
/gemini text --session "chat" "hello"
/gemini text --continue "What's the weather?"
```

### First call:

1. Dispatcher routes to `adapters/generation/text.py`
2. Adapter loads or creates session `"chat"` via `SessionState`
3. Session history starts empty: `[]`
4. Add user message: `[{"role": "user", "parts": [{"text": "hello"}]}]`
5. Call API
6. Get response: "Hello! How can I help you today?"
7. Save response to session: `[..., {"role": "model", "parts": [{"text": "..."}]}]`
8. Emit response to stdout

Session file saved to `~/.config/gemini-skill/sessions/chat.json`:
```json
{
  "messages": [
    {"role": "user", "parts": [{"text": "hello"}]},
    {"role": "model", "parts": [{"text": "Hello! How can I help you today?"}]}
  ]
}
```

### Second call:

1. Dispatcher routes to `adapters/generation/text.py`
2. Adapter loads session `"chat"` (via `--continue` → most recent)
3. Session history is loaded from file
4. Add user message to history
5. Call API with full conversation history
6. Get response
7. Update session file with new message
8. Emit response

This enables multi-turn conversations without user management.

---

## Large response example: save to file

If text response exceeds 50KB:

```python
if len(text) > 50_000:
    output_path = /tmp/response_xyz.txt
    output_path.write_text(text)
    safe_print(f"[Response saved to {output_path}]")
```

Claude Code receives:
```
[Response saved to /tmp/response_xyz.txt]
```

Instead of a 50KB+ response, Claude sees only the file path. This prevents token overflow.

---

## File operation example: dry-run

If the user runs:

```bash
/gemini files upload dataset.csv
```

Without `--execute`:

```python
def run(..., execute: bool = False, ...):
    if check_dry_run(execute, "upload file: dataset.csv"):
        return  # Prints dry-run message and exits
```

Output:
```
[DRY RUN] upload file: dataset.csv
[To execute, add --execute flag]
```

The file is NOT uploaded. To actually upload:

```bash
/gemini files upload dataset.csv --execute
```

This prevents accidental uploads.

---

## Streaming example

If the user runs:

```bash
/gemini streaming "Write a haiku"
```

The adapter calls `api_call(..., stream=True)`, which:

1. Opens a connection with `response.read()` in SSE mode
2. Parses each SSE event as JSON
3. Extracts the `text` part from each chunk
4. Prints immediately (no buffering)

Output appears incrementally:
```
A gentle breeze blows,
Cherry blossoms drift and swirl,
Spring awakens soft.
```

Instead of waiting for the full response, the user sees text as it arrives.

---

## Key takeaways

1. **Dispatcher is the policy boundary:** Whitelists commands, enforces flags, routes to adapters.
2. **Adapter implements the business logic:** Loads config, selects model, validates inputs, calls API.
3. **Router abstracts model selection:** Hides complexity tree and specialty task logic.
4. **Client handles HTTP:** Retries, authentication, streaming, and error handling.
5. **Atomic state:** Multi-turn sessions and file tracking use file locking.
6. **Fail closed:** Errors are clear and actionable.

This layered design makes the codebase easy to understand, test, and extend.
