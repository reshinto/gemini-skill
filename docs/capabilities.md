# Capabilities

**Last Updated:** 2026-04-13

A conceptual overview of every gemini-skill capability, with status, limitations, and use cases.

## Generation

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

---

## Data & Analysis

### Embeddings

**Status:** Stable

Generate vector embeddings for text (768 dimensions).

**Capabilities:**
- Embedding task types (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY)
- Deterministic output (same input → same embedding)
- Fast generation

**Limitations:**
- Fixed 768 dimensions
- Not suitable for long documents (>20KB text)
- Single text input (batch via `batch` command)

**Use cases:**
- Semantic search
- Retrieval-augmented generation (RAG)
- Similarity matching
- Clustering and classification

See [embed.md](../reference/embed.md).

### Token counting

**Status:** Stable

Count tokens a prompt will consume before sending.

**Capabilities:**
- Accurate token count (matches API calculation)
- Includes system instructions and chat history
- Free (no quota impact)

**Limitations:**
- Count only (no preview of tokenization)

**Use cases:**
- Budget estimation before expensive calls
- Verify prompts fit within context window
- Optimize prompt length

See [token_count.md](../reference/token_count.md).

### Batch processing

**Status:** Stable

Submit multiple requests in a JSONL batch for asynchronous processing.

**Capabilities:**
- Up to 100,000 requests per batch
- Asynchronous processing
- Lower cost than real-time API
- Long-running (queues behind interactive requests)

**Limitations:**
- Asynchronous (no real-time response)
- Cannot cancel requests mid-batch
- No progress indication (only final status)

**Use cases:**
- Process large document collections
- Cost optimization for high-volume tasks
- Offline data processing

See [batch.md](../reference/batch.md).

---

## Tool Use

### Function calling

**Status:** Stable

Model can call your defined functions/tools and receive responses.

**Capabilities:**
- Define custom functions with OpenAPI schema
- Multi-turn function calling (model calls, you respond, model calls again)
- Automatic tool state preservation

**Limitations:**
- You must implement function logic (skill only dispatches calls)
- Tool schema must be valid OpenAPI 3.0
- No asynchronous tool execution (request must complete)

**Use cases:**
- Calculator and math functions
- Web API integrations
- Database queries
- Real-time data retrieval

See [function_calling.md](../reference/function_calling.md).

### Code execution

**Status:** Stable

Execute Python code in Gemini's sandboxed environment.

**Capabilities:**
- Python 3.x standard library
- Fast code execution
- Access to stdout/stderr
- Math and data processing libraries

**Limitations:**
- Sandbox: no internet access, no external files
- Limited to standard library (no NumPy, Pandas, etc.)
- 30-second execution timeout
- State not preserved between calls

**Use cases:**
- Mathematical calculations
- Data manipulation and analysis
- Code verification
- Algorithm testing

See [code_exec.md](../reference/code_exec.md).

---

## Grounding

### Google Search grounding

**Status:** Stable (opt-in)

Ground responses in real-time Google Search results.

**Capabilities:**
- Live search integration
- Up-to-date information (within hours)
- Search source attribution

**Limitations:**
- Requires explicit opt-in (privacy-sensitive)
- Slower than text-only (network latency)
- Adds cost per request
- May cite unreliable sources

**Use cases:**
- Current events and news
- Stock prices and market data
- Recent discoveries and research
- Up-to-date product information

See [search.md](../reference/search.md).

### Google Maps grounding

**Status:** Stable (opt-in)

Ground responses in Google Maps location data.

**Capabilities:**
- Real-time business and location data
- Map-aware responses
- Attribution required

**Limitations:**
- Requires explicit opt-in (privacy-sensitive)
- Location queries may reveal intent
- Mandatory output schema enforced
- Adds cost per request

**Use cases:**
- Business finder (restaurants, stores)
- Location recommendations
- Route and navigation queries
- Local event discovery

See [maps.md](../reference/maps.md).

---

## File Management

### Files API

**Status:** Stable

Upload, list, retrieve, and delete files in Gemini's file storage.

**Capabilities:**
- Upload documents (PDF, text, code, images, audio, video)
- Track file metadata
- Use files in subsequent multimodal requests
- 48-hour retention (auto-delete after)

**Limitations:**
- 2GB per file, 20GB total quota
- 48-hour expiration (automatic deletion)
- File reuse requires `file_id` tracking
- Cannot download file content (only metadata)

**Use cases:**
- Upload large documents once, reference many times
- Share files across multiple API calls
- Organize uploaded content

See [files.md](../reference/files.md).

### Context caching

**Status:** Stable

Cache large input context to save tokens and reduce latency.

**Capabilities:**
- Cache text, documents, or system instructions
- Reuse cache across multiple requests
- TTL-based expiration
- Token savings (25% on cached content)

**Limitations:**
- Minimum 1024 tokens to benefit
- TTL expires cache (max default 3600s)
- Costs tokens to create cache
- Break-even: use cache 3+ times minimum

**Use cases:**
- Reuse large system instructions
- Analyze same document multiple ways
- Multi-turn RAG with fixed context
- Cost optimization for repeated patterns

See [cache.md](../reference/cache.md).

### File Search (hosted RAG)

**Status:** Stable (long-running operations)

Host documents in a File Search store for semantic retrieval without sending file content in each request.

**Capabilities:**
- Create persistent document stores
- Upload documents once, query many times
- Semantic search (not keyword)
- Long-running operations (polling required)

**Limitations:**
- Asynchronous operations (polling required)
- Store is permanent (no expiry like Files API)
- Uploads may take 30–60 seconds
- Query latency varies by store size

**Use cases:**
- Knowledge base / FAQ system
- Document corpus semantic search
- Multi-document research
- Persistent RAG without reprocessing

See [file_search.md](../reference/file_search.md).

---

## Media Generation

### Image generation

**Status:** Preview (v1beta, may change)

Generate images using the Nano Banana model.

**Capabilities:**
- Text-to-image generation
- Fast turnaround (5–10s)
- PNG output saved to file

**Limitations:**
- Requires `--execute` flag (mutating)
- Nano Banana is cost-optimized (lower quality than others)
- Cannot edit or modify images
- 1 image per request

**Use cases:**
- Quick visual content generation
- Illustration for documents
- UI/UX mockup generation
- Educational diagrams

See [image_gen.md](../reference/image_gen.md).

### Video generation

**Status:** Preview (v1beta, may change)

Generate videos using the Veo model.

**Capabilities:**
- Text-to-video generation
- 4–10 second videos
- MP4 output saved to file
- Long-running (polling required)

**Limitations:**
- Requires `--execute` flag (mutating)
- Slow (1–2 minutes typical)
- High cost per generation
- Async: must poll for completion
- Output quality may vary

**Use cases:**
- Animated explanations
- Visual storytelling
- Marketing video content
- Educational video generation

See [video_gen.md](../reference/video_gen.md).

### Music generation

**Status:** Preview (v1beta, may change)

Generate music using the Lyria 3 model.

**Capabilities:**
- Text-to-music generation
- SynthID watermark (audio identification)
- WAV output saved to file
- 30-second maximum duration

**Limitations:**
- Requires `--execute` flag (mutating)
- 30-second cap (no longer tracks)
- SynthID watermark embedded (may be audible)
- High cost per generation
- Non-commercial by default (check license)

**Use cases:**
- Background music for videos
- Soundtrack generation
- Audio branding
- Musical composition assistance

See [music_gen.md](../reference/music_gen.md).

---

## Advanced/Experimental

### Computer use

**Status:** Preview (v1beta, privacy-sensitive, opt-in)

Enable the model to capture screenshots, analyze UI, and simulate keyboard/mouse input.

**Capabilities:**
- Screenshot capture
- UI element detection
- Keyboard and mouse input simulation
- Long-running tasks

**Limitations:**
- Preview feature (API may change)
- Can capture sensitive data on screen (privacy risk)
- Input simulation is best-effort
- High latency (multiple round-trips)
- Not suitable for sensitive environments

**Use cases:**
- Automate desktop tasks
- Navigate GUI applications
- Screenshot analysis
- Automated testing

**Caution:** Do not use with sensitive data visible (passwords, financial info, PII).

See [computer_use.md](../reference/computer_use.md).

### Deep Research

**Status:** Preview (Interactions API, opt-in)

Conduct multi-step research tasks with server-side storage and resumption.

**Capabilities:**
- Multi-step research (agent-like)
- Server-side result storage
- Session resumption (`--resume`)
- Background processing

**Limitations:**
- Preview feature (API may change)
- Asynchronous: long-running (30s–5min)
- Storage expires: 55 days (paid), 1 day (free)
- Requires `--execute` (mutating)
- High cost

**Use cases:**
- Thorough research investigation
- Multi-source synthesis
- Complex analysis tasks
- Background research

See [deep_research.md](../reference/deep_research.md).

---

## Feature Matrix

| Feature | Status | Mutating | Cost | Latency | Stability |
|---------|--------|----------|------|---------|-----------|
| Text | Stable | No | Low | <1s | ✓ |
| Multimodal | Stable | No | Low–Med | 1–5s | ✓ |
| Streaming | Stable | No | Low | 1–10s | ✓ |
| Structured | Stable | No | Low | 1–3s | ✓ |
| Embed | Stable | No | Low | <1s | ✓ |
| Token count | Stable | No | Free | <1s | ✓ |
| Function calling | Stable | No | Med | 1–10s | ✓ |
| Code exec | Stable | No | Low | 1–5s | ✓ |
| Search | Stable | No | Med | 3–5s | ✓ |
| Maps | Stable | No | Med | 3–5s | ✓ |
| Files | Stable | Yes | Low | 1–30s | ✓ |
| Cache | Stable | Yes | Low | 1–5s | ✓ |
| Batch | Stable | Yes | Low | 5min–hours | ✓ |
| File Search | Stable | Yes | Low–Med | 30s–5min | ✓ |
| Image gen | Preview | Yes | High | 5–10s | ◐ |
| Video gen | Preview | Yes | High | 1–2min | ◐ |
| Music gen | Preview | Yes | High | 5–15s | ◐ |
| Computer use | Preview | No | High | 10–60s | ◐ |
| Deep Research | Preview | Yes | High | 30s–5min | ◐ |

---

## Next steps

- **Quick start:** [Getting started](usage.md)
- **All commands:** [Command index](commands.md)
- **Detailed reference:** [Per-command docs](../reference/index.md)
- **Security considerations:** [Security guide](security.md)
