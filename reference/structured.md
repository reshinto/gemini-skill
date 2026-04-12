# structured

Generate JSON output constrained to a JSON schema. Useful for extracting structured data from unstructured input.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" structured "prompt" --schema '{"type":"object","properties":{"name":{"type":"string"}}}' [--schema-file path.json]
```

## Flags

- `--schema JSON` — JSON schema inline (as a single quoted string).
- `--schema-file PATH` — Path to a JSON file containing the schema.
- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Extract names from text
gemini_run.py structured "Extract all person names" --schema '{"type":"object","properties":{"names":{"type":"array","items":{"type":"string"}}}}'

# Load schema from file
gemini_run.py structured "Classify this document" --schema-file schema.json

# Structured extraction with system instruction
gemini_run.py structured "Analyze this contract" --schema-file contract_schema.json --system "Extract key terms"
```

## Constraints

The model will only output JSON conforming to the provided schema. Invalid schema inputs cause an error.

## Default model

`gemini-2.5-flash` (strong at structured output).

## Large responses

Responses exceeding 50KB save to a file.
