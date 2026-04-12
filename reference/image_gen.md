# image_gen

Generate images using a Gemini image-capable model (Nano Banana family). Always saves to file, never outputs base64.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" image_gen "prompt" [--model MODEL] [--output-dir DIR] --execute
```

## Flags

- `--model MODEL` — Override the model. Must be a model registered in [registry/models.json](../registry/models.json) that declares the `image_gen` capability. If omitted, the router picks the default for the `image_gen` capability.
- `--output-dir DIR` — Directory for output images (default: OS temp dir, or `output_dir` from config).
- `--execute` — Required. Image generation is mutating; without this flag the command prints a dry-run message and exits without calling the API.

## Default model

The router-selected default for the `image_gen` capability, set in [registry/capabilities.json](../registry/capabilities.json) (`default_model`). Currently:

- **`gemini-3.1-flash-image-preview`** — Nano Banana family, preview on `v1beta`. Fast and cost-effective. This is the only model registered today with the `image_gen` capability.

## Examples

```bash
# Use the registered default (Nano Banana / gemini-3.1-flash-image-preview)
gemini_run.py image_gen "A serene mountain landscape at sunset" --execute

# Pin the model explicitly (recommended for reproducibility)
gemini_run.py image_gen "A serene mountain landscape at sunset" \
  --model gemini-3.1-flash-image-preview --execute

# Save to a specific directory
gemini_run.py image_gen "Abstract geometric art in blue and gold" \
  --output-dir ~/Pictures/gemini --execute

# Combine: pinned model + custom output dir
gemini_run.py image_gen "Futuristic city skyline at night" \
  --model gemini-3.1-flash-image-preview \
  --output-dir ~/Pictures/gemini \
  --execute
```

## Using a different model

`--model` accepts any model ID present in [registry/models.json](../registry/models.json) whose `capabilities` list includes `"image_gen"`. To add a new image-capable model (e.g., a future Nano Banana revision or an Imagen model):

1. Add the model entry to `registry/models.json` with `"capabilities": ["image_gen", ...]`.
2. Optionally update `default_model` for the `image_gen` capability in `registry/capabilities.json` if you want it to become the new default.
3. Pass `--model <new-id>` on the command line to pin it.

Passing a `--model` that isn't registered, or that doesn't declare `image_gen`, will fail at the router/registry layer before any API call is made.

## Output

The adapter decodes the base64 image inline data from the API response, saves it to disk under `--output-dir` (or the temp dir), and prints a single JSON line with metadata:

```json
{
  "path": "/path/to/image_12345.png",
  "mime_type": "image/png",
  "size_bytes": 245678
}
```

Raw base64 is **never** printed to stdout — this prevents Claude Code token overflow on large images.

## Default behavior (no `--execute`)

Without `--execute`, the dispatcher prints `[DRY RUN] 'image_gen' is a mutating operation. Pass --execute to actually run it.` and exits with code 0. No API call is made.

## Limits

Each generation counts toward your Gemini API quota. Nano Banana is designed for fast, cost-effective image generation but every `--execute` call is billable.

## Related

- Live smoke test (dry-run, no billing): [tests/integration/test_image_gen_live.py](../tests/integration/test_image_gen_live.py)
- Live real-API test against Nano Banana 2 (billable, extra opt-in via `GEMINI_LIVE_IMAGE_GEN=1`): [tests/integration/test_image_gen_nano_banana_2_live.py](../tests/integration/test_image_gen_nano_banana_2_live.py)
- Upstream API docs: https://ai.google.dev/gemini-api/docs/image-generation
