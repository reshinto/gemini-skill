# gemini-skill

A Claude Code skill for broad Gemini REST API access — text generation, multimodal input, image/video/music generation, embeddings, caching, batch processing, search grounding, code execution, file search, and more.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/reshinto/gemini-skill.git
   cd gemini-skill
   ```

2. **Install the skill** (copies operational files to `~/.claude/skills/gemini/`)
   ```bash
   python3 setup/install.py
   ```
   The installer creates `~/.claude/skills/gemini/.env` from `.env.example` on first run.

3. **Set your Gemini API key** (get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))

   Pick **one** of:

   **Option A — edit the installed `.env` file** (recommended for persistent use):
   ```bash
   # Open the installed .env (NOT the repo's .env — the skill reads this file)
   $EDITOR ~/.claude/skills/gemini/.env
   # Set: GEMINI_API_KEY=your_key_here
   ```
   The skill loads this file automatically at runtime — no shell export needed. Do **not** edit the repo-root `.env`; the installed skill doesn't read it.

   **Option B — shell environment variable** (overrides the `.env` file):
   ```bash
   export GEMINI_API_KEY=your_key_here
   ```

   Precedence: shell env wins over the `.env` file. See [docs/install.md](docs/install.md#api-key-setup) for full details.

4. **Fully restart Claude Code** (⌘Q on macOS, not "Reload Window"). Skill discovery happens at IDE launch; a new in-process session won't pick up a newly installed skill.

5. **Use it in Claude Code**
   ```
   /gemini text "Explain quantum computing"
   ```

## Features

- Text generation, multimodal input, structured output, function calling
- Image generation (Nano Banana family), video generation (Veo), music generation (Lyria 3)
- Embeddings, context caching, batch processing, token counting
- Google Search grounding, Google Maps grounding, code execution
- File API, File Search / hosted RAG
- Deep Research (Interactions API), Computer Use (preview)
- Automatic model routing by task type and complexity
- Two-phase cost tracking (pre-flight estimate + post-response)
- Multi-turn conversation sessions with Gemini
- Zero runtime dependencies — Python 3.9+ stdlib only

## Prerequisites

- Python 3.9+
- A Gemini API key

## Documentation

See [docs/](docs/) for full documentation including:
- [Architecture](docs/architecture.md) — System design and module layout
- [How It Works](docs/how-it-works.md) — End-to-end execution trace
- [Installation](docs/install.md) — Setup, troubleshooting, API key configuration
- [Commands](docs/commands.md) — Command index by capability family
- [Capabilities](docs/capabilities.md) — Feature overview with status and limitations
- [Model Routing](docs/model-routing.md) — Router decision tree and model selection
- [Security](docs/security.md) — Threat model, auth, data protection
- [Usage](docs/usage.md) — Getting started and common workflows
- [Testing](docs/testing.md) — Running tests, writing tests, coverage, live API smoke tests
- [Python Design](docs/python-guide.md) — Stdlib-only architecture, Python 3.9+ floor
- [Contributing](docs/contributing.md) — Adding adapters, code style, PRs
- [Update & Sync](docs/update-sync.md) — Install mechanism, rollback, registry updates

See also:
- [Per-command reference](reference/index.md) — Detailed docs for all 19 commands

## License

MIT
