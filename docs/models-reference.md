# Models Reference

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

This catalog lists every model available in the skill's registry, with details on cost, capabilities, and recommended use cases.

## Gemini Text & Multimodal Models

### gemini-2.5-flash

**Family:** Gemini 2.5

**Cost Tier:** Affordable

**Input:** $0.15 per 1M tokens | **Output:** $0.60 per 1M tokens | **Cached:** $0.0375 per 1M tokens

**Status:** Stable

**Capabilities:** text, multimodal, structured, streaming, function_calling, code_exec, search, cache, token_count

**When to pick:** Default choice for most tasks. Fast, efficient, and cheap. Handles text generation, image/PDF analysis, structured output, and function calling. Excellent for iterative reasoning where you want quick feedback. Recommended for new projects.

**Common use cases:** Chat, code generation, document analysis, JSON schema extraction, web search grounding.

---

### gemini-2.5-pro

**Family:** Gemini 2.5

**Cost Tier:** Premium

**Input:** $1.25 per 1M tokens | **Output:** $10.00 per 1M tokens | **Cached:** $0.3125 per 1M tokens

**Status:** Stable

**Capabilities:** text, multimodal, structured, streaming, function_calling, code_exec, search, cache, token_count

**When to pick:** For complex reasoning, advanced math, and nuanced analysis. Trades cost for accuracy. Use when Flash's output is insufficient or when you need the most capable model available. Context caching is especially valuable here due to the high token cost.

**Common use cases:** Research, complex problem-solving, multi-step reasoning, high-quality content generation.

---

### gemini-2.5-flash-lite

**Family:** Gemini 2.5

**Cost Tier:** Budget

**Input:** $0.075 per 1M tokens | **Output:** $0.30 per 1M tokens | **Cached:** $0.01875 per 1M tokens

**Status:** Stable

**Capabilities:** text, multimodal, streaming, file_search, token_count

**When to pick:** For simple, straightforward tasks where model power is less important than speed and cost. Ideal for high-volume inference (e.g., batch processing, content filtering, simple classification). Note: does not support structured output, function calling, or search grounding.

**Common use cases:** Batch file analysis, simple text classification, light document search, high-throughput inference.

---

### gemini-3-flash-preview

**Family:** Gemini 3 Preview

**Cost Tier:** Affordable

**Input:** $0.15 per 1M tokens | **Output:** $0.60 per 1M tokens | **Cached:** $0.0375 per 1M tokens

**Status:** Preview (may change)

**Capabilities:** text, multimodal, structured, streaming, function_calling, code_exec, search, maps, file_search, computer_use, token_count

**When to pick:** Experimental model with advanced tool use: maps grounding, file_search (RAG), and computer_use (screen automation). Use for testing new capabilities in the Gemini 3 family. Note: preview status means the model, API, or pricing may change.

**Common use cases:** Advanced tool coordination, screen automation, geographic reasoning, file-based RAG.

---

### gemini-3.1-pro-preview

**Family:** Gemini 3.1 Preview

**Cost Tier:** Premium

**Input:** $1.25 per 1M tokens | **Output:** $10.00 per 1M tokens | **Cached:** $0.3125 per 1M tokens

**Status:** Preview (may change)

**Capabilities:** text, multimodal, structured, streaming, function_calling, code_exec, search, token_count

**When to pick:** Preview of the Gemini 3.1 Pro model with advanced reasoning. Use for cutting-edge capability testing. Not recommended for production until the model reaches stable status.

**Common use cases:** Testing advanced reasoning on the 3.1 family, research.

---

## Image Generation Models

### gemini-3.1-flash-image-preview

**Family:** Gemini 3.1 Image (Nano Banana)

**Cost Tier:** Affordable

**Input:** $0.15 per 1M tokens | **Output:** $0.60 per 1M tokens (metered by image dimensions)

**Status:** Preview

**Capabilities:** image_gen

**When to pick:** Gemini-native image generation with strong text-in-image support. Faster and cheaper than Imagen for simple/abstract images. Pass `--model gemini-3.1-flash-image-preview` with the `image_gen` command.

**Common use cases:** Quick image prototypes, text-heavy images, abstract/artistic content.

---

### imagen-3.0-generate-002

**Family:** Imagen 3

**Cost Tier:** Variable (per request)

**Status:** Stable

**Capabilities:** image_gen

**When to pick:** For photorealistic images and complex scenes. Imagen excels at realism and fine detail. Trade-off: slower and potentially more expensive than Gemini-native generation. Use when you need production-quality, photorealistic output.

**Common use cases:** Product photography, realistic scenes, professional asset generation.

---

## Embedding & Similarity Models

### gemini-embedding-2-preview

**Family:** Gemini Embedding

**Cost Tier:** Free (0 cost)

**Status:** Preview

**Capabilities:** embed

**When to pick:** Convert text to fixed-dimensional vectors for similarity search, clustering, or retrieval-augmented generation (RAG). Zero cost makes this ideal for large-scale embedding pipelines. Note: preview status means the embedding dimensions or behavior may change.

**Common use cases:** Semantic search, document retrieval, similarity matching, vector database population.

---

## Video & Animation Models

### veo-3.1-generate-preview

**Family:** Veo 3.1 Video

**Cost Tier:** Metered (cost varies by duration)

**Status:** Preview

**Capabilities:** video_gen

**When to pick:** Generate short videos (up to ~60 seconds) from text prompts. Expensive operation due to video output size and computation. Use sparingly and only when video is necessary. Preview status means API and pricing may change.

**Common use cases:** Marketing videos, animated explainers, creative prototypes.

---

## Audio & Music Models

### lyria-3-clip-preview

**Family:** Lyria Audio Clip

**Cost Tier:** Metered

**Status:** Preview

**Capabilities:** music_gen

**When to pick:** Generate short music clips (up to ~30 seconds) from text descriptions. Use for background music, mood setting, or creative projects where you describe the desired sound. Preview status means the model and pricing may change.

**Common use cases:** Soundtrack generation, audio branding, creative audio experiments.

---

## Live Interaction Models

### gemini-2.5-live-flash-preview

**Family:** Gemini 2.5 Live

**Cost Tier:** Metered (real-time conversation)

**Status:** Preview

**Capabilities:** Bidirectional real-time text/audio streaming

**When to pick:** Real-time, low-latency conversation with audio input and output. Ideal for chatbots, voice assistants, and interactive applications. Metering is typically per minute of interaction. Preview status means the API and pricing are subject to change.

**Common use cases:** Voice chatbots, real-time assistants, interactive voice applications.

---

## Computer Use Models

### gemini-2.5-computer-use-preview-10-2025

**Family:** Gemini 2.5 Computer Use

**Cost Tier:** Premium (higher than base Gemini 2.5)

**Status:** Preview (dated 10/2025)

**Capabilities:** computer_use

**When to pick:** Screen automation and tool use. The model can see your screen and click/type to accomplish tasks programmatically. Expensive operation (multiple vision calls, action execution). Use only when you need end-to-end automation and the task is complex enough to justify the cost. Preview status means the API and pricing may change.

**Common use cases:** UI automation, end-to-end workflow automation, form filling, screenshot-based troubleshooting.

---

## Quick Selection Guide

| Task | Recommended Model | Why |
|------|-------------------|-----|
| Chat, general text | gemini-2.5-flash | Fast, cheap, all-around capable |
| Complex reasoning | gemini-2.5-pro | Better accuracy; cache for long prompts |
| Bulk processing | gemini-2.5-flash-lite | Cheapest; sufficient for simple tasks |
| Image analysis | gemini-2.5-flash | Multimodal, fast |
| Realistic image generation | imagen-3.0-generate-002 | Photorealistic; worth the extra cost |
| Quick image generation | gemini-3.1-flash-image-preview | Faster, cheaper; good for abstract |
| Text embeddings | gemini-embedding-2-preview | Free; perfect for search/RAG |
| Video generation | veo-3.1-generate-preview | Only option; use sparingly (expensive) |
| Music generation | lyria-3-clip-preview | Only option; use for audio projects |
| Voice chat | gemini-2.5-live-flash-preview | Real-time interaction; metered per minute |
| Screen automation | gemini-2.5-computer-use-preview-10-2025 | Only option; use for complex automation |

---

## How to List Models from the Skill

```bash
# List all models and their capabilities
python3 scripts/gemini_run.py models

# Search for a specific model
python3 scripts/gemini_run.py models --search "image"

# List models for a specific capability
python3 scripts/gemini_run.py models --capability text --capability multimodal
```

---

## Cost Estimation

The skill reports cost in two ways:

1. **Inline in command output:** Many commands (especially generation) print `Estimated cost: $X.XX` before execution.
2. **With `--cost-breakdown`:** Pass this flag to any command to see a detailed breakdown of input tokens, output tokens, cached tokens, and total USD cost.

Example:
```bash
python3 scripts/gemini_run.py text "your prompt" --cost-breakdown
```

---

## Caching Strategy by Model Cost

**Low cost** (Flash, Flash Lite): Caching is helpful only for very large, repetitive prompts (100K+ tokens reused 3+ times). For most use cases, the caching latency penalty isn't worth it.

**High cost** (Pro): Caching is highly recommended for large prompts. Even one reuse typically pays back the caching overhead. Use `--cache` (or rely on auto-caching for models that support it) and reuse the same prompt structure across requests.

---

## Navigation

- **Previous:** [Flags Reference](flags-reference.md)
- **Next:** [Usage Tour](usage-tour.md)
