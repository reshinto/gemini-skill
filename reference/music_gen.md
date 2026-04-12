# music_gen

Generate music using Gemini's music generation model (Lyria 3). 30-second maximum duration, SynthID watermark applied.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" music_gen "prompt" [--output-dir dir] --execute
```

## Flags

- `--output-dir DIR` — Directory for output audio (default: OS temp dir).
- `--execute` — Confirm and generate. **Mutating, required.**
- `--model MODEL` — Override the default model.

## Examples

```bash
# Generate background music
gemini_run.py music_gen "Calm ambient piano, 120 BPM" --execute

# With custom output directory
gemini_run.py music_gen "Upbeat electronic dance track with synths" --output-dir ~/Music --execute

# Specific style and tempo
gemini_run.py music_gen "Jazz improvisation, alto saxophone solo" --execute
```

## Output

Returns JSON with file path and metadata:

```json
{
  "path": "/path/to/music_12345.wav",
  "mime_type": "audio/wav",
  "duration_seconds": 30,
  "size_bytes": 1234567
}
```

## Duration limit

Generated music is capped at 30 seconds maximum.

## Watermarking

SynthID watermark is applied to all generated audio for identification purposes.

## Default behavior

Without `--execute`, prints dry-run. Use `--execute` to generate.

## Default model

Lyria 3 (Gemini's music model).

## Note

Music generation is non-commercial in most jurisdictions. Check your terms of service before publishing generated music.
