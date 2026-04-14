# imagen

Generate photoreal images with Google's Imagen model.

Distinct from `image_gen`:
- **`image_gen`** uses Gemini-native image generation via `generateContent` with `responseModalities=["IMAGE"]`. Works well for mixed text+image outputs and quick iterations.
- **`imagen`** uses Google's dedicated Imagen model (`client.models.generate_images`). Higher photoreal quality, more aspect-ratio control, optimized for standalone image generation. **SDK-only** — there is no raw HTTP fallback for this capability.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" imagen "PROMPT" [OPTIONS] --execute
```

Mutating operation — requires `--execute` to actually generate. Dry-run default.

## Options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--num-images N` | integer ≥ 1 | `1` | Number of images to generate in one call. |
| `--aspect-ratio` | `1:1`, `3:4`, `4:3`, `9:16`, `16:9` | (model default) | Image aspect ratio. |
| `--output-dir DIR` | path | config `output_dir` or OS temp | Directory for output files. |
| `--model MODEL` | model id | `imagen-3.0-generate-002` | Override the routed model. |

## Output

Bytes always land on disk. Stdout carries a JSON summary only — never base64 content — so Claude Code's tokenizer never ingests a large image blob.

```json
{
  "count": 2,
  "images": [
    {"path": "/tmp/gemini-skill-abc123.png", "mime_type": "image/png", "size_bytes": 189234},
    {"path": "/tmp/gemini-skill-def456.png", "mime_type": "image/png", "size_bytes": 201822}
  ]
}
```

## Examples

```bash
# Single image, default aspect ratio
python3 scripts/gemini_run.py imagen "a calico cat playing with yarn" --execute

# Four variants in 16:9
python3 scripts/gemini_run.py imagen "mountain sunset, photorealistic" \
  --num-images 4 --aspect-ratio 16:9 --execute

# Custom output directory
python3 scripts/gemini_run.py imagen "portrait of a fox" \
  --output-dir ./generated --execute
```

## Backend-agnostic

This command routes through the SDK backend exclusively. Imagen has no raw HTTP path in this skill — setting `GEMINI_IS_SDK_PRIORITY=false` does not affect it, but it does require `google-genai` installed in the skill venv.

---

[← Back](index.md) · [Previous: image_gen](image_gen.md) · [Next: live](live.md)
