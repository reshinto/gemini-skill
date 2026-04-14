# gemini-skill Command Reference

Use the skill from Claude Code:

```text
/gemini <command> [args]
```

or from the CLI:

```bash
python3 scripts/gemini_run.py <command> [args]
```

## Command Map

| Command | Purpose | Mutating | Preview | Reference |
|---------|---------|----------|---------|-----------|
| `text` | Text generation and multi-turn sessions | no | no | [text.md](text.md) |
| `streaming` | Streaming text output | no | no | [streaming.md](streaming.md) |
| `plan_review` | Iterative plan review with verdict output | no | preview | [plan_review.md](plan_review.md) |
| `multimodal` | Prompt plus files and URLs | no | no | [multimodal.md](multimodal.md) |
| `structured` | Schema-constrained JSON | no | no | [structured.md](structured.md) |
| `embed` | Embeddings | no | no | [embed.md](embed.md) |
| `token_count` | Token counting | no | no | [token_count.md](token_count.md) |
| `function_calling` | Tool calling | no | no | [function_calling.md](function_calling.md) |
| `code_exec` | Gemini sandbox execution | no | no | [code_exec.md](code_exec.md) |
| `search` | Search grounding | no | no | [search.md](search.md) |
| `maps` | Maps grounding | no | no | [maps.md](maps.md) |
| `files` | Files API operations | some | no | [files.md](files.md) |
| `cache` | Cache operations | some | no | [cache.md](cache.md) |
| `batch` | Batch jobs | some | no | [batch.md](batch.md) |
| `file_search` | Hosted RAG / File Search | some | yes | [file_search.md](file_search.md) |
| `image_gen` | Gemini-native image generation | yes | yes | [image_gen.md](image_gen.md) |
| `imagen` | Imagen 3 generation | yes | yes | [imagen.md](imagen.md) |
| `video_gen` | Veo generation | yes | yes | [video_gen.md](video_gen.md) |
| `music_gen` | Lyria generation | yes | yes | [music_gen.md](music_gen.md) |
| `computer_use` | Computer use preview | no | yes | [computer_use.md](computer_use.md) |
| `live` | Live API preview | no | yes | [live.md](live.md) |
| `deep_research` | Deep Research preview | yes | yes | [deep_research.md](deep_research.md) |

## Session Paths

- Text-style sessions live at `~/.config/gemini-skill/sessions/<id>.json`.
- `plan_review` sessions live at `~/.config/gemini-skill/plan-review-sessions/<id>.json`.

## Runtime Config Reminder

The launcher resolves canonical Gemini env keys from the current working directory before dispatch:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env
