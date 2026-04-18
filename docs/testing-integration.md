# Testing — Integration Tests

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Live integration tests hit the real Gemini API. They are skipped by default and require explicit opt-in.

## Running live integration tests

[tests/integration/](../tests/integration/) holds one smoke test per adapter (19 total) that hits the **real Gemini API**. They are skipped by default and only run when you explicitly opt in.

### Prerequisites

1. A Gemini API key — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Both of these environment variables set:
   ```bash
   export GEMINI_LIVE_TESTS=1
   export GEMINI_API_KEY=your_real_key_here
   ```
   If either is missing, every live test auto-skips with a clear reason.

### Running them

All live tests (the whole integration suite):
```bash
GEMINI_LIVE_TESTS=1 GEMINI_API_KEY=... pytest tests/integration -m live
```

A single adapter (recommended for a first smoke check — cheapest and fastest):
```bash
GEMINI_LIVE_TESTS=1 GEMINI_API_KEY=... pytest tests/integration/test_text_live.py -v
```

Exclude them from a normal unit-test run (they're already gated, this is just explicit):
```bash
pytest -m "not live"
```

---

## Dual-backend matrix (Phase 8)

Every live test is backend-agnostic by design — the same assertions must pass whether the coordinator routes via the SDK backend or raw HTTP. Run the suite once per backend by flipping the two priority flags:

```bash
# SDK primary (default)
GEMINI_LIVE_TESTS=1 GEMINI_API_KEY=... \
  GEMINI_IS_SDK_PRIORITY=true GEMINI_IS_RAWHTTP_PRIORITY=false \
  pytest tests/integration -m live

# Raw HTTP primary
GEMINI_LIVE_TESTS=1 GEMINI_API_KEY=... \
  GEMINI_IS_SDK_PRIORITY=false GEMINI_IS_RAWHTTP_PRIORITY=true \
  pytest tests/integration -m live
```

The matrix runs automatically on `workflow_dispatch` in CI via the
`live-integration` job. It's intentionally gated to manual runs so
PRs from forks can never exfiltrate the `GEMINI_API_KEY` secret.

Both runs share the `tests/integration/conftest.py` helpers:
- `runner_python` / `runner_script` / `repo_root` fixtures for consistent subprocess paths.
- `backend_env` fixture builds an env dict the CI cell's priority flags propagate into.
- `run_gemini(args, env=..., timeout=...)` centralized subprocess helper.
- `current_primary_backend(env)` resolves the configured primary per the Config rules.

Running both doubles the cost — for local iteration just pick one backend.
To skip a specific expensive test (like image generation) inside a matrix
run, use pytest's `-k 'not nano_banana'` filter.

---

## Writing tests with type safety

Always use `Mock(spec=ConcreteClass)` instead of bare `MagicMock()`:

```python
# Good: spec enforces the mock matches the real interface
mock_config = Mock(spec=Config)
mock_config.api_key = "test_key"

# Avoid: bare MagicMock has no interface guarantees
mock_config = MagicMock()
```

---

## What each test does

Each file is **self-contained** — no shared conftest, no cross-file state — and runs exactly **one** subprocess call to `scripts/gemini_run.py` with a minimal prompt.

**Real API calls (11 adapters, cheap):**

| Test | What it does |
|---|---|
| `test_text_live.py` | Single-token text generation |
| `test_multimodal_live.py` | Sends a 1x1 PNG with a short prompt |
| `test_structured_live.py` | Tiny JSON schema response |
| `test_streaming_live.py` | Streamed single-token response |
| `test_embed_live.py` | Embed `"hello world"` |
| `test_token_count_live.py` | Count tokens (free) |
| `test_function_calling_live.py` | Declares one no-arg tool |
| `test_code_exec_live.py` | `compute 2+2` |
| `test_search_live.py` | Grounded query with dispatcher-managed privacy opt-in |
| `test_maps_live.py` | Grounded query with dispatcher-managed privacy opt-in |
| `test_computer_use_live.py` | Preview model with dispatcher-managed privacy opt-in |

**Dry-run only (8 mutating adapters):**

`test_files_live.py`, `test_cache_live.py`, `test_batch_live.py`, `test_file_search_live.py`, `test_image_gen_live.py`, `test_video_gen_live.py`, `test_music_gen_live.py`, `test_deep_research_live.py`

These smoke tests target mutating commands or mutating subcommands, so they are blocked by the dispatcher unless `--execute` is passed. The tests **do not** pass `--execute` — they assert the `[DRY RUN]` output instead. This verifies the CLI → dispatch → registry → policy path without burning quota on image/video/music generation, persistent cache/store creation, downloads to the local filesystem, or long-running agentic flows. To actually exercise these adapters against the live API, see the rationale in each file's docstring and run them manually with `--execute`.

---

## Estimated cost per full run

Running all 19 live tests once costs roughly a **few cents** in total — the real-call tests use the cheapest routed model with minimal prompts, and the dry-run tests make no API calls at all. Safe to run before a release; **not** safe to run in a tight loop.

---

## Privacy note

The search, maps, computer-use, and deep-research tests send prompts through privacy-sensitive capabilities (web search results, maps data, computer interaction, long-term research storage). Dispatch auto-applies the internal privacy opt-in flag for those commands. Don't run them on a machine where that consent is not appropriate.

---

## See also

- [testing.md](testing.md) — overview and quick commands
- [testing-unit.md](testing-unit.md) — unit tests, setup, fixtures, coverage gate, TDD workflow
- [testing-smoke.md](testing-smoke.md) — clean-install smoke, packaged install, upgrade path
- [contributing.md](contributing.md) — PR workflow
