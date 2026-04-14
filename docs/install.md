# Installation

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-14

## Prerequisites

- **Stable CPython 3.9 or later**
- **A Gemini API key** (free; get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- **Claude Code** running in your Claude Code environment

If you install from a clone or release tarball, `setup/install.py` rejects
pre-release, free-threaded, and non-CPython runtimes for the SDK venv. When
possible it automatically re-execs under a compatible `python3.N` found on
`PATH`.

## Quick Install

![Install pipeline](diagrams/install-flow.svg)
<sub>Source: [`diagrams/install-flow.mmd`](diagrams/install-flow.mmd) — regenerate with `bash scripts/render_diagrams.sh`</sub>

### Method 1: Bootstrap installer via `uvx` or `pipx` (recommended)

Install directly from GitHub without cloning:

```bash
uvx --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

or fallback if there are errors

```
uvx --python 3.13 --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

Or with `pipx`:

```bash
pipx run --spec git+https://github.com/reshinto/gemini-skill.git gemini-skill-install
```

or fallback if there are errors

```bash
pipx run --python 3.13 --spec git+https://github.com/reshinto/gemini-skill.git gemini-skill-install

```

Tagged releases also build a PyPI package. After the first published PyPI
release, these simplify to:

```bash
uvx gemini-skill-install
```

or fallback if there are errors

```bash
uvx --python 3.13 gemini-skill-install
```

Or with `pipx`:

```bash
pipx install gemini-skill-install
```

or fallback if there are errors

```bash
pipx install --python 3.13 gemini-skill-install
```

### Method 2: Install from a clone or extracted release tarball

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

Release tarballs use the same flow after extraction:

```bash
tar -xzf gemini-skill-<version>.tar.gz
cd gemini-skill
python3 setup/install.py
```

### Method 3: Manual copy (advanced, not recommended)

Manual copy skips the normal installer safeguards. Use it only if you need to
debug install internals.

```bash
mkdir -p ~/.claude/skills/gemini
cp gemini-skill/SKILL.md gemini-skill/VERSION ~/.claude/skills/gemini/
cp -r gemini-skill/core gemini-skill/adapters gemini-skill/reference \
      gemini-skill/registry gemini-skill/scripts ~/.claude/skills/gemini/
mkdir -p ~/.claude/skills/gemini/setup
cp gemini-skill/setup/update.py gemini-skill/setup/requirements.txt \
   ~/.claude/skills/gemini/setup/
python3 -m venv ~/.claude/skills/gemini/.venv
~/.claude/skills/gemini/.venv/bin/pip install -r ~/.claude/skills/gemini/setup/requirements.txt
```

### What the installer does

Both public installer entry points share the same core install logic. They:

1. Validate Python compatibility and, for `setup/install.py`, re-exec under a stable CPython if needed.
2. Copy the runtime payload into `~/.claude/skills/gemini/`.
3. Write `.checksums.json` for install-integrity drift detection.
4. Create or reuse `~/.claude/skills/gemini/.venv`.
5. Install the pinned `google-genai==1.33.0` from `setup/requirements.txt`.
6. Prompt for `GEMINI_API_KEY` and merge the env block into `~/.claude/settings.json`.

## API Key Setup

### Primary: `~/.claude/settings.json`

The canonical location for the installed skill is the `env` block in
`~/.claude/settings.json`:

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

`gemini-skill-install` and `setup/install.py` both write these keys for you
interactively. If you edit the file manually:

```bash
$EDITOR ~/.claude/settings.json
```

Then fully restart Claude Code or VS Code. A window reload is not enough.

### Local development from a clone

If you're running `python3 scripts/gemini_run.py` directly from a checkout, you
can also use a repo-root `.env`:

```bash
cp .env.example .env
$EDITOR .env
```

The auth resolver reads that file only for repo-local development.

### Resolution order

1. `GEMINI_API_KEY` already present in the process environment
2. Repo-root `.env` file when running from a clone
3. Error if neither exists

`GOOGLE_API_KEY` is not used by this skill.

## Verify Installation

Inside Claude Code:

```bash
/gemini help
```

For a direct health report from the installed files:

```bash
python3 ~/.claude/skills/gemini/scripts/health_check.py
```

That prints backend configuration, pinned vs installed SDK version, and install
manifest drift status.

## Check for Updates

The installed update launcher checks GitHub Releases and compares the latest tag
to the installed `VERSION`:

```bash
python3 ~/.claude/skills/gemini/setup/update.py
```

Or from a clone:

```bash
python3 setup/update.py
```

Current behavior:

- prints the installed version
- prints the latest GitHub release version
- tells you whether a newer release is available

It **does not yet download or apply the update automatically**.

## Apply a New Release

To install a newer release, rerun the installer from your preferred source:

### If you install from GitHub directly

```bash
uvx --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

### If you install from PyPI

```bash
uvx gemini-skill-install
```

If you installed the bootstrap tool with `pipx`, upgrade it first and then rerun
the command:

```bash
pipx upgrade gemini-skill-install
gemini-skill-install
```

### If you install from a clone or release tarball

```bash
python3 setup/install.py
```

Overwrite installs preserve the existing `.venv` directory and only re-run the
pinned SDK install when needed.

## Troubleshooting

### Incompatible Python or free-threaded build

Symptom:

```text
ImportError: ... _PyType_Freeze
```

or:

```text
gemini-skill install needs a stable CPython 3.9+ interpreter
```

The clone/tarball launcher rejects pre-release, free-threaded, and non-CPython
interpreters because `google-genai` dependencies do not ship compatible wheels
for those runtimes. Install a stable CPython such as `python3.13` or
`python3.12` and rerun the installer.

### I edited `settings.json` and Claude Code still says no key

Claude Code reads the `env` block only at IDE launch. Fully quit and reopen the
editor after editing `~/.claude/settings.json`.

### `Unknown skill: gemini` after install

Check these, in order:

1. Fully restart Claude Code / VS Code.
2. Verify `~/.claude/skills/gemini/SKILL.md` exists.
3. Open the `Claude Code` output pane and look for skill-loader errors.
4. Re-run the installer if the skill directory is incomplete.

### Skill venv setup failed

If venv creation or SDK import verification fails, the install still completes
and the raw HTTP backend remains available. To retry the SDK install later,
re-run the installer:

```bash
python3 setup/install.py
```

or:

```bash
uvx --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

### SDK version drift

If `health_check.py` reports that the installed SDK version differs from the
pinned version, re-run the installer to restore the pin.

### Model not found in registry

Model registry changes ship with a new gemini-skill release. Install the latest
release, then verify the available models with:

```bash
/gemini models
```

### Permission denied

If the installed scripts are not executable:

```bash
chmod +x ~/.claude/skills/gemini/scripts/gemini_run.py
chmod +x ~/.claude/skills/gemini/scripts/health_check.py
```

### Network timeout

Possible causes:

- Gemini API is temporarily down ([status.ai.google.dev](https://status.ai.google.dev))
- Your internet connection is slow
- Firewall is blocking requests to `generativelanguage.googleapis.com`

## What Gets Installed

The installer copies only the runtime payload:

```text
~/.claude/skills/gemini/
├── SKILL.md
├── VERSION
├── .checksums.json
├── .venv/
├── scripts/
├── core/
├── adapters/
├── reference/
├── registry/
└── setup/
    ├── requirements.txt
    └── update.py
```

Not installed:

- `docs/`
- `tests/`
- `.git/`
- `.github/`
- `README.md`
- `setup/install.py`

## Uninstall

To remove the installed skill:

```bash
rm -rf ~/.claude/skills/gemini
```

That does not remove your user-global `~/.claude/settings.json`.
