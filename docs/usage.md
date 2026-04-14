# Usage

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

`gemini-skill` has one command surface and two entry points.

## Entry Points

### Claude Code skill

```text
/gemini text "What is machine learning?"
```

Because `SKILL.md` has `disable-model-invocation: true`, Claude Code will only use the skill after you invoke it or explicitly direct Claude to run it.

### Direct CLI

From a checkout:

```bash
python3 scripts/gemini_run.py text "What is machine learning?"
```

Installed copy:

```bash
python3 ~/.claude/skills/gemini/scripts/gemini_run.py text "What is machine learning?"
```

## Common Commands

### One-shot text

```bash
python3 scripts/gemini_run.py text "Summarize the repository architecture"
```

### Multi-turn text session

```bash
python3 scripts/gemini_run.py text "Start a migration checklist" --session migration
python3 scripts/gemini_run.py text "Now focus on rollback risk" --continue
```

Text sessions are stored at `~/.config/gemini-skill/sessions/<id>.json`.

### Plan review

One-turn review:

```bash
python3 scripts/gemini_run.py plan_review "Review this rollout plan for gaps"
```

Interactive review loop:

```bash
python3 scripts/gemini_run.py plan_review
```

`plan_review` starts with `VERDICT: APPROVED` or `VERDICT: REVISE`. Its dedicated review sessions live under `~/.config/gemini-skill/plan-review-sessions/`.

### Multimodal analysis

```bash
python3 scripts/gemini_run.py multimodal "Summarize this PDF" --file report.pdf
```

### Structured output

```bash
python3 scripts/gemini_run.py structured "Extract fields" --schema schema.json
```

### Search grounding

```bash
python3 scripts/gemini_run.py search "latest changes to the Gemini API"
```

### Media generation

```bash
python3 scripts/gemini_run.py image_gen "A technical blueprint poster" --execute
```

## Configuration Reminder

The launcher resolves env from the current working directory in this order:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env

That behavior is the same for the Claude Code skill and for direct CLI use.

## Where To Go Next

- [usage-tour.md](usage-tour.md) for runnable examples
- [commands.md](commands.md) for the command map
- [reference/index.md](../reference/index.md) for per-command details
