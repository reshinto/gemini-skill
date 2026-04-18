# Documentation Index

[← Back to README](../README.md) · [Reference index](../reference/index.md)

`gemini-skill` can be used as a Claude Code skill or as a direct CLI. This hub keeps the user-facing docs aligned around that shared command surface.

## Start Here

- [install.md](install.md) — install paths, env precedence, verification, troubleshooting
- [usage.md](usage.md) — quick start for both `/gemini ...` and `python3 scripts/gemini_run.py ...`
- [usage-tour.md](usage-tour.md) — example workflows, including `plan_review`
- [commands.md](commands.md) — command families and quick routing guide
- [flags-reference.md](flags-reference.md) — shared CLI flags and common invocation patterns
- [reference/index.md](../reference/index.md) — per-command reference pages

## Operational Docs

- [security.md](security.md) — secret handling, local storage, privacy-sensitive operations
- [architecture.md](architecture.md) — runtime path, module layout, and transport design
- [model-routing.md](model-routing.md) — model selection rules
- [models-reference.md](models-reference.md) — model catalog and selection reference
- [capabilities.md](capabilities.md) — capability matrix

## Design Docs

- [design-patterns.md](design-patterns.md) — implementation conventions and reusable patterns

## Contributor Docs

- [contributing.md](contributing.md) — contribution workflow and expectations
- [testing.md](testing.md) — test strategy and test commands
- [python-guide.md](python-guide.md) — Python setup and development guidance
- [update-sync.md](update-sync.md) — keeping installed and checked-out copies aligned

## Most Useful References

- [reference/text.md](../reference/text.md)
- [reference/plan_review.md](../reference/plan_review.md)
- [reference/multimodal.md](../reference/multimodal.md)
- [reference/image_gen.md](../reference/image_gen.md)
- [reference/files.md](../reference/files.md)

## Notes

- The current working directory controls env lookup.
- `disable-model-invocation: true` means Claude Code must be prompted to use `/gemini ...`; it will not start the skill automatically.
- `reference/` covers command syntax in detail. `docs/` covers installation, workflows, behavior, and design.
