# How It Works

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

This is the runtime path for both the Claude Code skill and the direct CLI.

## 1. Entry point

Claude Code runs:

```text
/gemini text "hello"
```

which invokes:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" text "hello"
```

Direct CLI use is the same launcher from a checkout:

```bash
python3 scripts/gemini_run.py text "hello"
```

## 2. Launcher bootstraps env from the current working directory

`scripts/gemini_run.py` and `scripts/health_check.py` both call the shared runtime-env bootstrap before dispatch. The lookup order is:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env

Only the canonical Gemini keys are imported into `os.environ`.

## 3. Launcher re-execs into the skill venv when available

After env bootstrap, `scripts/gemini_run.py` re-execs under `.venv/bin/python` if the skill-local virtual environment exists. That keeps the SDK path available without changing the CLI surface.

## 4. Dispatcher selects the adapter

`core/cli/dispatch.py` validates the command against the allowlist, loads the adapter module, builds the parser, applies policy checks such as privacy-sensitive and mutating-operation rules, then calls the adapter.

Examples:

- `text` → `adapters.generation.text`
- `plan_review` → `adapters.generation.plan_review`
- `multimodal` → `adapters.generation.multimodal`

## 5. Adapter builds the request

Adapters:

- validate arguments
- select a model
- construct the Gemini request body
- call the shared transport facade
- normalize and emit output

`plan_review` is built on the same `generateContent` path as `text`, but it adds:

- a fixed plan-review system prompt
- strict `VERDICT: APPROVED` / `VERDICT: REVISE` output normalization
- a dedicated review-session directory at `~/.config/gemini-skill/plan-review-sessions/`

## 6. Transport chooses the backend

The coordinator picks the SDK or raw HTTP transport from:

- `GEMINI_IS_SDK_PRIORITY`
- `GEMINI_IS_RAWHTTP_PRIORITY`

The output contract is backend-agnostic. Adapters receive the same normalized response shape no matter which backend handled the request.

## 7. Output is emitted safely

- Normal text prints to stdout.
- Large text responses save to a file and print the saved path.
- Media outputs always save to files.
- Session-enabled commands persist history under `~/.config/gemini-skill/`.

That flow is the same whether you started from Claude Code or directly from the terminal.
