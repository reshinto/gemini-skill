# text

Generate text using Gemini models. Supports single-turn and multi-turn conversations.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" text "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model (e.g., `gemini-2.5-pro`)
- `--system TEXT` — System instruction for the model
- `--max-tokens N` — Maximum output tokens (default: 8192)
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0)
- `--session ID` — Start or continue a named session
- `--continue` — Continue the most recent session

## Examples

```bash
# Simple prompt
gemini_run.py text "Explain quantum computing in one paragraph"

# With system instruction
gemini_run.py text "Code review this" --system "Be terse and actionable"

# High-complexity task
gemini_run.py text "Design a distributed consensus protocol" --model gemini-2.5-pro

# Multi-turn session
gemini_run.py text --session review "Analyze this code"
gemini_run.py text --continue "Focus on the race condition"
```

## Default model

`gemini-2.5-flash` (medium complexity). Use `--model gemini-2.5-pro` for complex reasoning, or `--model gemini-2.5-flash-lite` for the cheapest option.

## Large responses

Responses exceeding 50KB are saved to a file; only the path and size are printed to stdout.

---

Backend-agnostic: this command produces identical output whether the SDK or raw HTTP backend handled the call.

---

[← Back](index.md) · [Previous: structured](structured.md) · [Next: token_count](token_count.md)
