# Model Routing

**Last Updated:** 2026-04-13

How gemini-skill selects models based on task type, complexity, and user preferences.

## Decision Tree

```
Is the task a specialty task?
├─ YES: embed → gemini-embedding-2-preview
├─ YES: image_gen → gemini-3.1-flash-image-preview (Nano Banana 2)
├─ YES: imagen → imagen-3.0-generate-002 (SDK-only)
├─ YES: video_gen → veo-3.1-generate-preview
├─ YES: music_gen → lyria-3-clip-preview
├─ YES: live → gemini-live-2.5-flash-preview (SDK-only, async)
├─ YES: computer_use → gemini-3-flash-preview (default)
│                      or gemini-2.5-computer-use-preview-10-2025
├─ YES: file_search → gemini-2.5-flash-lite
├─ YES: maps → gemini-2.5-flash (with Maps grounding tool enabled)
│
└─ NO: General task (text, multimodal, code_exec, etc.)
    │
    └─ User override? (--model FLAG)
        ├─ YES: Use user override (validate against registry)
        │
        └─ NO: Use complexity tree
            │
            └─ Prefer preview models? (prefer_preview_models in config)
                ├─ YES (preview mode):
                │   ├─ Complexity HIGH → gemini-3.1-pro-preview
                │   ├─ Complexity MEDIUM → gemini-2.5-flash
                │   └─ Complexity LOW → gemini-2.5-flash-lite
                │
                └─ NO (stable mode):
                    ├─ Complexity HIGH → gemini-2.5-pro
                    ├─ Complexity MEDIUM → gemini-2.5-flash
                    └─ Complexity LOW → gemini-2.5-flash-lite
```

## Specialty Tasks

These tasks always route to a dedicated model, **regardless of complexity or preview settings**:

| Task | Default model | Purpose |
|------|---------------|---------|
| `embed` | `gemini-embedding-2-preview` | Vector embeddings |
| `image_gen` | `gemini-3.1-flash-image-preview` | Image generation (Nano Banana 2) |
| `imagen` | `imagen-3.0-generate-002` | Photoreal image generation (SDK-only) |
| `video_gen` | `veo-3.1-generate-preview` | Video generation |
| `music_gen` | `lyria-3-clip-preview` | Music generation |
| `live` | `gemini-live-2.5-flash-preview` | Realtime async sessions (SDK-only) |
| `computer_use` | `gemini-3-flash-preview` | Desktop automation (dedicated `gemini-2.5-computer-use-preview-10-2025` also registered) |
| `file_search` | `gemini-2.5-flash-lite` | RAG / semantic search |
| `maps` | `gemini-2.5-flash` | Location grounding (tool enabled on a general-purpose model) |

These are determined by the model registry (`registry/models.json`). If a model is unavailable, the command fails with an error.

## General Tasks

General tasks (text, multimodal, streaming, structured, code_exec, function_calling, etc.) use a **complexity-based routing tree**:

### Complexity Levels

- **HIGH:** Complex reasoning, multi-step logic, code analysis, research
  - Example: "Design a distributed consensus protocol"
  - Routes to: `gemini-2.5-pro` (default) or `gemini-3.1-pro-preview` (preview mode)

- **MEDIUM:** Balanced tasks, general queries, summarization, simple coding
  - Example: "Summarize this document"
  - Routes to: `gemini-2.5-flash` (default) or `gemini-2.5-flash` (preview mode)

- **LOW:** Simple queries, formatting, basic analysis
  - Example: "Convert this to JSON"
  - Routes to: `gemini-2.5-flash-lite` (cheapest, fastest)

**Default complexity:** MEDIUM (used if not explicitly specified by the adapter).

### Model Tiers

#### Stable models (default)

```
HIGH:   gemini-2.5-pro         (best reasoning, slower, more expensive)
MEDIUM: gemini-2.5-flash       (balanced, recommended for most tasks)
LOW:    gemini-2.5-flash-lite  (cheapest, fastest, lower quality)
```

#### Preview models

```
HIGH:   gemini-3.1-pro-preview (latest features, may change, may break)
MEDIUM: gemini-2.5-flash       (stable Flash remains stable)
LOW:    gemini-2.5-flash-lite  (stable Flash remains stable)
```

**Note:** Preview mode does NOT change the MEDIUM and LOW tier models — only HIGH tier gets a preview variant.

## User Override

Use `--model MODEL` to override automatic selection:

```bash
/gemini text "Summarize this" --model gemini-2.5-pro
```

User override:
- **Skips complexity check entirely**
- **Validates against the registry** (fails if model not found)
- **Works for any command** (adapters parse the `--model` flag)

Example:

```bash
# Explicit model override (skip router)
/gemini text "Hello" --model gemini-2.5-pro

# Illegal model (not in registry)
/gemini text "Hello" --model fake-model-999
→ [ERROR] Model not found in registry: fake-model-999
```

## Configuration

### prefer_preview_models

Set in your config file or environment:

```bash
# Via shell environment (if adapter loads from env)
export PREFER_PREVIEW_MODELS=true

# Via config file
# Configuration loading depends on adapter implementation
```

When `prefer_preview_models=true`:
- HIGH complexity → `gemini-3.1-pro-preview` (preview variant)
- MEDIUM/LOW → unchanged (still stable Flash)

**Caution:** Preview models are subject to breaking changes. Use only for development/testing.

## Cost Implications

Model selection impacts cost:

| Model | Cost | Speed | Quality | Reasoning |
|-------|------|-------|---------|-----------|
| `gemini-2.5-pro` | High | Slow | Best | ✓✓✓ |
| `gemini-2.5-flash` | Medium | Medium | Good | ✓✓ |
| `gemini-2.5-flash-lite` | Low | Fast | Good | ✓ |
| `gemini-embedding-2-preview` | Very Low | Fast | N/A | N/A |
| Preview models | Medium–High | Varies | Varies | Varies |

**Cost optimization:**
- Use `LOW` complexity for simple tasks (saves ~50% vs MEDIUM)
- Use `--model gemini-2.5-flash-lite` for cheap, fast responses
- Use `HIGH` complexity only for reasoning-heavy tasks
- Cache embeddings and use File Search for repeated RAG queries

## Registry

The model registry (`registry/models.json`) defines:

1. **Available models** — which models exist and are currently available
2. **Capabilities** — which models support which features (embeddings, images, etc.)
3. **Default models** — specialty task defaults
4. **Preview flag** — which models are preview/beta
5. **Deprecation status** — which models are sunset (phased out)

Example registry entry:

```json
{
  "models": [
    {
      "id": "gemini-2.5-pro",
      "display_name": "Gemini 2.5 Pro",
      "capabilities": ["text", "multimodal", "code_exec", "function_calling"],
      "preview": false,
      "deprecated": false,
      "default_for": []
    }
  ],
  "capabilities": {
    "text": {
      "default_model": "gemini-2.5-flash"
    },
    "embed": {
      "default_model": "gemini-embedding-2-preview"
    }
  }
}
```

### Updating the registry

When Gemini releases new models or deprecates old ones:

```bash
python3 setup/update.py
```

This fetches the latest model list from the Gemini API and updates `registry/models.json`.

## Fallback

If a model is not found:

1. **Preferred model unavailable** → error with available model list
2. **Registry is empty** → error (critical)
3. **API error** → error with diagnostic info

There is **no silent fallback**. If the model selection fails, you get a clear error message.

## Examples

### Example 1: Simple text task (MEDIUM complexity)

```bash
/gemini text "Explain quantum computing"
```

Routing:
1. Task type: `text` (general task)
2. Complexity: MEDIUM (default)
3. Prefer preview: false (default config)
4. Decision: `_STABLE_MODELS["medium"]` = `gemini-2.5-flash`
5. **Selected model:** `gemini-2.5-flash`

### Example 2: Complex analysis (HIGH complexity)

```bash
/gemini text "Design a distributed consensus protocol"
```

Routing:
1. Task type: `text` (general task)
2. Complexity: HIGH (inferred from complexity logic, or passed explicitly)
3. Prefer preview: false (default)
4. Decision: `_STABLE_MODELS["high"]` = `gemini-2.5-pro`
5. **Selected model:** `gemini-2.5-pro`

### Example 3: Preview mode (HIGH complexity)

```bash
# Assume config sets prefer_preview_models=true
/gemini text "Design a consensus protocol"
```

Routing:
1. Task type: `text` (general task)
2. Complexity: HIGH
3. Prefer preview: true
4. Decision: `_PREVIEW_MODELS["high"]` = `gemini-3.1-pro-preview`
5. **Selected model:** `gemini-3.1-pro-preview` (subject to breaking changes)

### Example 4: User override

```bash
/gemini text "Summarize this" --model gemini-2.5-pro
```

Routing:
1. Task type: `text`
2. User override: `gemini-2.5-pro`
3. Validate override against registry ✓
4. **Selected model:** `gemini-2.5-pro` (user's choice, skips router)

### Example 5: Embedding (specialty task)

```bash
/gemini embed "machine learning is powerful"
```

Routing:
1. Task type: `embed` (specialty task)
2. Specialty task → use dedicated model
3. Capability `embed` → `default_model` = `gemini-embedding-2-preview`
4. **Selected model:** `gemini-embedding-2-preview` (fixed, ignores complexity)

## API Versions

Model routing is **separate from API version selection**:

- **Router:** Selects model ID (e.g., `gemini-2.5-flash`)
- **API version:** Selects endpoint version (e.g., `v1` vs `v1beta`)

Each adapter may use a different API version for its endpoint:
- `/v1/models/{model}:generateContent` — stable generation
- `/v1beta/models/{model}:generateContent` — preview features
- `/v1beta/operations` — long-running operations (File Search, batch, etc.)

The router does **not** control API version; adapters choose based on the capability.

## Next steps

- **Commands:** [Command index](commands.md)
- **Capabilities:** [Capabilities overview](capabilities.md)
- **Architecture:** [System design](architecture.md)
