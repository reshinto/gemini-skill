# function_calling

Invoke Gemini's function/tool calling capability. Model can call your defined functions and you handle the responses.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" function_calling "prompt" --tools '<json-or-path>'
```

## Flags

- `--tools VALUE` — **Required.** Either an inline JSON string or a path to a JSON file containing tool declarations. The adapter detects whether the value is a file path on disk and loads it; otherwise it parses the value as inline JSON.
- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `function_calling` adapter accepts only the flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, `--temperature`, or a separate `--tools-file` flag — the single `--tools` flag handles both inline JSON and file paths.

## Examples

```bash
# Tool definitions from a file (same --tools flag, just pass the path)
gemini_run.py function_calling "What's the weather?" --tools weather_tools.json

# Inline tool definition
gemini_run.py function_calling "Convert 100 miles to kilometers" \
  --tools '[{"functionDeclarations":[{"name":"convert_units","description":"Convert between units","parameters":{"type":"object","properties":{"value":{"type":"number"}}}}]}]'

# Multi-turn function calling session
gemini_run.py function_calling "Get the temperature" --session tools --tools tools.json
```

## Tool definition format

Tools are defined as OpenAPI 3.0 schemas:

```json
{
  "name": "get_weather",
  "description": "Get weather for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"]
  }
}
```

## Default model

`gemini-2.5-flash` (set as `default_model` for the `function_calling` capability in [registry/capabilities.json](../registry/capabilities.json)). Pin `--model gemini-2.5-pro` or `--model gemini-3.1-pro-preview` for harder tool-use reasoning.

## Note

The model may call your functions multiple times. Tool state (including `id` and `tool_type`) must be preserved across multi-turn interactions.

---

Backend-agnostic: this command produces identical output whether the SDK or raw HTTP backend handled the call.
