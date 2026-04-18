# Testing

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Testing is split into three focus areas. Most contributors start with unit tests.

## Areas

- [testing-unit.md](testing-unit.md) — unit tests, setup, fixtures, coverage gate, TDD workflow
- [testing-integration.md](testing-integration.md) — live API matrix, `GEMINI_LIVE_TESTS`, backend parity, skip rules
- [testing-smoke.md](testing-smoke.md) — clean-install smoke, packaged install, upgrade path

## Quick commands

```bash
# all unit tests + coverage gate
bash setup/run_tests.sh

# one module
source .venv/bin/activate
python3 -m pytest tests/core/transport -v

# live API matrix (requires GEMINI_API_KEY)
GEMINI_LIVE_TESTS=1 python3 -m pytest tests/integration -v

# parity
python3 -m pytest tests/test_documentation_parity.py -v
```

## Gates enforced on every PR

- 100% line + branch coverage across `core/`, `adapters/`, `scripts/`, `setup/`, `gemini_skill_install/`
- `mypy --strict` clean on the modules under test
- `pytest tests/test_documentation_parity.py` green
- `bash scripts/render_diagrams.sh` produces zero diffs (stable SVGs)

## See also

- [contributing.md](contributing.md) — PR workflow
- [python-guide.md](python-guide.md) — Python version and annotations policy
- [architecture.md](architecture.md) — module map (what's being tested)
