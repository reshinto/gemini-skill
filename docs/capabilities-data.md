# Capabilities — Data

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Commands for embeddings, token accounting, server-side files and caches, batch jobs, and hosted file search (RAG).

## Commands in this category

- `embed` → [embed.md](../reference/embed.md)
- `token_count` → [token_count.md](../reference/token_count.md)
- `files` → [files.md](../reference/files.md)
- `cache` → [cache.md](../reference/cache.md)
- `batch` → [batch.md](../reference/batch.md)
- `file_search` → [file_search.md](../reference/file_search.md)

---

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
- Downloading file content writes locally and requires `--execute`

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
- Currently routed via the raw HTTP backend at runtime (SDK 1.33.0 does not expose this surface)

**Use cases:**
- Knowledge base / FAQ system
- Document corpus semantic search
- Multi-document research
- Persistent RAG without reprocessing

See [file_search.md](../reference/file_search.md).

---

## See also

- [capabilities.md](capabilities.md) — category index
- [commands.md](commands.md) — command routing
- [reference/index.md](../reference/index.md) — per-command reference
