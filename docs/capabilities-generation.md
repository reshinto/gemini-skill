# Capabilities — Generation

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Core text and content-generation commands, including streaming, multi-turn sessions, structured JSON output, multimodal input, and the plan-review verdict loop.

## Commands in this category

- `text` → [text.md](../reference/text.md)
- `streaming` → [streaming.md](../reference/streaming.md)
- `plan_review` → [plan_review.md](../reference/plan_review.md)
- `multimodal` → [multimodal.md](../reference/multimodal.md)
- `structured` → [structured.md](../reference/structured.md)

---

### Text generation

**Status:** Stable

Generate text responses from text prompts. Supports single-turn and multi-turn (sessions).

**Capabilities:**
- Temperature control (0.0–2.0)
- Max tokens control
- System instructions
- Multi-turn conversation history (stored locally in sessions)

**Limitations:**
- Max input: ~1M tokens per request (Gemini API limit)
- Max output: 8192 tokens (configurable)
- No image/video/audio input (use `multimodal`)

**Use cases:**
- Chat and question answering
- Text summarization
- Creative writing
- Code generation
- Analysis and reasoning

See [text.md](../reference/text.md).

### Multimodal input

**Status:** Stable

Process images, PDFs, audio, and video alongside text prompts.

**Supported formats:**
- **Images:** JPEG, PNG, GIF, WebP (up to 200K tokens)
- **PDFs:** application/pdf (up to 1000 pages)
- **Audio:** WAV, MP3, FLAC, Opus (up to 1 hour)
- **Video:** MP4, MPEG, MOV, AVI (up to 40 minutes)

**Limitations:**
- Files sent inline as base64 (larger file size in API call)
- No external URLs (file must be local)
- Audio/video processing slower than text

**Use cases:**
- Image analysis and captioning
- Document understanding (PDFs)
- Audio transcription and analysis
- Video scene understanding

See [multimodal.md](../reference/multimodal.md).

### Streaming output

**Status:** Stable

Receive text output incrementally via Server-Sent Events (SSE).

**Capabilities:**
- Real-time text streaming
- Early response visibility
- Useful for long-running text generation

**Limitations:**
- Cannot interrupt mid-stream (must wait for completion)
- Cannot use streaming with multimodal input
- Slightly slower than buffered response (due to overhead)

**Use cases:**
- Long-form content (articles, stories)
- Interactive dialogue
- Live response preview

See [streaming.md](../reference/streaming.md).

### Structured output

**Status:** Stable

Generate JSON output conforming to a JSON schema.

**Capabilities:**
- Define output structure with JSON schema
- Guaranteed schema compliance
- Useful for data extraction

**Limitations:**
- Schema must be valid OpenAPI 3.0 format
- Complex nested schemas may slow response
- No custom serialization

**Use cases:**
- Data extraction from text
- Form filling from documents
- Entity recognition
- Structured summaries

See [structured.md](../reference/structured.md).

> **Note:** The `plan_review` command is listed in this category's adapter directory but has no capability description in the original source. See [plan_review.md](../reference/plan_review.md) for the reference entry.

---

## See also

- [capabilities.md](capabilities.md) — category index
- [commands.md](commands.md) — command routing
- [reference/index.md](../reference/index.md) — per-command reference
