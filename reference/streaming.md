# streaming

Stream text output from Gemini using Server-Sent Events (SSE). Response appears incrementally in real-time.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" streaming "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `streaming` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`; if you need those, use the `text` command, which exposes them.

## Examples

```bash
# Stream a long response
gemini_run.py streaming "Write a detailed blog post about machine learning"

# Stream with custom model
gemini_run.py streaming "Explain quantum entanglement" --model gemini-2.5-pro

# Stream in a session
gemini_run.py streaming --session chat "Tell me a story"
gemini_run.py streaming --continue "What happens next?"
```

## Behavior

Output is printed as it arrives from the server. If the connection drops or no data arrives for 30s, the stream fails with a network error.

## Default model

`gemini-2.5-flash`.

## Note

Streaming is useful for long responses or interactive workflows. For one-shot requests, use the standard `text` command.

---

Backend-agnostic: this command produces identical output whether the SDK or raw HTTP backend handled the call.
