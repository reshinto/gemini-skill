# multimodal

Send multimodal content (images, PDFs, audio, video, URLs) alongside text prompts to Gemini.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" multimodal "prompt" [--file path] [--file path2] [--mime type]
```

## Flags

- `--file PATH` — Path to a local file (image, PDF, audio, or video). Repeatable for multiple files.
- `--mime TYPE` — Override MIME type detection (e.g., `application/pdf`).
- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Analyze an image
gemini_run.py multimodal "Describe this image" --file photo.jpg

# Process a PDF with a specific MIME type
gemini_run.py multimodal "Summarize this document" --file report.pdf --mime application/pdf

# Multi-file analysis
gemini_run.py multimodal "Compare these documents" --file doc1.pdf --file doc2.pdf
```

## Supported formats

- **Images:** JPEG, PNG, GIF, WebP
- **PDFs:** application/pdf
- **Audio:** WAV, MP3, FLAC, Opus
- **Video:** MP4, MPEG, MOV, AVI

MIME type is detected automatically from file extension. Use `--mime` to override if detection fails.

## Default model

`gemini-2.5-flash` (handles multimodal well).

## Large responses

Responses exceeding 50KB save to a file; only the path is printed.
