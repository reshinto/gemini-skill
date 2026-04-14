---
name: gemini
description: Gemini API access for Claude Code and the CLI: text generation, multimodal analysis, structured output, embeddings, plan review, search grounding, media generation, files, caching, and more.
disable-model-invocation: true
---

## Usage

Claude Code entry point:

`python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`

Direct CLI from a checkout:

`python3 scripts/gemini_run.py <command> [args]`

This skill does not auto-start. Invoke `/gemini ...` explicitly when you want Claude Code to use it.

## Configuration

The launcher resolves canonical Gemini env keys from the current working directory before dispatch:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env

Supported keys:

- `GEMINI_API_KEY`
- `GEMINI_IS_SDK_PRIORITY`
- `GEMINI_IS_RAWHTTP_PRIORITY`
- `GEMINI_LIVE_TESTS`

## How transport works

All commands route through `scripts/gemini_run.py`. The launcher bootstraps env, re-execs into `${CLAUDE_SKILL_DIR}/.venv/bin/python` when the skill venv exists, then dispatches to the selected adapter. Adapters call the shared transport facade, which chooses the SDK or raw HTTP backend based on the routing env flags. The CLI surface and normalized output stay the same regardless of backend.

## Rules

- Mutating operations require `--execute`.
- Privacy-sensitive commands (`search`, `maps`, `computer_use`, `deep_research`) are intentionally invoked only when the caller chooses them.
- Pass user input as single quoted argv values.
- Use `--session <id>` or `--continue` for multi-turn text sessions.
- `plan_review` supports one-turn review with a proposal argument or an interactive REPL when run without one from a TTY.
- Large text responses and generated media save to a file and print the path.

## Quick commands

- `help`
- `models`
- `text "prompt"`
- `multimodal "prompt" --file path.pdf`
- `plan_review "review this plan"`
- `plan_review`
- `embed "text"`
- `image_gen "prompt" --execute`

See `${CLAUDE_SKILL_DIR}/reference/index.md` for the full command map and `${CLAUDE_SKILL_DIR}/reference/plan_review.md` for the new planning workflow.
