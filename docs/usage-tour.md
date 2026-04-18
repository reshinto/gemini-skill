# Usage Tour

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Runnable workflows. The same commands work from Claude Code and the direct CLI. Each scenario shows both forms.

## 1. Single-turn text

**Claude Code**
```text
/gemini text "Write a haiku about debugging"
```

**direct CLI**
```bash
python3 scripts/gemini_run.py text "Write a haiku about debugging"
```

## 2. Multi-turn text session

```bash
python3 scripts/gemini_run.py text "Plan a Japan trip"        --session travel
python3 scripts/gemini_run.py text "Focus on food this time"  --continue
python3 scripts/gemini_run.py text "Now on accommodations"    --session travel
```

Session files land at `~/.config/gemini-skill/sessions/travel.json`.

## 3. Multimodal PDF + image analysis

**direct CLI**
```bash
python3 scripts/gemini_run.py multimodal "Summarize this paper" --file ./paper.pdf
python3 scripts/gemini_run.py multimodal "Describe the chart"   --file ./chart.png
```

**Claude Code**
```text
/gemini multimodal "Summarize this paper" --file ./paper.pdf
```

## 4. Structured JSON extraction

```bash
python3 scripts/gemini_run.py structured "Extract name, date, and total amount" \
  --schema '{"type":"object","properties":{"name":{"type":"string"},"date":{"type":"string"},"total":{"type":"number"}}}' \
  --file ./invoice.png
```

## 5. Plan review — one-shot and REPL

**Claude Code (one-shot)**
```text
/gemini plan_review "Review this migration plan for rollback gaps"
```

**direct CLI (REPL when stdin is a TTY)**
```bash
python3 scripts/gemini_run.py plan_review
```

Every response starts with `VERDICT: APPROVED` or `VERDICT: REVISE`. See [reference/plan_review.md](../reference/plan_review.md).

## 6. Image generation (dry-run first, then --execute)

```bash
# dry-run: prints the model, parameters, estimated cost
python3 scripts/gemini_run.py image_gen "A red apple on an oak table"
# actually generate:
python3 scripts/gemini_run.py image_gen "A red apple on an oak table" --execute
```

## 7. Files API — upload, list, delete

```bash
python3 scripts/gemini_run.py files upload ./paper.pdf --execute
python3 scripts/gemini_run.py files list
python3 scripts/gemini_run.py files delete files/<id> --execute
```

## 8. Search grounding

```bash
python3 scripts/gemini_run.py search "Summarize the last week in Rust news"
```

## See also

- [usage.md](usage.md) — quickstart and shared rules
- [commands.md](commands.md) — command routing
- [flags-reference.md](flags-reference.md) — every CLI flag
- [reference/index.md](../reference/index.md) — per-command reference
