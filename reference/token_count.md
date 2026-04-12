# token_count

Count the number of tokens a prompt will consume before making an API call.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" token_count "prompt" [--model model]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction (included in token count).

## Examples

```bash
# Count tokens in a simple prompt
gemini_run.py token_count "Explain quantum computing"

# Count for a complex prompt with system instruction
gemini_run.py token_count "Analyze this code" --system "You are a code reviewer" --model gemini-2.5-pro

# Budget check before sending
gemini_run.py token_count "Write a detailed research paper on AGI"
```

## Output format

```
Tokens: 45
Model: gemini-2.5-flash
```

## Use case

Use this command to estimate API costs before calling generateContent, or to verify that your prompt fits within token limits.

## Default model

`gemini-2.5-flash`.
