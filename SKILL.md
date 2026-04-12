---
name: gemini
description: Gemini API — text generation, image/video/music generation, embeddings, search grounding, maps grounding, context caching, batch processing, code execution, function calling, file search/RAG, computer use, deep research, and more.
disable-model-invocation: true
---

## Usage

Run: `python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`

See `${CLAUDE_SKILL_DIR}/reference/index.md` for the full command map.
For commands with flags or `--execute`, read `${CLAUDE_SKILL_DIR}/reference/<command>.md` first.

## Rules

- Mutating operations (upload, delete, create, image/video/music gen, batch submit, cache create) require `--execute` flag. Default is dry-run.
- Cost/privacy-sensitive operations (search grounding, maps grounding, URL context, inline file send, computer use, deep research) require explicit opt-in even when non-mutating.
- Pass user input as single opaque argv values (quoted).
- Use stdin or temp files for complex/multiline content.
- Never reconstruct shell commands by concatenating user text.
- Multi-turn sessions: use `--session <id>` to start/continue, `--continue` for most recent.
- Large responses (>50KB) and all media generation save to a file and return only the path + metadata.

## Quick commands

- `help` — list all commands
- `models` — list available models from registry
- `text "prompt"` — generate text
- `multimodal "prompt" --file path.pdf` — analyze files
- `embed "text"` — generate embeddings
- `image_gen "prompt" --execute` — generate an image
