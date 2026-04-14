# Documentation Index

[← Back to README](../README.md) · [Reference index](../reference/index.md)

---

This is the main hub for gemini-skill documentation. Every guide, reference, and explanation lives here or in the `reference/` folder.

## Getting Started

- **[Installation](install.md)** — How to set up the skill via `uvx` / `pipx` or from a clone, install the SDK, and configure your API key.
- **[Usage Tour](usage-tour.md)** — 16 end-to-end examples covering text generation, multimodal analysis, image generation, batch processing, and more.
- **[Quick Commands](../SKILL.md)** — Terse reference from Claude Code's context (the bare minimum to invoke the skill).

## Understanding the Design

- **[Architecture](architecture.md)** — High-level overview of how the dual-backend system works, why SKILL.md is terse, and how data flows through the skill.
- **[Design Patterns](design-patterns.md)** — Catalog of 16 architectural patterns used in the codebase: Adapter, Facade, Strategy, etc. Each pattern includes what, where, why, and how.
- **[How It Works](how-it-works.md)** — Detailed walkthrough of the request lifecycle: from CLI to SDK/raw HTTP to Gemini API to normalization to output.

## Making Decisions

- **[Models Reference](models-reference.md)** — Every available model, with cost, capabilities, and when to pick each one. Answer to "which model should I use?"
- **[Flags Reference](flags-reference.md)** — Every CLI flag, grouped by category (execution, privacy, cost, I/O, tuning). Answer to "what does --flag do?"
- **[Commands](commands.md)** — Legacy reference of all top-level commands.

## Deep Dives

- **[Security](security.md)** — API key storage, threat model, how the skill keeps secrets safe, and why it's secure. Covers settings.json security profile, atomic writes, redaction, and traceback scrubbing.
- **[Capabilities](capabilities.md)** — Which models support which features (multimodal, search grounding, maps, computer use, etc.) and when each capability is useful.
- **[Model Routing](model-routing.md)** — How the dispatch system chooses which model and backend to use for each request.
- **[Python Guide](python-guide.md)** — How to use gemini-skill from Python code (importing adapters, using the transport layer).
- **[Testing](testing.md)** — How to run unit tests, integration tests, and smoke tests. Coverage targets, CI/CD setup.
- **[Contributing](contributing.md)** — Code style, PR process, and contribution guidelines.
- **[Update & Sync](update-sync.md)** — Release checking, reinstall/update paths, GitHub Releases, and PyPI publishing.

## Command-Specific Guides

For detailed guides on individual commands, see `reference/index.md`. Common ones:

- **text** — One-shot and multi-turn text generation
- **multimodal** — Analyze files (PDFs, images, video, audio)
- **structured** — Extract JSON data matching a schema
- **image_gen** — Generate images (Gemini-native or Imagen)
- **video_gen** — Generate short videos
- **batch** — High-volume processing with 50% cost savings
- **cache** — Context caching for large prompts
- **search** — Web search grounding
- **function_calling** — Let the model call your tools
- **embed** — Generate text embeddings

See `reference/index.md` for the complete list (21 commands).

## Reference Organization

Every command has a reference page under `reference/` with the structure:

1. **What** — One-sentence purpose
2. **Which** — Which models support this
3. **Why** — When to use this vs alternatives
4. **How** — Usage examples, common flags, error handling

---

## Navigation by Use Case

### "I want to generate text"
- Start: [Usage Tour §2](usage-tour.md#2-one-shot-text-generation) (simple text)
- Then: [Usage Tour §3](usage-tour.md#3-multi-turn-session) (conversations)
- Reference: [reference/text.md](../reference/text.md)

### "I want to analyze files"
- Start: [Usage Tour §4](usage-tour.md#4-multimodal-analysis-pdf--prompt)
- Reference: [reference/multimodal.md](../reference/multimodal.md)

### "I want to generate images"
- Start: [Usage Tour §9-10](usage-tour.md#9-image-generation-gemini-native)
- Decision: [Models Reference (Image section)](models-reference.md#image-generation-models)
- Reference: [reference/image_gen.md](../reference/image_gen.md)

### "I want to understand costs"
- Start: [Usage Tour §15](usage-tour.md#15-cost-tracking--interpretation)
- Deep dive: [Flags Reference (--cost-breakdown)](flags-reference.md#--cost-breakdown)
- Reference: [reference/batch.md](../reference/batch.md) (cheapest way to process bulk data)

### "I'm worried about security"
- Start: [Architecture (Why SKILL.md is terse)](architecture.md#why-skillmd-is-terse)
- Deep dive: [Security (Secrets storage)](security.md#how-the-skill-stores-secrets-and-why-its-safe)
- Reference: [reference/settings.md](../reference/settings.md)

### "I want to read the code"
- Start: [Design Patterns](design-patterns.md)
- Then: [Architecture (Architecture overview)](architecture.md)
- For implementation: Look at the pattern's "Where" link to the actual file

### "Something broke"
- Check: [reference/troubleshooting.md](../reference/troubleshooting.md)
- Or run: `python3 ~/.claude/skills/gemini/scripts/health_check.py`

---

## All Documentation Files

### Guides (How To)

| File | Purpose |
|------|---------|
| [install.md](install.md) | Step-by-step installation |
| [usage-tour.md](usage-tour.md) | 16 end-to-end examples |
| [how-it-works.md](how-it-works.md) | Request lifecycle deep dive |
| [python-guide.md](python-guide.md) | Using the skill from Python code |
| [testing.md](testing.md) | Running tests |
| [contributing.md](contributing.md) | Code contribution guidelines |
| [update-sync.md](update-sync.md) | Keeping the skill up to date and publishing releases |

### Understanding the Design

| File | Purpose |
|------|---------|
| [architecture.md](architecture.md) | High-level architecture |
| [design-patterns.md](design-patterns.md) | 16 architectural patterns |
| [security.md](security.md) | Security and threat model |
| [capabilities.md](capabilities.md) | Model capabilities matrix |
| [model-routing.md](model-routing.md) | Dispatch and routing logic |

### References (What Do I Do?)

| File | Purpose |
|------|---------|
| [flags-reference.md](flags-reference.md) | All CLI flags, grouped |
| [models-reference.md](models-reference.md) | All models with cost/capabilities |
| [commands.md](commands.md) | All top-level commands (legacy) |

---

## Diagrams

The skill uses Mermaid diagrams to illustrate architecture and flows:

- **architecture-dual-backend.svg** — High-level dual-backend architecture
- **coordinator-decision-flow.svg** — Primary/fallback dispatch decision tree
- **backend-priority-matrix.svg** — SDK priority vs raw HTTP priority decision matrix
- **auth-resolution.svg** — How the skill resolves the API key
- **install-flow.svg** — Installation step-by-step
- **secrets-flow.svg** — Data flow of the API key from settings.json to API header
- **design-patterns-overview.svg** — Class diagram of core patterns
- **command-dispatch-flow.svg** — Sequence diagram of a single command invocation
- **token-optimization-flow.svg** — Why SKILL.md stays small and reference files are on-demand

---

## FAQ

**Q: Which documentation should I read first?**
A: Start with [Usage Tour](usage-tour.md) for concrete examples. Then read [Architecture](architecture.md) to understand the big picture. Dig into command-specific `reference/*.md` files as needed.

**Q: I just want to use the skill. Do I need to read all this?**
A: No. Read [Installation](install.md), then jump to [Usage Tour](usage-tour.md), then reference the specific `reference/<command>.md` file for commands you want to use.

**Q: I'm reading the code. Where do I start?**
A: Read [Design Patterns](design-patterns.md) first—it names every architectural decision and points to the code. Then read [Architecture](architecture.md) for the high-level flow. Then dive into specific files using the patterns as your guide.

**Q: Why is the documentation so large?**
A: The skill is complex: dual-backend system, 21 commands, 12 models, async/sync paths, security considerations. The documentation matches that complexity. Most users only read 2–3 files (install + usage tour + one command reference). The full docs are here for completeness.

**Q: I found a typo/error in the docs. How do I fix it?**
A: See [Contributing](contributing.md) for the PR process. Docs are treated the same as code.

---

## Last Updated

Last updated: 2026-04-14. Docs are regenerated after every phase of the refactor.

---

## Navigation

- **Back to README:** [../README.md](../README.md)
- **Command Reference:** [../reference/index.md](../reference/index.md)
