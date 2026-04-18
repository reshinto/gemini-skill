# Testing — Smoke Tests

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Smoke tests verify the packaged installer and the end-to-end install path work correctly outside the development environment.

## Bootstrap Installer Packaging Checks

The project ships a packaged bootstrap installer (`gemini-skill-install`) that
must stay healthy alongside the clone-based installer.

Minimum packaging checks:

```bash
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" \
  tests/setup/test_install.py \
  tests/gemini_skill_install/test_cli.py
python -m build
```

For release readiness, also run:

```bash
python -m pip install twine
python -m twine check dist/*
```

---

## Running Tests in Production

Before deploying:

```bash
# Run all tests with coverage
bash setup/run_tests.sh

# Check coverage
coverage report --fail-under=100

# Lint and format check
ruff check core adapters scripts
black --check core adapters scripts

# Type check (if applicable)
mypy core adapters --strict
```

---

## See also

- [testing.md](testing.md) — overview and quick commands
- [testing-unit.md](testing-unit.md) — unit tests, setup, fixtures, coverage gate, TDD workflow
- [testing-integration.md](testing-integration.md) — live API matrix, `GEMINI_LIVE_TESTS`, backend parity, skip rules
- [contributing.md](contributing.md) — PR workflow
