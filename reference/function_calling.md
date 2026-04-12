# function_calling

Invoke Gemini's function/tool calling capability. Model can call your defined functions and you handle the responses.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" function_calling "prompt" --tools '{"tools":[...]}' [--tools-file path.json]
```

## Flags

- `--tools JSON` — Tool definitions inline (as a single quoted JSON string).
- `--tools-file PATH` — Path to a JSON file containing tool/function definitions.
- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Define a function and let the model call it
gemini_run.py function_calling "What's the weather?" --tools-file weather_tools.json

# Inline tool definition
gemini_run.py function_calling "Convert 100 miles to kilometers" --tools '{"tools":[{"name":"convert_units","description":"Convert between units","inputSchema":{"type":"object","properties":{"value":{"type":"number"}}}}]}'

# Multi-turn function calling session
gemini_run.py function_calling --session tools "Get the temperature" --tools-file tools.json
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

`gemini-2.5-pro` (best at function calling).

## Note

The model may call your functions multiple times. Tool state (including `id` and `tool_type`) must be preserved across multi-turn interactions.
