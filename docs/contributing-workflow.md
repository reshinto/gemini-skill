# Contributing — PR Workflow & Release

[← Back to Contributing](contributing.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

PR workflow, commit style, pre-push hook, release tagging, and code-style enforcement.

## Development Environment

For contributors working from a clone:

```bash
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r setup/requirements-dev.txt
```

This dev venv is separate from the skill runtime venv at `~/.claude/skills/gemini/.venv`.

---

## How to Bump the google-genai Pin

1. Edit `setup/requirements.txt`: `google-genai==X.YZ.W`
2. Run `python3 setup/install.py` to test venv creation
3. Run live integration suite under both backends (see docs/testing.md dual-backend matrix)
4. Run the bootstrap installer coverage slice and packaging build:
   ```bash
   .venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" \
     tests/setup/test_install.py \
     tests/gemini_skill_install/test_cli.py
   python -m build
   ```
5. Verify health check reports no drift
6. Open PR with clear justification for the version bump

## If You Change Installer Payload or Packaging

Update these together:

1. `core/cli/installer/payload.py`
2. `setup.py`
3. `.github/workflows/release.yml`
4. `README.md` and `docs/install.md`

Minimum verification:

```bash
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" \
  tests/core/cli/test_install_main.py \
  tests/setup/test_install.py \
  tests/gemini_skill_install/test_cli.py
python -m build
```

## Cutting a Release

1. Bump `VERSION` on `main`
2. Ensure the GitHub `pypi` environment and PyPI Trusted Publisher are configured
3. Run:
   ```bash
   bash scripts/tag_release.sh
   ```
4. Watch `.github/workflows/release.yml`
5. Verify the GitHub Release and PyPI publication

---

## Deprecation Policy

When deprecating a command:

1. **Announce** in CHANGELOG
2. **Mark deprecated** in code:
   ```python
   """Deprecated command (will be removed in v2.0).
   
   Use 'new_command' instead.
   """
   ```
3. **Keep working** for 2+ releases
4. **Remove** in next major version

Don't break existing workflows without notice.

---

## PR Checklist

Before submitting a pull request:

- [ ] Tests pass: `pytest tests/ -v --cov`
- [ ] Coverage 100%: `coverage report --fail-under=100`
- [ ] Code style: `black core adapters scripts`
- [ ] Lint: `ruff check core adapters scripts`
- [ ] All files documented
- [ ] Reference file created (if new command)
- [ ] SKILL.md updated (if new command)
- [ ] No new external dependencies
- [ ] No hardcoded values (use config)

---

## Code Style Enforcement

### Formatting (black)

```bash
black core adapters scripts
```

### Linting (ruff)

```bash
ruff check core adapters scripts
```

### Type checking (mypy --strict)

```bash
mypy --strict core adapters
```

All three must be clean before opening a PR.

### Pre-push hook

The repo ships a pre-push hook that runs black, ruff, and mypy automatically. It is installed when you run:

```bash
pip install -r setup/requirements-dev.txt
```

If the hook blocks your push, fix the reported issues and push again. Do not bypass the hook with `--no-verify`.

---

## See also

- [contributing.md](contributing.md) — overview and principles
- [contributing-adapters.md](contributing-adapters.md) — how to add a new command/adapter
- [python-guide.md](python-guide.md) — Python version and annotations policy
- [testing.md](testing.md) — test strategy and commands
