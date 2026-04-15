[![CI](https://github.com/reshinto/gemini-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/reshinto/gemini-skill/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gemini-skill-install)](https://pypi.org/project/gemini-skill-install/)
[![Downloads](https://static.pepy.tech/badge/gemini-skill-install/month)](https://pepy.tech/project/gemini-skill-install)

# gemini-skill

`gemini-skill` is a Gemini API front end that works in two modes:

- as a Claude Code skill via `/gemini ...`
- as a direct CLI via `python3 scripts/gemini_run.py ...`

It exposes the same command surface in both modes: text, multimodal analysis, structured output, embeddings, Files API, image/video/music generation, file search, deep research, and iterative plan review.

## Quick Start

### Install for Claude Code

Recommended:

```bash
uvx gemini-skill-install
```

Fallback:

```bash
uvx --python 3.13 gemini-skill-install
```

Or from a clone:

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

The installer copies the runtime payload into `~/.claude/skills/gemini/`, creates or reuses `~/.claude/skills/gemini/.venv`, installs the pinned `google-genai` SDK, and writes the canonical env block into `~/.claude/settings.json`.

### Configure credentials
Create a Gemini API key in Google AI Studio:

- Google AI Studio: https://aistudio.google.com/
- API key guide: https://ai.google.dev/gemini-api/docs/api-key

The Gemini API is not an unlimited flat-rate service. Google offers a free tier for getting started and a paid pay-as-you-go tier for higher-volume or production use. If you enable the paid tier, prompts and responses can incur usage-based charges depending on the model and features you use.

The launcher resolves canonical Gemini env keys from the current working directory first, then Claude settings files, then existing process env:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env

Supported keys:

```text
GEMINI_API_KEY
GEMINI_IS_SDK_PRIORITY
GEMINI_IS_RAWHTTP_PRIORITY
GEMINI_LIVE_TESTS
```

For repo-local CLI use:

```bash
cp .env.example .env
```

`GEMINI_API_KEY` is the only supported secret name. `GOOGLE_API_KEY` is ignored.

### Use it from Claude Code

The skill manifest sets `disable-model-invocation: true`, so Claude Code will not start this skill on its own. Invoke it explicitly first.

```text
/gemini text "Explain quantum computing in three sentences"
/gemini plan_review "Review this implementation plan for gaps and rollout risks"
```

### Use it as a direct CLI

From a checkout:

```bash
python3 scripts/gemini_run.py text "hi"
python3 scripts/gemini_run.py plan_review "Review this migration plan"
python3 scripts/gemini_run.py plan_review
```

The last command starts the interactive `plan_review` REPL when stdin is a TTY.

## Core Workflows

- `text` for one-shot prompts and multi-turn sessions
- `plan_review` for iterative plan review, either one-turn or REPL
- `multimodal` for PDFs, images, audio, video, and URLs
- `structured` for schema-constrained JSON output
- `embed`, `token_count`, `files`, `cache`, `batch`, and `file_search`
- `image_gen`, `imagen`, `video_gen`, and `music_gen`
- `search`, `maps`, `computer_use`, `deep_research`, and `live`

## Documentation

- [docs/install.md](docs/install.md) — install paths, env precedence, troubleshooting
- [docs/usage.md](docs/usage.md) — Claude Code skill usage and direct CLI usage
- [docs/usage-tour.md](docs/usage-tour.md) — end-to-end examples
- [docs/commands.md](docs/commands.md) — command index by capability family
- [reference/index.md](reference/index.md) — per-command reference pages
- [docs/security.md](docs/security.md) — secrets handling, local data storage, privacy notes
- [docs/how-it-works.md](docs/how-it-works.md) — launcher, dispatch, transport, and output flow
- [docs/README.md](docs/README.md) — documentation hub

## Backend Routing

The launcher and adapters are backend-agnostic. The transport coordinator chooses the SDK or raw HTTP backend from the two routing flags:

- `GEMINI_IS_SDK_PRIORITY=true`
- `GEMINI_IS_RAWHTTP_PRIORITY=false`

Both backends produce the same normalized response shape for callers.

## License

MIT
