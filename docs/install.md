# Installation

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

> **Direct CLI install?** See [docs/cli.md](cli.md) instead.

![Install flow](diagrams/install-flow.svg)
<sub>Source: [`docs/diagrams/install-flow.mmd`](diagrams/install-flow.mmd)</sub>

## Install options

All four paths install into `~/.claude/skills/gemini/` and merge the canonical
env block into `~/.claude/settings.json`.

**Recommended — zero-clone bootstrap:**

```bash
uvx gemini-skill-install
```

If `uvx` defaults to an older Python:

```bash
uvx --python 3.13 gemini-skill-install
```

**With `pipx` (from GitHub):**

```bash
pipx run --spec git+https://github.com/reshinto/gemini-skill.git gemini-skill-install
```

**From a clone:**

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

Pass `-y` / `--yes` to skip interactive prompts in CI.

## What the installer does

The installer copies the following payload into `${CLAUDE_SKILL_DIR}` (`~/.claude/skills/gemini/`):

| Entry | Type |
|---|---|
| `SKILL.md` | root file — Claude Code skill manifest |
| `VERSION` | root file — pinned version string |
| `core/` | directory |
| `adapters/` | directory |
| `reference/` | directory |
| `registry/` | directory |
| `scripts/` | directory |
| `setup/update.py` | setup file — in-place updater |
| `setup/requirements.txt` | setup file — pinned dependencies |

After copying, the installer:

1. Writes `.checksums.json` (SHA-256 manifest) into `${CLAUDE_SKILL_DIR}`; excludes `.venv/` and `__pycache__/`.
2. Creates or reuses `${CLAUDE_SKILL_DIR}/.venv`; pip-installs `setup/requirements.txt`.
3. Prompts for `GEMINI_API_KEY`; merges canonical env defaults into `~/.claude/settings.json`.

On overwrite, `.venv/` and `.env` are preserved.

## Install location

The skill installs to:

```
~/.claude/skills/gemini/
```

Referred to as `${CLAUDE_SKILL_DIR}` throughout the docs. The installer derives this path automatically.

## Verify

Inside Claude Code:

```text
/gemini help
```

From the installed skill directory:

```bash
python3 ~/.claude/skills/gemini/scripts/health_check.py
```

To reinstall or update, see [update-sync.md](update-sync.md).

## Troubleshooting

**`No GEMINI_API_KEY found`**

The launcher resolves config from the *current working directory*, not from
`${CLAUDE_SKILL_DIR}`. Run `pwd` and check that `.env` or `.claude/settings.json`
exists there, or set the key in `~/.claude/settings.json` for global availability.

**`venv not found` / import errors after fresh-HOME setup**

The `.venv` inside `${CLAUDE_SKILL_DIR}` is created during install. If missing,
re-run: `uvx gemini-skill-install --yes`.

**SKILL.md frontmatter rejects non-skill fields**

Claude Code validates SKILL.md frontmatter strictly. Do not add custom keys
to `${CLAUDE_SKILL_DIR}/SKILL.md`; use `.claude/settings.json` env blocks for
runtime configuration instead.

## See also

| Page | Purpose |
|---|---|
| [cli.md](cli.md) | Direct CLI install (pipx, venv, dev setup) |
| [security.md](security.md) | Secrets and API key management |
| [update-sync.md](update-sync.md) | Reinstalling and updating |
| [architecture-installer.md](architecture-installer.md) | Installer internals (coming soon) |
