# Installation

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

## Install Paths

### Recommended: bootstrap installer

```bash
uvx gemini-skill-install
```

Fallback:

```bash
uvx --python 3.13 gemini-skill-install
```

Or with `pipx`:

```bash
pipx run --spec git+https://github.com/reshinto/gemini-skill.git gemini-skill-install
```

### From a clone

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

Both installer paths copy the runtime payload into `~/.claude/skills/gemini/`, create or reuse `~/.claude/skills/gemini/.venv`, install the pinned `google-genai` dependency, and merge the canonical env block into `~/.claude/settings.json`.

## Runtime Configuration

The launcher uses the current working directory for config lookup, whether the command is started from Claude Code or directly from the CLI.

Per-key precedence:

1. `./.env`
2. `./.claude/settings.local.json`
3. `./.claude/settings.json`
4. `~/.claude/settings.json`
5. existing process env

Canonical keys:

```text
GEMINI_API_KEY
GEMINI_IS_SDK_PRIORITY
GEMINI_IS_RAWHTTP_PRIORITY
GEMINI_LIVE_TESTS
```

### `.env` for repo-local CLI use

```bash
cp .env.example .env
```

Example:

```dotenv
GEMINI_API_KEY=
GEMINI_IS_SDK_PRIORITY=true
GEMINI_IS_RAWHTTP_PRIORITY=false
GEMINI_LIVE_TESTS=0
```

### Project-local Claude settings

`./.claude/settings.local.json` is appropriate for machine-local secrets in a working project:

```json
{
  "env": {
    "GEMINI_API_KEY": "AIzaSy..."
  }
}
```

`./.claude/settings.json` is lower priority and is typically shared project configuration. Do not put secrets there unless that is an intentional team decision.

### Global Claude settings

The installer writes the canonical defaults to `~/.claude/settings.json`:

```json
{
  "env": {
    "GEMINI_API_KEY": "AIzaSy...",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0"
  }
}
```

`GEMINI_API_KEY` is the only supported secret name. `GOOGLE_API_KEY` is ignored.

## Verify Installation

Inside Claude Code:

```text
/gemini help
```

From a checkout:

```bash
python3 scripts/gemini_run.py help
python3 scripts/gemini_run.py text "hi"
```

Installed health check:

```bash
python3 ~/.claude/skills/gemini/scripts/health_check.py
```

## Common Problems

### `No GEMINI_API_KEY found`

Check the current directory first:

```bash
pwd
ls -a
ls -a .claude
```

The launcher reads config from the directory you started the command in, not from the installed skill directory.

### Claude Code still uses old settings

Fully restart Claude Code after editing `~/.claude/settings.json`. A window reload is not enough because Claude injects env at session start.

### `plan_review` without a prompt exits immediately

That is expected when stdin is non-interactive. Use:

```bash
python3 scripts/gemini_run.py plan_review "review this plan"
```

or run `plan_review` with no proposal from a real terminal to start the REPL.
