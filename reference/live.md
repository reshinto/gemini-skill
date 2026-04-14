
# live

Realtime bidirectional session with the Gemini Live API.

The Live API streams responses over a persistent session instead of the classic request/response shape. It's optimized for conversational UX and realtime agents — the model produces text (or audio, when configured) incrementally as it thinks, and the session stays open until the adapter sees a `turn_complete` signal.

This adapter is **async-only** — it runs via `asyncio.run(run_async(...))` through the Phase 6 dispatch path. Setting `GEMINI_IS_SDK_PRIORITY=true` is required; the raw HTTP backend has no Live API counterpart.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" live "PROMPT" [OPTIONS]
```

Non-mutating (read-only from a policy standpoint). No `--execute` gate.

## Options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--modality` | `TEXT`, `AUDIO` | `TEXT` | Response modality. Audio mode requires client-side media handling. |
| `--model MODEL` | model id | `gemini-live-2.5-flash-preview` | Override the routed model. |

## Output

Text chunks stream to stdout as they arrive. A trailing newline is printed after `turn_complete` so the next shell prompt starts on its own line.

## Examples

```bash
# Basic text session
python3 scripts/gemini_run.py live "explain quantum entanglement in one paragraph"

# Use a specific Live model
python3 scripts/gemini_run.py live "hello" --model gemini-live-2.5-flash-preview
```

## Session lifecycle

1. Adapter calls `client.aio.live.connect(model, config)` which returns an async context manager.
2. Inside the `async with`, the adapter sends the prompt as a single `Content` turn via `session.send_client_content(turns=[...])`.
3. The adapter drains `session.receive()` as an async iterator, printing each message's `.text` to stdout.
4. The loop stops on the first message whose `server_content.turn_complete` is `True`. Any trailing messages on the channel are ignored.
5. The session closes cleanly on context exit.

## Backend-agnostic

This command is **SDK-only**. It requires `google-genai` in the skill venv and `GEMINI_IS_SDK_PRIORITY=true`. There is no raw HTTP fallback.

---

[← Back](index.md) · [Previous: imagen](imagen.md) · [Next: maps](maps.md)
