# Installation

**Last Updated:** 2026-04-13

## Prerequisites

- **Python 3.9 or later**
- **A Gemini API key** (free; get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- **Claude Code** running in your Claude Code environment

## Quick Install

### Method 1: Install script (easiest)

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
python3 setup/install.py
```

The script will:
1. Check Python version
2. Copy operational files to `~/.claude/skills/gemini/`
3. Prompt for Gemini API key
4. Create `.env` file with your key (optional)
5. Print setup confirmation

### Method 2: Manual copy

```bash
# Copy the skill directory
mkdir -p ~/.claude/skills/gemini
cp -r gemini-skill/scripts ~/.claude/skills/gemini/
cp -r gemini-skill/core ~/.claude/skills/gemini/
cp -r gemini-skill/adapters ~/.claude/skills/gemini/
cp -r gemini-skill/registry ~/.claude/skills/gemini/
cp gemini-skill/SKILL.md ~/.claude/skills/gemini/

# Create .env file with your API key
echo "GEMINI_API_KEY=your_key_here" > ~/.claude/skills/gemini/.env
chmod 600 ~/.claude/skills/gemini/.env
```

### Method 3: Download as tarball

```bash
# Download (when available)
tar -xzf gemini-skill-latest.tar.gz
cd gemini-skill-latest
python3 setup/install.py
```

## API Key Setup

### Option A: Shell environment variable (recommended)

```bash
export GEMINI_API_KEY="your_key_here"
```

This is the most secure option. The skill reads the environment variable first.

Add to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
export GEMINI_API_KEY="your_key_here"
```

### Option B: `.env` file (convenience)

After installation, edit **the installed copy** at `~/.claude/skills/gemini/.env` (the installer creates it from `.env.example` on first run):

```bash
$EDITOR ~/.claude/skills/gemini/.env
# Set:
# GEMINI_API_KEY=your_key_here
```

The installer automatically sets `chmod 0600` on the file so only your user can read it. If you copied it manually, set it yourself:

```bash
chmod 600 ~/.claude/skills/gemini/.env
```

**Do not edit the repo-root `.env`.** Only the installed copy at `~/.claude/skills/gemini/.env` is read by the skill at runtime. Editing the repo's `.env` has no effect on the installed skill — the repo's `.env` is only used when you run the skill directly from a checkout (e.g., during development or when running the integration test suite).

The skill reads this file if `GEMINI_API_KEY` is not set in your shell environment.

### Priority order (first-match wins)

1. `GEMINI_API_KEY` shell environment variable
2. `GEMINI_API_KEY` from `.env` file (local-development only)
3. Error if neither found

**Note:** The skill **does not honor `GOOGLE_API_KEY`** — `GEMINI_API_KEY` is the one canonical name to avoid confusion about which key is in use. If you have `GOOGLE_API_KEY` set from another tool, set `GEMINI_API_KEY` separately (they may have the same value).

**Important:** Shell environment variables always take precedence over `.env`. This allows you to override the file for testing or multi-account scenarios.

## Verify installation

After installing, verify the skill is accessible:

```bash
/gemini help
```

You should see a list of available commands. If you see an error, check:

1. **File permissions:** Ensure `~/.claude/skills/gemini/` is readable
2. **Python version:** Run `python3 --version` (should be 3.9+)
3. **API key:** Verify the key is set via environment variable

## Update the skill

If a new version is released:

```bash
git pull origin main
python3 setup/update.py
```

The update script syncs operational files while preserving your configuration.

## Troubleshooting

### macOS SSL Certificate Error

If you see:

```
[SSL: CERTIFICATE_VERIFY_FAILED]
```

This is usually due to macOS not having the latest SSL certificates. Fix it:

```bash
/Applications/Python\ 3.x/Install\ Certificates.command
```

Or reinstall Python via Homebrew:

```bash
brew install python@3.9
```

### Python version mismatch

Error:
```
gemini-skill requires Python 3.9+. Found: 3.8
```

Solution:
```bash
# Install Python 3.9 or later
brew install python@3.11  # macOS
# or
apt install python3.11    # Linux
# or
choco install python      # Windows

# Update your PATH or use explicit version
python3.11 setup/install.py
```

### `Unknown skill: gemini` after install

Symptom: `setup/install.py` finished successfully, `~/.claude/skills/gemini/SKILL.md` exists on disk, but typing `/gemini` in Claude Code still returns `Unknown skill: gemini`.

Causes, in order of likelihood:

1. **Claude Code caches skill discovery at IDE launch.** Opening a new Claude Code session inside the same IDE process does **not** re-scan `~/.claude/skills/`. You need to fully quit VSCode (⌘Q on macOS) and relaunch it. "Reload Window" is not enough.

2. **Invalid frontmatter fields in `SKILL.md`.** Claude Code skills (`.claude/skills/<name>/SKILL.md`) and slash commands (`.claude/commands/*.md`) use **different** frontmatter fields. Mixing them causes the skill loader to silently reject the file:
   - ✅ Valid skill fields: `name`, `description`, `disable-model-invocation`, `user-invocable`
   - ❌ Slash-command-only fields that break a SKILL.md: `allowed-tools`, `argument-hint`, `model`

   The minimal recommended `SKILL.md` frontmatter for this skill is:
   ```yaml
   ---
   name: gemini
   description: Gemini API — ...
   disable-model-invocation: true
   ---
   ```

   `user-invocable` defaults to `true`, so leave it unset unless you specifically want to hide the skill from the `/` menu. `disable-model-invocation: true` is set intentionally so Claude doesn't auto-invoke the billable Gemini API on its own — the user must explicitly type `/gemini`.

3. **`SKILL.md` is missing from the install directory.** Verify:
   ```bash
   ls ~/.claude/skills/gemini/SKILL.md
   head -10 ~/.claude/skills/gemini/SKILL.md
   ```
   If missing, re-run `python3 setup/install.py`.

4. **Skill loader errors in the extension output pane.** In VSCode, open `View → Output` and select `Claude Code` from the dropdown. Skill-discovery errors are logged there. Look for lines mentioning `gemini` or `SKILL.md`.

### API key not found

Error:
```
[ERROR] No GEMINI_API_KEY found.
```

Solution:
```bash
export GEMINI_API_KEY="your_key_here"

# Or verify .env file exists and is readable
cat ~/.claude/skills/gemini/.env
ls -la ~/.claude/skills/gemini/.env
```

### Permission denied

Error:
```
Permission denied: ~/.claude/skills/gemini/scripts/gemini_run.py
```

Solution:
```bash
chmod +x ~/.claude/skills/gemini/scripts/gemini_run.py
chmod +x ~/.claude/skills/gemini/setup/install.py
```

### Network timeout

Error:
```
[ERROR] Timeout after 30 seconds
```

Possible causes:
- Gemini API is temporarily down (check [status.ai.google.dev](https://status.ai.google.dev))
- Your internet connection is slow
- Firewall is blocking requests to generativelanguage.googleapis.com

Solutions:
- Wait a few seconds and retry
- Check your internet connection
- Check your firewall settings

### Model not available

Error:
```
[ERROR] Model not found in registry: gemini-3.5-pro
```

Solution:
1. Update the model registry:
   ```bash
   python3 setup/update.py
   ```

2. Check available models:
   ```bash
   /gemini models
   ```

## Installation locations

The skill can be installed in two places:

### Personal installation

```
~/.claude/skills/gemini/
```

Available to all Claude Code sessions on your machine. This is the default install location.

### Project-specific installation

```
./.claude/skills/gemini/
```

In your project root. Available only to Claude Code sessions in that project. Useful for sharing a preconfigured skill with your team.

## What gets installed

The install script copies only operational files (no tests, no docs, no `.git`):

```
~/.claude/skills/gemini/
├── SKILL.md              # Skill definition
├── scripts/
│   ├── gemini_run.py     # CLI entry point
│   └── health_check.py   # Health check utility
├── core/                 # Runtime modules
├── adapters/             # Command implementations
├── registry/             # Model and capability data
├── setup/
│   └── update.py         # Update handler
└── .env                  # API key (created during install)
```

Test files, doc files, and git history are excluded to minimize storage.

## Next steps

1. **Set your API key** (environment variable or `.env`)
2. **Verify installation:** `/gemini help`
3. **Try a command:** `/gemini text "hello"`
4. **Read the docs:**
   - Quick start: `README.md`
   - All commands: `reference/index.md`
   - Capabilities: `docs/capabilities.md`
   - Usage guide: `docs/usage.md`

## Uninstall

To remove the skill:

```bash
rm -rf ~/.claude/skills/gemini/
# Or for project-specific:
rm -rf ./.claude/skills/gemini/
```

This does not affect your API key or any created resources (files, caches, sessions remain in your Gemini account).
