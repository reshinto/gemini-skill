# Update and Sync Mechanism

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-13

How the install, update, and sync process works. For end-users, see [install.md](install.md).

## Installation Flow

### Phase 1: Repository Clone

User clones the repo:

```bash
git clone https://github.com/reshinto/gemini-skill.git
cd gemini-skill
```

The repo contains:
- Source code (core/, adapters/, scripts/)
- Tests (tests/) — not installed
- Docs (docs/, reference/) — not installed
- Build files (.git/, .github/, etc.) — not installed

### Phase 2: Setup Script

User runs the install script:

```bash
python3 setup/install.py
```

The script (launcher + installer in `core.cli.install_main`):

1. **Check Python version** (3.9+)
2. **Resolve install location** (default: `~/.claude/skills/gemini/`)
3. **Copy operational files** (source, no tests, no docs)
4. **Create config directory** (`~/.config/gemini-skill/`)
5. **Prompt for API key** (offer to save in `.env`)
6. **Verify installation** (test import and help)

### Phase 3: Installed Structure

```
~/.claude/skills/gemini/                # Installation root
├── SKILL.md                            # Skill metadata (Claude reads)
├── scripts/
│   ├── gemini_run.py                   # Main entry point
│   └── health_check.py                 # Health/diagnostics
├── core/
│   ├── cli/
│   ├── auth/
│   ├── infra/
│   ├── routing/
│   ├── state/
│   └── adapter/
├── adapters/
│   ├── generation/
│   ├── data/
│   ├── tools/
│   ├── media/
│   └── experimental/
├── registry/
│   ├── models.json                     # Available models
│   └── capabilities.json               # Feature flags
├── setup/
│   └── update.py                       # Update handler
└── .env                                # API key (optional, user-created)

~/.config/gemini-skill/                 # Config & state
├── cost_today.json                     # Cost tracking (auto-created)
├── files.json                          # Files API state
├── stores.json                         # File Search stores
└── sessions/
    ├── chat.json                       # Conversation sessions (auto-created)
    └── ...
```

**Not installed:**
- tests/ (574 tests)
- docs/ (this directory)
- reference/ (per-command docs)
- .git/ (version history)
- .github/ (CI/CD workflows)

This keeps the installed skill small (~5–10 MB) and focused on runtime.

---

## Update Flow

### Checking for Updates

The install script can be re-run to update:

```bash
cd gemini-skill
python3 setup/update.py
```

(Or the user can re-run `python3 setup/install.py` — it's idempotent.)

### Update Process

The `update.py` script (in `core.cli.update_main`):

1. **Verify installation exists** (fail if not installed)
2. **Preserve pinned google-genai version** — Does NOT upgrade the SDK silently; respects `setup/requirements.txt` pinning
3. **Preserve `.venv`** — Does not delete or re-create the runtime venv; allows existing virtual environment to persist
4. **Fetch latest model registry** (optional, if API accessible)
5. **Sync operational files** from repo to `~/.claude/skills/gemini/`
6. **Preserve user config** (`~/.claude/settings.json` env block, session history, cost tracking)
7. **Verify updated installation** (test help command)

### Bumping the SDK Version

To upgrade the pinned `google-genai` version:

1. Edit `setup/requirements.txt` and change the version pin (e.g., `google-genai==1.33.0` → `google-genai==1.34.0`)
2. Run `python3 setup/install.py` (updates the runtime venv)
3. Run the full integration test suite under **both** backends:
   ```bash
   GEMINI_IS_SDK_PRIORITY=true pytest tests/integration/ -v
   GEMINI_IS_RAWHTTP_PRIORITY=true pytest tests/integration/ -v
   ```
4. If all tests pass, open a pull request with the version bump and test results
5. Users update via `cd gemini-skill && git pull && python3 setup/update.py`

### Atomic Update

Updates are **atomic** (no partial updates on failure):

1. Copy files to temporary directory
2. Validate syntax and imports
3. If valid: atomic swap to installation directory
4. If invalid: preserve old installation, report error

**Rollback:**

If an update breaks things, the previous installation is preserved. User can downgrade by reverting to an older git commit or reinstalling from backup.

---

## Sync Mechanism

### What Gets Synced

Only **operational files** are synced:

```
scripts/         → ~/.claude/skills/gemini/scripts/
core/            → ~/.claude/skills/gemini/core/
adapters/        → ~/.claude/skills/gemini/adapters/
registry/        → ~/.claude/skills/gemini/registry/
SKILL.md         → ~/.claude/skills/gemini/SKILL.md
setup/update.py  → ~/.claude/skills/gemini/setup/update.py
```

**NOT synced:**
- tests/ — user doesn't need tests
- docs/ — reference docs not needed at runtime
- .git/ — version control not needed in installation
- .github/ — CI/CD not needed in installation

### What's Preserved

User files and state are **never overwritten**:

```
~/.claude/skills/gemini/.env              # User's API key (preserved)
~/.config/gemini-skill/sessions/          # User's sessions (preserved)
~/.config/gemini-skill/cost_today.json    # Cost tracking (preserved)
~/.config/gemini-skill/files.json         # File state (preserved)
~/.config/gemini-skill/stores.json        # Store state (preserved)
```

### Sync Algorithm

```python
def sync_files(repo_dir: Path, install_dir: Path):
    """Sync operational files from repo to installation."""
    
    # Define operational directories
    operational_dirs = ["scripts", "core", "adapters", "registry"]
    operational_files = ["SKILL.md"]
    
    for dir_name in operational_dirs:
        src = repo_dir / dir_name
        dst = install_dir / dir_name
        
        # Remove old directory
        if dst.exists():
            shutil.rmtree(dst)
        
        # Copy new directory
        shutil.copytree(src, dst)
    
    # Copy individual files
    for file_name in operational_files:
        src = repo_dir / file_name
        dst = install_dir / file_name
        shutil.copy2(src, dst)
    
    # Verify installation
    verify_installation(install_dir)
```

---

## Model Registry Updates

The model registry (`registry/models.json`) contains:

1. **Available models** — which model IDs are current
2. **Model capabilities** — which features each model supports
3. **Default models** — specialty task defaults (embed, image_gen, etc.)
4. **Deprecation status** — which models are being phased out

### Updating the Registry

When Google releases new models or deprecates old ones:

```bash
# Fetch latest from Gemini API (if available)
python3 setup/update.py --fetch-models

# Or manually update registry/models.json
```

Example registry entry:

```json
{
  "models": [
    {
      "id": "gemini-2.5-pro",
      "display_name": "Gemini 2.5 Pro",
      "input_token_limit": 1000000,
      "output_token_limit": 8192,
      "capabilities": [
        "text",
        "multimodal",
        "function_calling",
        "code_execution"
      ],
      "preview": false,
      "deprecated": false,
      "default_for": [],
      "pricing": {
        "input_tokens_per_million": 1.50,
        "output_tokens_per_million": 6.00
      }
    }
  ],
  "capabilities": {
    "text": {
      "description": "Text generation",
      "default_model": "gemini-2.5-flash",
      "v1beta": true
    },
    "embed": {
      "description": "Embeddings",
      "default_model": "gemini-embedding-2-preview",
      "v1beta": true
    }
  }
}
```

### Backwards Compatibility

Old models are marked `"deprecated": true` but remain in the registry:

```json
{
  "id": "gemini-1.5-flash",
  "deprecated": true,
  "deprecation_message": "Use gemini-2.5-flash instead"
}
```

Users can still use them with `--model gemini-1.5-flash`, but they're warned in logs/docs.

---

## Integrity Checking

### File Checksums (SHA-256)

The install script verifies file integrity using SHA-256 checksums stored in `.checksums.json`:

```python
# Stored in .checksums.json at repo root
{
  "scripts/gemini_run.py": "abc123...",
  "core/cli/dispatch.py": "def456...",
  ...
}

# Verify during install
with open(".checksums.json") as f:
    expected = json.load(f)

for file, expected_hash in expected.items():
    actual_hash = hashlib.sha256(Path(file).read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise IntegrityError(f"Checksum mismatch: {file}")
```

**Behavior:** If a user has modified files locally, the install refuses to proceed and reports which files have been altered. This prevents silent corruption and ensures the installation matches the released version.

**Updating checksums:** Before each release, run `python3 setup/generate_checksums.py` to regenerate `.checksums.json` based on the current operational files.

### GPG Signatures (Future)

Future releases could sign the repo with GPG:

```bash
git tag -s v1.0.0 -m "Release 1.0.0"
git verify-tag v1.0.0
```

Users can verify before install:

```bash
git verify-tag <tag>
```

**Current status:** Not implemented.

---

## Rollback Procedure

If an update breaks things:

### Option 1: Reinstall from Git

```bash
cd gemini-skill
git checkout <previous-version>
python3 setup/install.py
```

### Option 2: Preserve Old Installation

Before updating, backup:

```bash
cp -r ~/.claude/skills/gemini ~/.claude/skills/gemini.backup
```

If update fails, restore:

```bash
rm -rf ~/.claude/skills/gemini
mv ~/.claude/skills/gemini.backup ~/.claude/skills/gemini
```

### Option 3: Manual File Recovery

The old installation directory can be restored if updates use atomic swaps:

```python
# If update fails mid-swap, old dir still exists
os.replace(new_dir, old_dir)  # Atomic swap
```

---

## Installation Options

### Personal Installation (Default)

```
~/.claude/skills/gemini/
```

Installed by `python3 setup/install.py` (no args).

Accessible to all Claude Code sessions on the user's machine.

### Project-Specific Installation

```
./.claude/skills/gemini/
```

Installed with:

```bash
python3 setup/install.py --project-local
```

Accessible only to Claude Code sessions in that project directory. Useful for sharing a preconfigured skill with your team.

### Custom Installation Path

```bash
python3 setup/install.py --install-dir /custom/path/gemini
```

Install to a custom location. Update also needs the custom path.

---

## Uninstall Procedure

To remove the skill:

```bash
rm -rf ~/.claude/skills/gemini
rm -rf ~/.config/gemini-skill
```

This removes the installation and all state (sessions, cost tracking, file tracking). User's API key (if in `.env`) is deleted; shell env var persists.

To keep state but remove skill:

```bash
rm -rf ~/.claude/skills/gemini
# ~/.config/gemini-skill persists (can be restored if skill is reinstalled)
```

---

## Release Process

When a new version is released:

1. **Update VERSION file:**
   ```
   1.0.0
   ```

2. **Create git tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Create GitHub release** (with release notes)

4. **Users update via:**
   ```bash
   cd gemini-skill
   git pull origin main
   python3 setup/update.py
   ```

---

## Troubleshooting Installation

### Installation fails with "Python 3.9+ required"

```bash
python3.9 setup/install.py
# or
brew install python@3.9
```

### Installation fails with "Permission denied"

```bash
mkdir -p ~/.claude/skills/
chmod 755 ~/.claude/skills/
python3 setup/install.py
```

### Installation fails with "Module not found"

Ensure you're in the repo root:

```bash
cd gemini-skill
python3 setup/install.py
```

### Update fails with "Installation not found"

Reinstall from repo:

```bash
python3 setup/install.py
```

### Files not synced properly

Manual sync:

```bash
cp -r scripts core adapters registry SKILL.md ~/.claude/skills/gemini/
```

---

## Development Installation

For development (working on the skill itself):

```bash
cd gemini-skill
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run without installing (for testing)
export PYTHONPATH=$(pwd):$PYTHONPATH
python3 scripts/gemini_run.py text "hello"

# Or use symbolic link for live-reload development
ln -s $(pwd) ~/.claude/skills/gemini
```

This allows testing changes without reinstalling.

---

## Next Steps

- **Installation:** [Install guide](install.md)
- **Architecture:** [System design](architecture.md)
- **Contributing:** [Contributing guide](contributing.md)
