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
# Or
export GOOGLE_API_KEY="your_key_here"
```

This is the most secure option. The skill reads the environment variable first.

Add to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
export GEMINI_API_KEY="your_key_here"
```

### Option B: `.env` file (convenience)

After installation, edit `~/.claude/skills/gemini/.env`:

```bash
GEMINI_API_KEY=your_key_here
```

The skill reads this file if the environment variable is not set. Make sure permissions are restrictive:

```bash
chmod 600 ~/.claude/skills/gemini/.env
```

### Priority order (first-match wins)

1. `GOOGLE_API_KEY` environment variable
2. `GEMINI_API_KEY` environment variable
3. `GEMINI_API_KEY` from `.env` file
4. Error if none found

**Important:** Environment variables always take precedence over `.env`. This allows you to override the file for testing or multi-account scenarios.

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

### API key not found

Error:
```
[ERROR] API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.
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
