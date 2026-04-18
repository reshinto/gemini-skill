# image_gen

Generate images using a Gemini image-capable model (Nano Banana family). Always saves to file, never outputs base64.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" image_gen "prompt" [--model MODEL] [--output-dir DIR] --execute
```

## Flags

- `--model MODEL` — Override the model. Must be a model registered in [registry/models.json](../registry/models.json) that declares the `image_gen` capability. If omitted, the router picks the default for the `image_gen` capability.
- `--aspect-ratio RATIO` — Image aspect ratio. Valid values: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`. Default: model-determined (typically `1:1`). Applies to Gemini 3 Pro Image models.
- `--image-size SIZE` — Image size preset. Valid values: `1K`, `2K`, `4K`. Default: model-determined. Applies to Gemini 3 Pro Image models.
- `--output-dir DIR` — Directory for output images (default: OS temp dir, or `output_dir` from config).
- `--execute` — Required. Image generation is mutating; without this flag the command prints a dry-run message and exits without calling the API.

Default model: **`gemini-3.1-flash-image-preview`** — Nano Banana family, preview on `v1beta`. Fast and cost-effective. This is the only model registered today with the `image_gen` capability (set in [registry/capabilities.json](../registry/capabilities.json)).

## Examples

```bash
# Use the registered default (Nano Banana / gemini-3.1-flash-image-preview)
gemini_run.py image_gen "A serene mountain landscape at sunset" --execute

# Specify aspect ratio (for Gemini 3 Pro Image models)
gemini_run.py image_gen "Mountain landscape" --aspect-ratio 16:9 --execute

# Specify image size preset
gemini_run.py image_gen "Abstract geometric art" --image-size 4K --execute

# Combine aspect ratio + size
gemini_run.py image_gen "Landscape photo" \
  --aspect-ratio 3:2 --image-size 2K --execute

# Pin the model explicitly (recommended for reproducibility)
gemini_run.py image_gen "A serene mountain landscape at sunset" \
  --model gemini-3.1-flash-image-preview --execute

# Save to a specific directory
gemini_run.py image_gen "Abstract geometric art in blue and gold" \
  --output-dir ~/Pictures/gemini --execute
```

## Using a different model

`--model` accepts any model ID in [registry/models.json](../registry/models.json) with `"image_gen"` in its `capabilities`. To add a new model, add it there and optionally update `default_model` in `registry/capabilities.json`. Unregistered or incapable model IDs fail at the registry layer before any API call.

## Output

Adapter saves decoded image to disk and prints one JSON line: `{"path": "...", "mime_type": "image/png", "size_bytes": N}`. Raw base64 is **never** printed to stdout.

## Default behavior (no `--execute`)

Prints a dry-run message and exits with code 0. No API call is made.

## Limits

Each generation counts toward your Gemini API quota. Nano Banana is designed for fast, cost-effective image generation but every `--execute` call is billable.

## Related

- Live smoke test (dry-run, no billing): [tests/integration/test_image_gen_live.py](../tests/integration/test_image_gen_live.py)
- Live real-API test against Nano Banana 2 (billable; runs whenever `GEMINI_LIVE_TESTS=1` — filter out with `pytest -k "not nano_banana"` to skip): [tests/integration/test_image_gen_nano_banana_2_live.py](../tests/integration/test_image_gen_nano_banana_2_live.py)
- Upstream API docs: https://ai.google.dev/gemini-api/docs/image-generation

[← Back](index.md)
