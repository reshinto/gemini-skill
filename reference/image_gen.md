# image_gen

Generate images using Gemini's image generation model (Nano Banana family). Always saves to file, never outputs base64.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" image_gen "prompt" [--output-dir dir] --execute
```

## Flags

- `--output-dir DIR` — Directory for output images (default: OS temp dir).
- `--execute` — Confirm and generate. **Mutating, required.**
- `--model MODEL` — Override the default model.

## Examples

```bash
# Generate an image
gemini_run.py image_gen "A serene mountain landscape at sunset" --execute

# With custom output directory
gemini_run.py image_gen "Abstract geometric art in blue and gold" --output-dir ~/Pictures --execute

# Using a different model
gemini_run.py image_gen "Futuristic city skyline" --model imagen-3 --execute
```

## Output

Returns JSON with file path and metadata:

```json
{
  "path": "/path/to/image_12345.png",
  "mime_type": "image/png",
  "size_bytes": 245678
}
```

The image is decoded from base64 and saved to disk. Only the path is printed.

## Limits

Each generation counts toward your quota. Nano Banana is designed for fast, cost-effective image generation.

## Default behavior

Without `--execute`, prints a dry-run message. Use `--execute` to actually generate.

## Default model

Nano Banana (Gemini's image model family).

## Note

Images are always saved to a file. Base64 output is never sent to stdout (prevents token overflow in Claude Code).
