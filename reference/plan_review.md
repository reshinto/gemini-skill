# plan_review

Review an implementation plan with Gemini and return a strict verdict line plus concise feedback.

## Usage

Claude Code:

```text
/gemini plan_review "Review this plan for gaps"
```

CLI:

```bash
python3 scripts/gemini_run.py plan_review "Review this plan for gaps"
python3 scripts/gemini_run.py plan_review
```

The second CLI form starts an interactive REPL when stdin is a TTY.

## Flags

- `--model MODEL` — Override the default review model
- `--session ID` — Reuse a named review session
- `--continue` — Continue the most recent review session
- `--thinking on|off` — Explicit thinking mode, default `on`

## Output Contract

Every response starts with exactly one of:

```text
VERDICT: APPROVED
VERDICT: REVISE
```

The remaining lines contain concise human-readable feedback. If the model does not produce a valid verdict line, the adapter normalizes the response to `VERDICT: REVISE`.

## Modes

### One-turn review

```bash
python3 scripts/gemini_run.py plan_review "Review this rollout plan for missing tests"
```

Use this when Claude Code or a shell script needs a single review pass.

### Interactive REPL

```bash
python3 scripts/gemini_run.py plan_review
```

REPL controls:

- `/done` — end the conversation
- `/quit` — exit without continuing
- blank lines — ignored

Review-session files are stored under `~/.config/gemini-skill/plan-review-sessions/`.

## Thinking Behavior

- Default requested model: `gemini-3.1-pro-preview`
- `--thinking on` uses model-appropriate thinking config
- `--thinking off` uses true thinking-off when the selected model supports it
- When the requested model does not support true thinking-off, the adapter falls back in this order:
  - `gemini-2.5-flash`
  - `gemini-2.5-flash-lite`

## Example

```text
VERDICT: REVISE
Call out the rollback plan, define the backfill success metric, and add a test for mixed old/new readers during deployment.
```

[← Back](index.md)
