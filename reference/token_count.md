
# token_count

Count the number of tokens a prompt will consume before making an API call.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" token_count "prompt" [--model model]
```

## Flags

- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `token_count` adapter accepts only the flags above plus a positional `text` argument. It does **not** support `--system`, `--max-tokens`, or `--temperature` — the count is performed on the positional text as passed.

## Examples

```bash
# Count tokens in a simple prompt
gemini_run.py token_count "Explain quantum computing"

# Pin a model for the count
gemini_run.py token_count "Analyze this code" --model gemini-2.5-pro

# Budget check before sending
gemini_run.py token_count "Write a detailed research paper on AGI"
```

## Output format

```json
{"model": "gemini-2.5-flash", "totalTokens": 45}
```

## Use case

Use this command to estimate API costs before calling generateContent, or to verify that your prompt fits within token limits.

Default model: `gemini-2.5-flash`. Override with `--model`.

[← Back](index.md)
