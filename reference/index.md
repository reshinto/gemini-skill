# gemini-skill Command Reference

Run any command via: `python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`

## Command Map

| Command | Purpose | Mutating | Preview | Reference |
|---------|---------|----------|---------|-----------|
| `text` | Generate text | no | no | [text.md](text.md) |
| `multimodal` | Multimodal input (image, PDF, audio, video) | no | no | [multimodal.md](multimodal.md) |
| `structured` | JSON schema-constrained output | no | no | [structured.md](structured.md) |
| `streaming` | SSE streaming text | no | no | [streaming.md](streaming.md) |
| `embed` | Generate embeddings | no | no | [embed.md](embed.md) |
| `token_count` | Count tokens | no | no | [token_count.md](token_count.md) |
| `function_calling` | Tool/function calling | no | no | [function_calling.md](function_calling.md) |
| `code_exec` | Sandboxed code execution | no | no | [code_exec.md](code_exec.md) |
| `search` | Google Search grounding (opt-in) | no | no | [search.md](search.md) |
| `maps` | Google Maps grounding (opt-in) | no | no | [maps.md](maps.md) |
| `files` | Files API (upload/list/get/delete) | YES | no | [files.md](files.md) |
| `cache` | Context caching (create/list/get/delete) | YES | no | [cache.md](cache.md) |
| `batch` | Batch processing (create/list/get/cancel) | YES | no | [batch.md](batch.md) |
| `file_search` | File Search / hosted RAG | YES | yes | [file_search.md](file_search.md) |
| `image_gen` | Image generation (Nano Banana) | YES | yes | [image_gen.md](image_gen.md) |
| `video_gen` | Video generation (Veo) | YES | yes | [video_gen.md](video_gen.md) |
| `music_gen` | Music generation (Lyria 3) | YES | yes | [music_gen.md](music_gen.md) |
| `computer_use` | Computer use (preview, opt-in) | no | yes | [computer_use.md](computer_use.md) |
| `deep_research` | Deep Research (Interactions API) | YES | yes | [deep_research.md](deep_research.md) |
| `help` | Show command list | — | — | — |
| `models` | List available models | — | — | — |

## Mutating operations

Commands marked **YES** require `--execute` to actually run. Without it, they print a dry-run message and exit.

## Preview commands

Preview commands use v1beta API features that may change. Their model IDs are treated as defaults and verified against the live model list at runtime.

## Sessions

Multi-turn conversations are supported via `--session <id>` and `--continue`:

```bash
gemini_run.py text --session review "Analyze this code for bugs: ..."
gemini_run.py text --continue "Focus on the race condition. What's the fix?"
```

Session state is stored at `~/.config/gemini-skill/sessions/<id>.json`.
