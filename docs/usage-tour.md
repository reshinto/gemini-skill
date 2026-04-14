# Usage Tour

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

This page focuses on runnable workflows. The same commands work from Claude Code and from the CLI.

## 1. Quick text response

Claude Code:

```text
/gemini text "Write a haiku about debugging"
```

CLI:

```bash
python3 scripts/gemini_run.py text "Write a haiku about debugging"
```

## 2. Continue a text session

```bash
python3 scripts/gemini_run.py text "Plan a Japan trip" --session travel-2026
python3 scripts/gemini_run.py text "Focus on food this time" --session travel-2026
python3 scripts/gemini_run.py text "Now focus on accommodations" --continue
```

Session files are written to `~/.config/gemini-skill/sessions/<id>.json`.

## 3. Review an implementation plan once

```bash
python3 scripts/gemini_run.py plan_review "Review this database migration plan for missing tests and rollback gaps"
```

Expected shape:

```text
VERDICT: REVISE
Add a rollback step for the index migration and specify how backfill failures are detected.
```

## 4. Run an interactive plan review conversation

```bash
python3 scripts/gemini_run.py plan_review
```

Inside the REPL:

```text
plan_review> Migrate auth tokens to the new table.
VERDICT: REVISE
...
plan_review> Add a dual-write phase and rollback switch.
VERDICT: APPROVED
plan_review> /done
```

`plan_review` stores review conversations under `~/.config/gemini-skill/plan-review-sessions/`.

## 5. Analyze a document

```bash
python3 scripts/gemini_run.py multimodal \
  "Summarize the key findings in this report" \
  --file /path/to/report.pdf
```

## 6. Produce structured JSON

```bash
python3 scripts/gemini_run.py structured \
  "Extract name and email from: Ada Lovelace, ada@example.com" \
  --schema '{"type":"object","properties":{"name":{"type":"string"},"email":{"type":"string"}},"required":["name","email"]}'
```

## 7. Ground a response in current search results

```bash
python3 scripts/gemini_run.py search "latest Gemini SDK release notes"
```

Use privacy-sensitive commands only when the task actually requires them.

## 8. Generate an image

```bash
python3 scripts/gemini_run.py image_gen \
  "A diagram poster showing a dual-backend transport layer" \
  --execute
```

The command writes the output file and prints the saved path instead of raw binary data.

## 9. Manage files

```bash
python3 scripts/gemini_run.py files upload dataset.csv --execute
python3 scripts/gemini_run.py files list
python3 scripts/gemini_run.py files get files/abc123
```

## 10. Decide which entry point to use

- Use `/gemini ...` when you want Claude Code to orchestrate the command inside the current task.
- Use `python3 scripts/gemini_run.py ...` when you want the same behavior directly from a terminal or during local development.
- In both cases, configuration is resolved from the current working directory before dispatch.
