[![CI](https://github.com/reshinto/gemini-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/reshinto/gemini-skill/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gemini-skill-install)](https://pypi.org/project/gemini-skill-install/)
[![Downloads](https://static.pepy.tech/badge/gemini-skill-install/month)](https://pepy.tech/project/gemini-skill-install)

# gemini-skill

A Gemini API front end with two entry points:

- **Claude Code skill:** `/gemini <command> [args]`
- **Direct CLI:** `python3 scripts/gemini_run.py <command> [args]` or the `gemini-skill-install` launcher

Same command surface in both: text, multimodal analysis, structured output, embeddings, Files API, image/video/music generation, file search, deep research, and iterative plan review.

## Install

**Claude Code skill (recommended):**

```bash
uvx gemini-skill-install
```

Fallback: `uvx --python 3.13 gemini-skill-install`. See [docs/install.md](docs/install.md).

**Direct CLI (no Claude Code required):**

```bash
pipx install gemini-skill-install
# or from a clone:
git clone https://github.com/reshinto/gemini-skill.git && cd gemini-skill
python3 -m venv .venv && source .venv/bin/activate
pip install -r setup/requirements.txt
```

See [docs/cli.md](docs/cli.md) for full CLI setup.

## Configure

Set `GEMINI_API_KEY` (the only supported key; `GOOGLE_API_KEY` is ignored). The launcher merges keys from all sources below; later entries override earlier ones, so **`./.env` wins** and `existing process env` is the fallback:

1. existing process env (lowest priority)
2. `~/.claude/settings.json`
3. `./.claude/settings.json`
4. `./.claude/settings.local.json`
5. `./.env` (highest priority)

Full details and examples: [docs/security.md](docs/security.md).

## Example

Claude Code:

```text
/gemini text "Explain quantum computing in three sentences"
```

Direct CLI:

```bash
python3 scripts/gemini_run.py text "Explain quantum computing in three sentences"
```

Interactive plan-review REPL (CLI only):

```bash
python3 scripts/gemini_run.py plan_review
```

## Docs

- [docs/README.md](docs/README.md) — documentation hub
- [docs/install.md](docs/install.md) — skill install paths and verification
- [docs/cli.md](docs/cli.md) — CLI install and usage
- [docs/usage.md](docs/usage.md) — quickstart across both entry points
- [docs/usage-tour.md](docs/usage-tour.md) — end-to-end examples
- [docs/commands.md](docs/commands.md) — command families
- [docs/architecture.md](docs/architecture.md) — module layout
- [docs/system-design.md](docs/system-design.md) — scalability, reliability, fallbacks
- [docs/design-patterns.md](docs/design-patterns.md) — patterns used
- [docs/security.md](docs/security.md) — secret handling
- [reference/index.md](reference/index.md) — per-command reference

## License

MIT
