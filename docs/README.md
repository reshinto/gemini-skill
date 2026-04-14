# Documentation Index

[← Back to README](../README.md) · [Reference index](../reference/index.md)

`gemini-skill` can be used as a Claude Code skill or as a direct CLI. This hub keeps the user-facing docs aligned around that shared command surface.

## Start Here

- [install.md](install.md) — install paths, env precedence, verification, troubleshooting
- [usage.md](usage.md) — quick start for both `/gemini ...` and `python3 scripts/gemini_run.py ...`
- [usage-tour.md](usage-tour.md) — example workflows, including `plan_review`
- [commands.md](commands.md) — command families and quick routing guide
- [reference/index.md](../reference/index.md) — per-command reference pages

## Operational Docs

- [security.md](security.md) — secret handling, local storage, privacy-sensitive operations
- [how-it-works.md](how-it-works.md) — launcher bootstrap, dispatch, transport, output flow
- [architecture.md](architecture.md) — module layout and transport design
- [model-routing.md](model-routing.md) — model selection rules
- [capabilities.md](capabilities.md) — capability matrix

## Contributor Docs

- [contributing.md](contributing.md)
- [testing.md](testing.md)
- [python-guide.md](python-guide.md)
- [update-sync.md](update-sync.md)

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
