# Capabilities

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Full capability matrix is split by adapter category. Each page lists the
commands in that category with status, limitations, and use cases.

## Categories

| Category | Commands | Page |
|----------|----------|------|
| Generation | `text`, `streaming`, `plan_review`, `multimodal`, `structured` | [capabilities-generation.md](capabilities-generation.md) |
| Tools | `function_calling`, `code_exec`, `search`, `maps` | [capabilities-tools.md](capabilities-tools.md) |
| Data | `embed`, `token_count`, `files`, `cache`, `batch`, `file_search` | [capabilities-data.md](capabilities-data.md) |
| Media | `image_gen`, `imagen`, `video_gen`, `music_gen` | [capabilities-media.md](capabilities-media.md) |
| Experimental | `computer_use`, `deep_research`, `live` | [capabilities-experimental.md](capabilities-experimental.md) |

## Conventions used on every page

- **Status** — Stable, Preview, or Experimental.
- **Capabilities** — what the command supports.
- **Limitations** — what it does not support, plus any server-side caps.
- **Use cases** — common reasons to pick this command.
- **See** — direct link to the detailed per-command reference under `reference/`.

## See also

- [commands.md](commands.md) — command routing by capability family
- [reference/index.md](../reference/index.md) — per-command reference
- [architecture.md](architecture.md) — module layout
