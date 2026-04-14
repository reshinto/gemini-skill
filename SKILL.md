---
name: gemini
description: Gemini API access for Claude Code: text, multimodal, structured output, embeddings, plan review, search grounding, media generation, files, caching, and more.
disable-model-invocation: true
---

## Usage

Run:

`python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`

See `${CLAUDE_SKILL_DIR}/reference/index.md` for the full command map.
See `${CLAUDE_SKILL_DIR}/reference/plan_review.md` for plan review.

## Rules

- Mutating operations require `--execute`.
- Pass user input as single quoted argv values.
- Use `--session <id>` or `--continue` for multi-turn text sessions.
- Large text responses and generated media save to a file and print the path.

## Quick commands

- `help`
- `models`
- `text "prompt"`
- `multimodal "prompt" --file path.pdf`
- `plan_review "review this plan"`
- `embed "text"`
- `image_gen "prompt" --execute`
