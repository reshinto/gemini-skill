# structured

Generate JSON output constrained to a JSON schema. Useful for extracting structured data from unstructured input.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" structured "prompt" --schema '<json-or-path>'
```

## Flags

- `--schema VALUE` — **Required.** Either an inline JSON schema string or a path to a JSON file containing the schema. The adapter detects whether the value is a file path on disk and loads it; otherwise it parses the value as inline JSON.
- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `structured` adapter accepts only the flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, `--temperature`, or a separate `--schema-file` flag — the single `--schema` flag handles both inline JSON and file paths.

## Examples

```bash
# Inline schema
gemini_run.py structured "Extract all person names" \
  --schema '{"type":"object","properties":{"names":{"type":"array","items":{"type":"string"}}}}'

# Schema loaded from a file (same --schema flag, just pass the path)
gemini_run.py structured "Classify this document" --schema schema.json

# Pin a model
gemini_run.py structured "Analyze this contract" \
  --schema contract_schema.json --model gemini-2.5-pro
```

## Constraints

The model will only output JSON conforming to the provided schema. Invalid schema inputs cause an error.

Default model: `gemini-2.5-flash`. Override with `--model`. Responses exceeding 50KB save to a file. See [docs/usage.md#shared-rules](../docs/usage.md#shared-rules).

[← Back](index.md)
