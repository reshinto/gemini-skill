# How It Works: Execution Trace

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-14

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

## Step 1: Launcher re-execs under venv

File: `scripts/gemini_run.py`

```python
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(...))

# If not already running under .venv, re-exec under it
venv_python = Path(__file__).parent.parent / ".venv" / "bin" / "python"
if venv_python.exists() and sys.prefix != str(venv_python.parent.parent):
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

# Now running under venv (or venv doesn't exist — raw HTTP fallback OK)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.cli.dispatch import main
main(sys.argv[1:])  # ["text", "hello"]
```

The launcher is **2.7-compatible syntax** so Python 2 or early 3.x versions get a readable error instead of a SyntaxError.

Once Python 3.9 is confirmed, the script re-execs under `~/.claude/skills/gemini/.venv/bin/python` if it exists (gives access to the google-genai SDK). If the venv doesn't exist, execution continues with the system Python (raw HTTP backend still works).

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
    
    # Check if adapter is async (IS_ASYNC = True flag)
    if getattr(adapter_module, "IS_ASYNC", False):
        # Async path: run via asyncio.run(run_async(...))
        parser = adapter_module.get_parser()
        args = parser.parse_args(remaining)
        asyncio.run(adapter_module.run_async(**vars(args)))
    else:
        # Sync path (most adapters)
        parser = adapter_module.get_parser()
        args = parser.parse_args(remaining)
        adapter_module.run(**vars(args))
```

The dispatcher is the **policy boundary**. It enforces:
- Command whitelist (only commands in `ALLOWED_COMMANDS` allowed)
- IS_ASYNC detection (async adapters like `live` run via `asyncio.run()`)
- Argument parsing (each adapter's parser)
- Privacy opt-in injection for privacy-sensitive commands
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
    
    # Call API via the dual-backend facade
    # The coordinator routes via primary (SDK) or fallback (raw HTTP) transparently
    response = api_call(
        f"models/{resolved_model}:generateContent",
        body=body
    )
    # response is normalized GeminiResponse dict shape (identical from both backends)
    
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

## Step 5: Dual-backend coordinator dispatch

File: `core/transport/coordinator.py`

The `TransportCoordinator` is invoked by the facade (`core/transport/__init__.py::api_call`):

```python
def api_call(endpoint: str, body: dict, ...) -> dict:
    coordinator = _get_or_init_coordinator()
    return coordinator.api_call(endpoint=endpoint, body=body, ...)

# Inside TransportCoordinator:
def api_call(self, ...) -> dict:
    try:
        # Try primary backend (SDK by default, or raw HTTP if inverted)
        return self._primary.api_call(...)
    except Exception as exc:
        if policy.is_fallback_eligible(exc) and self._fallback:
            # Log and retry with fallback
            logger.warning("Primary backend failed, trying fallback", 
                         extra={"primary": "sdk", "fallback": "raw_http"})
            return self._fallback.api_call(...)
        else:
            # Not eligible for fallback — re-raise
            raise
```

The coordinator:
- Routes to primary backend (SDK or raw HTTP) based on `GEMINI_IS_SDK_PRIORITY` / `GEMINI_IS_RAWHTTP_PRIORITY`
- Checks **capability support** before probing SDK (deterministic routing for unsupported capabilities)
- Catches exceptions and decides fallback eligibility via `policy.is_fallback_eligible()`
- Normalizes both backends' responses to identical `GeminiResponse` dict shape
- Logs all fallbacks so silent degradation is visible in production

### Primary Backend: SdkTransport

File: `core/transport/sdk/transport.py`

```python
class SdkTransport(Transport):
    _SUPPORTED_CAPABILITIES = frozenset({
        "text", "multimodal", "structured", "streaming",
        "embeddings", "token_count", "function_calling", "code_exec"
    })
    # Capabilities like "maps", "music_gen" are NOT in the set → route to raw HTTP
    
    def api_call(self, endpoint: str, body: dict, ...) -> dict:
        client = self._client_factory.get_client()
        response = client.models.generate_content(...)
        return normalize_sdk_response(response)  # Unified GeminiResponse shape
```

### Fallback Backend: RawHttpTransport

File: `core/transport/raw_http/transport.py`

```python
class RawHttpTransport(Transport):
    def api_call(self, endpoint: str, body: dict, ...) -> dict:
        key = resolve_key()
        url = f"{BASE_URL}/{api_version}/{endpoint}"
        request = Request(url, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("x-goog-api-key", key)
        
        response_json = _request_with_retry(request, body, timeout=timeout)
        return normalize_http_response(response_json)  # Unified GeminiResponse shape
```

Both transports:
- Resolve API key from environment (`GEMINI_API_KEY`)
- Support retries (exponential backoff for 429, 5xx, network errors)
- Return normalized responses (`GeminiResponse` dict)

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

Without `--execute`, the dispatcher exits before the adapter runs:

```python
_enforce_policy("files", ["upload", "dataset.csv"])
# prints [DRY RUN] 'files' is a mutating operation. Pass --execute to actually run it.
# exits before adapter.run(...)
```

Output:
```
[DRY RUN] 'files' is a mutating operation. Pass --execute to actually run it.
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

1. **Venv re-exec:** Launcher runs under `~/.claude/skills/gemini/.venv` if available (gives SDK access); falls back to system Python (raw HTTP only).
2. **Dispatcher is the policy boundary:** Whitelists commands, detects IS_ASYNC for async adapters, enforces flags, routes to adapters.
3. **Adapter implements business logic:** Loads config, selects model, validates inputs, calls facade (backend-agnostic).
4. **Coordinator owns backend dispatch:** Primary/fallback routing via capability gate + error-driven fallback, transparent to adapters.
5. **Normalized responses:** Both backends normalize to identical `GeminiResponse` dict shape via `normalize.py`.
6. **Router abstracts model selection:** Hides complexity tree and specialty task logic.
7. **Atomic state:** Multi-turn sessions and file tracking use file locking.
8. **Fail closed:** Errors are clear and actionable; fallbacks are logged.

This layered design makes the codebase easy to understand, test, and extend. The dual-backend transport is transparent to adapters — they never know (or care) which backend ran.
