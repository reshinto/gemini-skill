# streaming

Stream text output from Gemini using Server-Sent Events (SSE). Response appears incrementally in real-time.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" streaming "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

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
