# Usage Quickstart

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

`gemini-skill` has one command surface and two entry points.

## Claude Code skill

```text
/gemini text "hello"
```

`SKILL.md` sets `disable-model-invocation: true`, so Claude Code only uses the skill when you invoke it explicitly. Install paths: [install.md](install.md). Commands: [commands.md](commands.md).

## direct CLI

```bash
python3 scripts/gemini_run.py text "hello"
```

Install paths, session files, and health-check: [cli.md](cli.md). End-to-end examples: [usage-tour.md](usage-tour.md).

## Shared rules

- Mutating operations require `--execute` (image_gen, video_gen, music_gen, batch writes, file operations). Dry-run is the default.
- Pass user input as single-quoted argv values.
- Use `--session <id>` or `--continue` for multi-turn text.
- Use `plan_review` with no prompt to start the interactive REPL.
- Responses larger than 50 KB are saved to a file; stdout prints only the path.

## Where state lives

- Text sessions: `~/.config/gemini-skill/sessions/<id>.json`
- Plan-review sessions: `~/.config/gemini-skill/plan-review-sessions/<id>.json`
- Installed skill payload: `~/.claude/skills/gemini/`

## Next

- [commands.md](commands.md) — all 23 commands grouped by capability
- [flags-reference.md](flags-reference.md) — every CLI flag
- [reference/index.md](../reference/index.md) — per-command reference
- [usage-tour.md](usage-tour.md) — runnable end-to-end examples
