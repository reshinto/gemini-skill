# Documentation Index

[← Back to README](../README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

`gemini-skill` can be used as a Claude Code skill or as a direct CLI. This hub groups every user-facing doc around that shared command surface.

## Start Here

- [install.md](install.md) — Claude Code skill install: paths, payload, verification
- [cli.md](cli.md) — direct CLI install and usage (pipx / uvx / clone)
- [usage.md](usage.md) — quickstart for `/gemini` and `python3 scripts/gemini_run.py`
- [usage-tour.md](usage-tour.md) — runnable end-to-end workflows
- [commands.md](commands.md) — command families and quick routing
- [flags-reference.md](flags-reference.md) — every CLI flag, grouped by topic

## Capabilities (split by category)

- [capabilities.md](capabilities.md) — category index
- [capabilities-generation.md](capabilities-generation.md) — text, streaming, plan_review, multimodal, structured
- [capabilities-tools.md](capabilities-tools.md) — function_calling, code_exec, search, maps
- [capabilities-data.md](capabilities-data.md) — embed, token_count, files, cache, batch, file_search
- [capabilities-media.md](capabilities-media.md) — image_gen, imagen, video_gen, music_gen
- [capabilities-experimental.md](capabilities-experimental.md) — computer_use, deep_research, live

## Models

- [models-reference.md](models-reference.md) — catalog and cost tiers
- [model-routing.md](model-routing.md) — how the router picks a model

## Architecture and Design

- [architecture.md](architecture.md) — overview, runtime path, module map
- [architecture-transport.md](architecture-transport.md) — dual-backend transport, coordinator, policy
- [architecture-installer.md](architecture-installer.md) — installer payload, venv, checksums
- [design-patterns.md](design-patterns.md) — implementation pattern catalog
- [system-design.md](system-design.md) — scalability, reliability, trade-offs

## Operational

- [security.md](security.md) — secret handling, local storage, privacy notes
- [update-sync.md](update-sync.md) — updating, reinstalling, release publishing

## Contributor Docs

- [contributing.md](contributing.md) — contribution overview
- [contributing-adapters.md](contributing-adapters.md) — adding a new command adapter
- [contributing-workflow.md](contributing-workflow.md) — PR, commit, and release workflow
- [testing.md](testing.md) — testing overview
- [testing-unit.md](testing-unit.md) — unit tests, fixtures, coverage
- [testing-integration.md](testing-integration.md) — live API matrix, backend parity
- [testing-smoke.md](testing-smoke.md) — clean-install smoke, upgrade path
- [python-guide.md](python-guide.md) — Python version and coding conventions

## Most Useful References

- [../reference/index.md](../reference/index.md) — per-command reference hub
- [../reference/text.md](../reference/text.md)
- [../reference/plan_review.md](../reference/plan_review.md)
- [../reference/multimodal.md](../reference/multimodal.md)
- [../reference/image_gen.md](../reference/image_gen.md)
- [../reference/files.md](../reference/files.md)

## Notes

- The current working directory controls env lookup.
- `disable-model-invocation: true` means Claude Code must be prompted to use `/gemini ...`; it will not start the skill automatically.
- `reference/` covers command syntax in detail. `docs/` covers installation, workflows, behavior, and design.
