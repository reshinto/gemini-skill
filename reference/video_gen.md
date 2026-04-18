# video_gen

Generate videos using Gemini's video generation model (Veo). Long-running operation with polling.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" video_gen "prompt" [--output-dir dir] [--poll-interval seconds] [--max-wait seconds] --execute
```

## Flags

- `--output-dir DIR` — Directory for output video (default: OS temp dir).
- `--poll-interval SECONDS` — Polling interval (default: 15).
- `--max-wait SECONDS` — Maximum wait time (default: 1800).
- `--execute` — Confirm and generate. **Mutating, required.**
- `--model MODEL` — Override the default model.

## Examples

```bash
# Generate a video (long-running, will poll)
gemini_run.py video_gen "A person walking through a forest" --execute

# With custom output directory and wait time
gemini_run.py video_gen "Ocean waves crashing on rocks" --output-dir ~/Videos --max-wait 900 --execute

# Custom polling interval
gemini_run.py video_gen "City traffic at night" --poll-interval 10 --execute
```

## Output

Returns JSON with file path and metadata:

```json
{
  "path": "/path/to/video_12345.mp4",
  "mime_type": "video/mp4",
  "duration_seconds": 6,
  "size_bytes": 5678900
}
```

## Polling

Video generation is asynchronous. The command polls every `--poll-interval` seconds until complete or `--max-wait` is exceeded.

## Limits

Generated videos are typically 4–10 seconds. Veo is Google's video generation model.

## Default behavior

Without `--execute`, prints dry-run. Use `--execute` to generate.

Default model: Veo (Gemini's video model).

[← Back](index.md)
