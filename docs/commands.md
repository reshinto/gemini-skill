# Commands

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

Run commands either as a Claude Code skill:

```text
/gemini <command> [args]
```

or directly from the CLI:

```bash
python3 scripts/gemini_run.py <command> [args]
```

## Text and Review

| Command | Purpose | Reference |
|---------|---------|-----------|
| `text` | Single-turn and multi-turn text generation | [text.md](../reference/text.md) |
| `streaming` | Streaming text output | [streaming.md](../reference/streaming.md) |
| `plan_review` | Iterative plan review with verdict output | [plan_review.md](../reference/plan_review.md) |

## Multimodal and Structured Output

| Command | Purpose | Reference |
|---------|---------|-----------|
| `multimodal` | Prompt plus files or URLs | [multimodal.md](../reference/multimodal.md) |
| `structured` | Schema-constrained JSON | [structured.md](../reference/structured.md) |

## Search, Tools, and Execution

| Command | Purpose | Reference |
|---------|---------|-----------|
| `embed` | Generate embeddings | [embed.md](../reference/embed.md) |
| `token_count` | Estimate token usage | [token_count.md](../reference/token_count.md) |
| `function_calling` | Tool invocation via Gemini | [function_calling.md](../reference/function_calling.md) |
| `code_exec` | Code execution in Gemini's sandbox | [code_exec.md](../reference/code_exec.md) |
| `search` | Google Search grounding | [search.md](../reference/search.md) |
| `maps` | Google Maps grounding | [maps.md](../reference/maps.md) |

## Data and Storage

| Command | Purpose | Reference |
|---------|---------|-----------|
| `files` | Upload, list, fetch, download, and delete files | [files.md](../reference/files.md) |
| `cache` | Create and manage cached context | [cache.md](../reference/cache.md) |
| `batch` | Create and monitor batch jobs | [batch.md](../reference/batch.md) |
| `file_search` | Hosted RAG / File Search | [file_search.md](../reference/file_search.md) |

## Media and Preview Features

| Command | Purpose | Reference |
|---------|---------|-----------|
| `image_gen` | Gemini-native image generation | [image_gen.md](../reference/image_gen.md) |
| `imagen` | Imagen 3 generation | [imagen.md](../reference/imagen.md) |
| `video_gen` | Veo generation | [video_gen.md](../reference/video_gen.md) |
| `music_gen` | Lyria generation | [music_gen.md](../reference/music_gen.md) |
| `computer_use` | Computer use preview | [computer_use.md](../reference/computer_use.md) |
| `live` | Live API preview | [live.md](../reference/live.md) |
| `deep_research` | Deep Research preview | [deep_research.md](../reference/deep_research.md) |

## Utilities

| Command | Purpose |
|---------|---------|
| `help` | Print command help |
| `models` | List registered models |

## Safety Notes

- Mutating commands require `--execute`.
- Privacy-sensitive commands include `search`, `maps`, `computer_use`, and `deep_research`.
- `plan_review` is read-only. It uses the same transport stack as `text`, but adds a stricter output contract for planning workflows.
