# Contributing

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Guidelines for extending gemini-skill.

## Quick principles

- **DRY. YAGNI. TDD.** Small commits, frequent commits.
- **Python 3.9+ only.** Every new module starts with `from __future__ import annotations`.
- **100% line + branch coverage** on every new module under `core/`, `adapters/`, `scripts/`, `setup/`, `gemini_skill_install/`.
- **`mypy --strict` clean** on touched modules.
- **Backend-agnostic adapters.** Go through the coordinator facade (`core.transport.api_call` or the `core.infra.client` shim) — never import SDK types directly unless the capability only exists on one backend (see `live`, `imagen`).
- **Dry-run first.** Any command that writes or spends quota requires `--execute`.

## Focus areas

- [contributing-adapters.md](contributing-adapters.md) — how to add a new command/adapter: files to touch, registry wiring, reference page, tests, coverage gate
- [contributing-workflow.md](contributing-workflow.md) — PR workflow, commit style, pre-push hook, release tagging, code-style enforcement

## First-time contributor checklist

1. Read [architecture.md](architecture.md) and [design-patterns.md](design-patterns.md).
2. Set up the dev environment (see [python-guide.md](python-guide.md) and [cli.md](cli.md) option C).
3. Run `bash setup/run_tests.sh` — must be green before you change anything.
4. Pick up an issue or propose a feature in an issue before starting work.
5. Branch from `main`, commit small, open a draft PR early.

## See also

- [architecture.md](architecture.md) — module map
- [design-patterns.md](design-patterns.md) — patterns used in the codebase
- [python-guide.md](python-guide.md) — Python version and annotations policy
- [testing.md](testing.md) — test strategy and commands
- [update-sync.md](update-sync.md) — reinstall/update behavior
