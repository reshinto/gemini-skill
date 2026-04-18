# Direct CLI Install and Usage

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

`gemini-skill` can run independently of Claude Code. This page is the canonical reference for the direct-CLI path. If you are using the skill inside Claude Code, see [install.md](install.md) and [usage.md](usage.md) instead.

## Install options

### Option A: pipx (PyPI)

```bash
pipx install gemini-skill-install
gemini-skill-install --help
```

The `gemini-skill-install` console script is the bootstrap installer package. It provisions the skill payload and venv at `~/.claude/skills/gemini/`, then exits. For a developer checkout that lets you run commands directly from the repo, use Option C.

### Option B: uvx one-shot

```bash
uvx gemini-skill-install
# pin the interpreter if system python is older than 3.9
uvx --python 3.13 gemini-skill-install
```

### Option C: from a clone (developer setup)

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 -m venv .venv
source .venv/bin/activate
pip install -r setup/requirements.txt

# optional dev extras (tests, linters, coverage)
pip install -r setup/requirements-dev.txt
```

From a clone you use the launcher directly:

```bash
python3 scripts/gemini_run.py text "hello"
```

## Configure credentials

Set `GEMINI_API_KEY`. The launcher merges values from all sources below; later entries override earlier ones, so **`./.env` wins** and `existing process env` is the fallback:

1. existing process env (lowest priority)
2. `~/.claude/settings.json`
3. `./.claude/settings.json`
4. `./.claude/settings.local.json`
5. `./.env` (highest priority)

`.env` template:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY=<your key>
```

Full detail on secrets and storage: [security.md](security.md).

## Usage examples

### Single-turn text

```bash
python3 scripts/gemini_run.py text "Summarize the CAP theorem in three sentences"
```

### Multi-turn session

```bash
python3 scripts/gemini_run.py text "Plan a Japan trip" --session travel
python3 scripts/gemini_run.py text "Focus on food"     --continue
```

Session files are written to `~/.config/gemini-skill/sessions/<id>.json`.

### Multimodal input

```bash
python3 scripts/gemini_run.py multimodal "Describe this PDF" --file ./paper.pdf
```

### Structured JSON

```bash
python3 scripts/gemini_run.py structured "Extract name, date, total" \
  --schema '{"type":"object","properties":{"name":{"type":"string"},"date":{"type":"string"},"total":{"type":"number"}}}' \
  --file ./invoice.png
```

### Plan-review REPL

```bash
python3 scripts/gemini_run.py plan_review           # interactive REPL when stdin is a TTY
python3 scripts/gemini_run.py plan_review "Review"  # one-shot
```

### Mutating commands (require `--execute`)

```bash
python3 scripts/gemini_run.py image_gen "A red apple on an oak table" --execute
python3 scripts/gemini_run.py video_gen "Timelapse of a sunrise"      --execute
```

Dry-run is the default for any command that writes files or spends quota.

## Verify your install

```bash
python3 scripts/health_check.py
```

Expected output sections:

- Python version and interpreter path
- Backend and venv resolution
- API key presence (without printing the key)
- API connectivity probe
- Install integrity (SHA-256 checksum comparison)

## Troubleshooting

- **"requires Python 3.9+"** — upgrade the interpreter; the launcher is 2.7-safe and refuses older Python.
- **`GEMINI_API_KEY` not picked up** — verify the current working directory and rerun `python3 scripts/health_check.py`. The launcher anchors lookup to `cwd`.
- **`GOOGLE_API_KEY` set but not used** — expected. Only `GEMINI_API_KEY` is honored.
- **Fresh HOME produces no skill output** — see [install.md](install.md) for `${CLAUDE_SKILL_DIR}` and payload setup.

## See also

- [usage.md](usage.md) — quickstart across Claude Code and CLI
- [usage-tour.md](usage-tour.md) — end-to-end examples
- [commands.md](commands.md) — command routing
- [flags-reference.md](flags-reference.md) — every CLI flag
- [reference/index.md](../reference/index.md) — per-command reference
- [architecture.md](architecture.md) — module layout
