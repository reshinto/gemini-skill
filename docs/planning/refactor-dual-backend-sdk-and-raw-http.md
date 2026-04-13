# Dual-backend transport refactor (SDK + raw HTTP with fallback)

## Implementation checklist

This is the **canonical task tracker** for the refactor. Tick boxes as work lands. The checklist mirrors the phase plan but is flat for fast scanning. Every item links to the phase / section that owns it. Do NOT delete checked items — preserve history so the PR description can paste a snapshot.

### Phase 0 — Pre-implementation (manual git + key migration + GOOGLE_API_KEY removal) — model: `haiku`, effort: `low`

- [ ] **Switch model to `haiku`, effort to `low`** before starting (this phase is shell-only; haiku is the cheapest correct choice)

- [ ] `git checkout main && git pull --ff-only origin main`
- [ ] `git checkout -b refactor/dual-backend-sdk-and-raw-http`
- [ ] **Create dev venv at repo root** (`python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip`)
- [ ] Verify `.venv/` is gitignored
- [ ] **Update `setup/requirements.txt`** with `google-genai==1.33.0` (create if missing)
- [ ] **Update `setup/requirements-dev.txt`** with `pytest>=8.0`, `pytest-cov>=4.1`, `pytest-asyncio==0.23.7`, `deepdiff==7.0.1`, `mypy>=1.8`, `ruff>=0.5` (preserving existing dev deps)
- [ ] Commit both requirements files: `chore(deps): pin runtime + dev dependencies for dual-backend refactor`
- [ ] Install runtime dep: `pip install google-genai==1.33.0`
- [ ] Install dev deps from file: `pip install -r setup/requirements-dev.txt`
- [ ] Verify imports clean: `python -c "import google.genai, pytest, pytest_asyncio, deepdiff, mypy, ruff, black"`
- [ ] **Install pre-push hook** that runs `black` and auto-commits any formatting changes (see Pre-implementation step 6 part j below)
- [ ] Run baseline `pytest --tb=short -q` and record pass/fail count
- [ ] Copy this plan to `docs/planning/refactor-dual-backend-sdk-and-raw-http.md` and commit
- [ ] **Manual `.env` → `~/.claude/settings.json` migration** (steps a–e in Pre-implementation):
  - [ ] Inventory existing keys in `~/.claude/skills/gemini/.env` and repo-root `.env`
  - [ ] Read existing `~/.claude/settings.json` and validate JSON
  - [ ] Run duplicate-key check Python script
  - [ ] Resolve any conflicts manually (no overwrite)
  - [ ] Add `GEMINI_API_KEY`, `GEMINI_IS_SDK_PRIORITY`, `GEMINI_IS_RAWHTTP_PRIORITY`, `GEMINI_LIVE_TESTS` to `env` block
  - [ ] Verify repo-root `.env` is gitignored
- [ ] **MOVED FROM PHASE 4 — Remove `GOOGLE_API_KEY` from `core/auth/auth.py` immediately** so Phase 1-3 tests run against the final auth contract. Otherwise the old `GOOGLE_API_KEY` precedence silently masks bugs in every earlier phase.
  - [ ] Strip the `GOOGLE_API_KEY` branch from `resolve_key()` and `_load_env_file()`
  - [ ] Update `tests/core/auth/test_auth.py` to assert `GOOGLE_API_KEY` alone yields `AuthError`
  - [ ] Run `! grep -rn "GOOGLE_API_KEY" core/ adapters/ scripts/ tests/ docs/ reference/ README.md SKILL.md .env.example` — must be empty
  - [ ] Commit as `refactor(auth): remove GOOGLE_API_KEY in favor of GEMINI_API_KEY`

### Phase 1 — Foundation (TDD) — model: `sonnet`, effort: `medium` — also lands the config flags Phase 3 will need

- [ ] **Config flags moved from Phase 4 into here**: extend `core/infra/config.py` with `is_sdk_priority`/`is_rawhttp_priority` fields, validation (both-false → ConfigError), `_parse_bool_env` helper, computed `primary_backend`/`fallback_backend` properties. Tests in `tests/core/infra/test_config.py` extensions. This must land in Phase 1 because Phase 3's coordinator reads these fields.
- [ ] `tests/transport/test_policy.py` written (red)
- [ ] `core/transport/policy.py` implemented (green); 100% cov; mypy strict clean
- [ ] `tests/transport/test_base.py` + `core/transport/base.py` (TypedDicts + Protocols + `BackendUnavailableError` — moved from `core/infra/errors.py` per layering fix)
- [ ] `tests/transport/test_normalize.py` + fixtures + `core/transport/normalize.py` — uses **explicit snake→camel mapping table** (not just `model_dump(by_alias=True)`) plus runtime envelope validator. See "Normalize layer hardening" addendum below.
- [ ] **`git mv` (not delete+create)** `core/infra/client.py` → `core/transport/raw_http/client.py` so blame history is preserved on the most-debugged file in the repo
- [ ] Strip `_SKILL_ROOT` and `env_dir=_SKILL_ROOT` from the moved file (auth now reads from process env)
- [ ] Update `tests/core/infra/test_client.py` import path; rewrite `_SKILL_ROOT` assertions to assert no-arg `resolve_key()`
- [ ] `tests/transport/test_raw_http_transport.py` + `core/transport/raw_http/transport.py`
- [ ] `ecc:python-reviewer` review pass + `ecc:security-reviewer` review pass
- [ ] Phase 1 exit gate: `pytest tests/transport/ tests/core/infra/test_client.py tests/core/infra/test_config.py --cov=core/transport --cov=core/infra/config --cov-branch --cov-fail-under=100`
- [ ] Commit Phase 1

### Phase 2 — SDK transport + client factory (TDD) — model: `sonnet`, effort: `high`

- [ ] **Switch model to `sonnet`, effort to `high`** before writing any code; verify via `/status`

- [ ] `tests/transport/sdk/test_client_factory.py` + `core/transport/sdk/client_factory.py`
- [ ] `tests/transport/sdk/test_transport.py` + `core/transport/sdk/transport.py` (every endpoint mapped)
- [ ] `tests/transport/test_parity.py` (byte-identical responses across backends)
- [ ] `ecc:docs-lookup` consulted for every uncertain SDK surface
- [ ] `ecc:python-reviewer` + `ecc:security-reviewer` + `ecc:architect` review passes
- [ ] Phase 2 exit gate: `pytest tests/transport/sdk/ --cov-fail-under=100`; parity test green
- [ ] Commit Phase 2

### Phase 3 — Coordinator + facade + auto-fallback (TDD, adversarial review) — model: `sonnet`, effort: `high`

- [ ] **Switch model to `sonnet`, effort to `high`** before writing any code; verify via `/status`

- [ ] `ecc:architect` design pass before code
- [ ] `tests/transport/test_coordinator.py` + `core/transport/coordinator.py` (full matrix)
- [ ] `tests/transport/test_facade.py` + `core/transport/__init__.py`
- [ ] `tests/transport/test_auto_fallback.py` (missing-surface cache)
- [ ] `ecc:gan-generator` + `ecc:gan-evaluator` adversarial loop
- [ ] `ecc:python-reviewer` + `ecc:performance-optimizer` + `ecc:security-reviewer` reviews
- [ ] Existing `pytest tests/adapters/` still 100% green via the `core/infra/client.py` shim
- [ ] Commit Phase 3

### Phase 4 — Errors + checksums (config moved to Phase 1) — model: `haiku`, effort: `medium`

- [ ] **Switch model to `haiku`, effort to `medium`** before writing any code; verify via `/status`

- [ ] `tests/core/infra/test_config.py` extensions + `core/infra/config.py` (priority flags)
- [ ] `tests/core/infra/test_errors.py` extensions + `core/infra/errors.py` (`BackendUnavailableError`, `APIError` ctx fields)
- [ ] `tests/core/infra/test_checksums.py` + `core/infra/checksums.py`
- [ ] **Remove `GOOGLE_API_KEY` branch** from `core/auth/auth.py` + update `tests/core/auth/test_auth.py`
- [ ] CI grep regression: `! grep -rn "GOOGLE_API_KEY" core/ adapters/ scripts/ tests/ docs/ reference/ README.md SKILL.md .env.example`
- [ ] Rewrite `.env.example` to list every key in `_DEFAULT_ENV_KEYS` in the same order
- [ ] `tests/test_env_example_in_sync.py` enforces no drift between `.env.example` and `_DEFAULT_ENV_KEYS`
- [ ] **Remove `GEMINI_LIVE_IMAGE_GEN` gate** from `tests/integration/test_image_gen_nano_banana_2_live.py` + docs
- [ ] CI grep regression: `! grep -rn "GEMINI_LIVE_IMAGE_GEN\|GOOGLE_API_KEY\|GEMINI_RECORD_MOCKS"` (extended)
- [ ] `ecc:refactor-cleaner` sweep for dead `_SKILL_ROOT`, `primary_backend`, `fallback_enabled`, `vertex`, `gemini_api_mode`
- [ ] `ecc:python-reviewer` + `ecc:security-reviewer` reviews
- [ ] Phase 4 exit gate green
- [ ] Commit Phase 4

### Phase 5 — Install / update / health / venv / settings.json merge — model: `sonnet`, effort: `medium`

- [ ] **Switch model to `sonnet`, effort to `medium`** before writing any code; verify via `/status`

- [ ] `setup/requirements.txt` created with `google-genai==1.33.0` pin
- [ ] `tests/core/cli/test_install_main.py` extensions covering the API key prompt:
  - [ ] `test_prompt_api_key_keeps_existing_when_user_chooses_keep`
  - [ ] `test_prompt_api_key_updates_existing_when_user_chooses_update`
  - [ ] `test_prompt_api_key_handles_absent_key_with_user_supplied_value`
  - [ ] `test_prompt_api_key_handles_absent_key_with_empty_input`
  - [ ] `test_prompt_api_key_strips_whitespace_from_input`
  - [ ] `test_prompt_api_key_uses_getpass_no_echo`
  - [ ] `test_prompt_api_key_warns_on_unusual_prefix_but_saves_anyway`
  - [ ] `test_prompt_api_key_never_prints_value_only_length`
  - [ ] `test_prompt_api_key_skipped_under_yes_flag`
  - [ ] `test_prompt_api_key_skipped_under_non_tty_with_stderr_warning`
  - [ ] `test_prompt_api_key_default_choice_is_keep_when_existing`
  - [ ] `test_prompt_api_key_invalid_choice_reprompts`
- [ ] `tests/core/cli/test_install_main.py` extensions covering the generic merge scenarios:
  - [ ] `test_merge_settings_creates_file_when_missing`
  - [ ] `test_merge_settings_creates_env_block_when_missing`
  - [ ] `test_merge_settings_adds_only_missing_keys_silently`
  - [ ] `test_merge_settings_aborts_on_malformed_json`
  - [ ] `test_merge_settings_prompts_on_duplicate_key_with_empty_string`
  - [ ] `test_merge_settings_prompts_on_duplicate_key_with_real_value`
  - [ ] `test_merge_settings_skip_keeps_existing_value`
  - [ ] `test_merge_settings_replace_overwrites_value`
  - [ ] `test_merge_settings_quit_aborts_install`
  - [ ] `test_merge_settings_default_choice_is_skip`
  - [ ] `test_merge_settings_invalid_input_reprompts`
  - [ ] `test_merge_settings_multiple_conflicts_prompted_independently`
  - [ ] `test_merge_settings_never_prints_secret_values`
  - [ ] `test_merge_settings_preserves_other_top_level_keys`
  - [ ] `test_merge_settings_preserves_unknown_env_keys`
  - [ ] `test_merge_settings_atomic_write_on_failure_keeps_original`
  - [ ] `test_yes_flag_auto_skips_all_conflicts`
  - [ ] `test_non_tty_stdin_auto_skips_with_warning`
  - [ ] `test_migrate_legacy_env_to_settings_happy_path`
  - [ ] `test_migrate_legacy_env_with_conflict_prompts`
  - [ ] `test_migrate_legacy_env_with_user_decline_keeps_legacy_file`
- [ ] `core/cli/install_main.py` venv creation + pip install + settings merge
- [ ] `core/cli/update_main.py` pinned-version preservation
- [ ] `core/cli/health_main.py` reports backend / venv / SDK / pinned-vs-installed / checksums
- [ ] `tests/scripts/test_gemini_run.py` + `scripts/gemini_run.py` venv re-exec
- [ ] `tests/scripts/test_health_check.py` + `scripts/health_check.py` thin launcher
- [ ] `core/infra/client.py` rewritten as 5-line shim
- [ ] SKILL.md interpreter line updated to `${CLAUDE_SKILL_DIR}/.venv/bin/python`
- [ ] `ecc:security-reviewer` MANDATORY review of settings.json merge logic
- [ ] Manual install dry-run on a temp HOME passes
- [ ] Commit Phase 5

### Phase 6 — Async transport + dispatch async path — model: `sonnet`, effort: `high`

- [ ] **Switch model to `sonnet`, effort to `high`** before writing any code; verify via `/status`

- [ ] `tests/transport/sdk/test_async_transport.py` + `core/transport/sdk/async_transport.py`
- [ ] Coordinator `execute_*_async` mirrors + tests
- [ ] `core/cli/dispatch.py` IS_ASYNC adapter detection
- [ ] `ecc:performance-optimizer` async correctness review
- [ ] Commit Phase 6

### Phase 7 — New adapters + adapter extensions — model: `sonnet`, effort: `medium`

- [ ] **Switch model to `sonnet`, effort to `medium`** before writing any code; verify via `/status`

- [ ] `adapters/generation/imagen.py` + tests + `reference/imagen.md`
- [ ] `adapters/generation/live.py` + tests + `reference/live.md`
- [ ] `adapters/media/image_gen.py` extended with `--aspect-ratio` + `--image-size`
- [ ] `adapters/data/files.py` extended with `download` subcommand
- [ ] `adapters/tools/search.py` extended with `--show-grounding`
- [ ] `registry/capabilities.json` updated for new capabilities
- [ ] All adapter unit tests at 100% coverage
- [ ] Commit Phase 7

### Phase 8 — Live integration matrix — model: `haiku`, effort: `low`

- [ ] **Switch model to `haiku`, effort to `low`** before writing any test files; verify via `/status`

- [ ] `tests/integration/conftest.py` backend selection helper + last-backend marker reader
- [ ] `tests/integration/test_imagen_live.py`
- [ ] `tests/integration/test_live_live.py`
- [ ] `.github/workflows/ci.yml` matrix dimension added
- [ ] `GEMINI_LIVE_TESTS=1 GEMINI_IS_SDK_PRIORITY=true GEMINI_IS_RAWHTTP_PRIORITY=false pytest tests/integration/` green
- [ ] `GEMINI_LIVE_TESTS=1 GEMINI_IS_SDK_PRIORITY=false GEMINI_IS_RAWHTTP_PRIORITY=true pytest tests/integration/` green
- [ ] Commit Phase 8

### Phase 9a — Doc sweep (high-traffic) — model: `sonnet`, effort: `medium`

- [ ] **Switch model to `sonnet`, effort to `medium`** before writing any prose; verify via `/status`

- [ ] README.md
- [ ] SKILL.md
- [ ] docs/install.md
- [ ] docs/architecture.md
- [ ] docs/contributing.md
- [ ] docs/testing.md
- [ ] docs/security.md

### Phase 9b — Doc sweep (remaining + reference) — model: `sonnet`, effort: `medium`

- [ ] **Switch model to `sonnet`, effort to `medium`** before writing any prose; verify via `/status`

- [ ] docs/how-it-works.md, docs/usage.md, docs/capabilities.md, docs/commands.md, docs/model-routing.md, docs/python-guide.md, docs/update-sync.md
- [ ] All 19 reference/*.md files (one-by-one, even if unchanged)
- [ ] New: docs/env-vars-reference.md
- [ ] .env.example rewritten with dev-only header
- [ ] CI grep: no stale "stdlib only" / "urllib" / "GOOGLE_API_KEY" / "vertex" / "GEMINI_LIVE_IMAGE_GEN" / "GEMINI_PRIMARY_BACKEND" references

### Phase 9c — Mermaid diagrams → SVG — model: `sonnet`, effort: `medium`

- [ ] **Switch model to `sonnet`, effort to `medium`** before writing any diagrams; verify via `/status`

- [ ] `scripts/render_diagrams.sh` helper script
- [ ] `setup/diagram-tools.json` (or pinned mmdc invocation)
- [ ] All 12 `.mmd` source files written under `docs/diagrams/`
- [ ] All 12 `.png` files rendered and committed
- [ ] Each PNG embedded in the relevant doc(s) with source-link footer
- [ ] CI grep: no raw `mermaid` blocks outside `docs/diagrams/`
- [ ] CI gate: `git diff --exit-code docs/diagrams/*.png` after re-render

### Phase 10 — Final QA + PR — model: `opus-1m`, effort: `high`

- [ ] **Switch model to `opus-4-6[1m]`, effort to `high`** before starting the cross-cutting review pass; verify via `/status`

- [ ] Full `pytest --cov-fail-under=100` matrix green
- [ ] `mypy --strict` green on new surface
- [ ] Both backend live matrices green
- [ ] Manual install on a clean HOME succeeds
- [ ] Manual `/gemini text "hello"` from fresh VSCode session works
- [ ] `ecc:gan-evaluator` cross-cutting senior pass
- [ ] `ecc:security-reviewer` final pass on auth/transport/install
- [ ] `ecc:refactor-cleaner` final dead-code sweep
- [ ] `ecc:e2e-runner` runs both backend matrices
- [ ] `ecc:python-reviewer` final type/style pass
- [ ] PR opened with description linking to `docs/planning/refactor-dual-backend-sdk-and-raw-http.md`
- [ ] Update `docs/planning/refactor-dual-backend-sdk-and-raw-http.md` footer with merged-PR link after merge

## Per-phase content loading map (token efficiency)

This plan is large (~2600 lines). To keep working context under ~100k tokens during implementation, **never load the whole plan at once**. Instead, load only the slices listed below for whichever phase is active, plus the always-loaded global rules.

### Always loaded (global rules; ~10k tokens total)
- `## Implementation checklist` — the live tracker
- `## Context` — why this refactor exists
- `## Architecture summary` — high-level diagram
- `## Code commenting requirement` — review gate
- `## Strict typing requirement (no Any)` — review gate
- `## TDD workflow & 100% coverage requirement` — review gate

### Per-phase additional sections to load

| Phase | Load these additional sections |
|---|---|
| **0 — Pre-impl** | `## Pre-implementation steps` (full) |
| **1 — Foundation** | `## File-by-file plan` (transport rows only), `## Pseudocode` → `### Package: core/transport/` (only `__init__.py`, `base.py`, `policy.py`, `normalize.py`, `raw_http/*`), `## Execution phases` → Phase 1 |
| **2 — SDK transport** | `## Feature parity audit` (entire), `## Pseudocode` → `### Package: core/transport/` (only `sdk/*`), `## Pseudocode` → `### Package: core/auth/` (stub pointer), Phase 2 from `## Execution phases` |
| **3 — Coordinator** | `## Pseudocode` → `core/transport/coordinator.py` and `core/transport/__init__.py`, `## Architecture summary → Fallback eligibility rules`, `## User decisions` → eligibility rule update + per-capability routing override, Phase 3 |
| **4 — Config + errors + checksums** | `## Pseudocode` → `### Package: core/infra/`, `## Outstanding TODOs converted to features`, `## Auth + env var storage model` → `### Existing GOOGLE_API_KEY references — must be removed` and `### Existing GEMINI_LIVE_IMAGE_GEN references — must be removed`, Phase 4 |
| **5 — Install + venv + settings.json** | `## Auth + env var storage model` → `### Concrete settings.json shape`, `### GEMINI_API_KEY interactive setup`, `### Generic settings.json merge`, `### Install flow updates`, `## Pseudocode` → `### Package: core/cli/`, `### Package: scripts/`, Phase 5, the `setup/requirements.txt` content snippet |
| **6 — Async** | `## Pseudocode` → `core/transport/sdk/async_transport.py` and the AsyncTransport bits in `base.py`/`coordinator.py`, `## User decisions` → `### Async dispatch path`, Phase 6 |
| **7 — New adapters + extensions** | `## User decisions` → `### New adapters and adapter extensions in scope`, `## Pseudocode` → `### New adapters` and `### Adapter extensions`, Phase 7 |
| **8 — Live integration matrix** | `## Execution phases` → Phase 8 (it now contains the full live-test design inline) |
| **9a — Doc sweep (high-traffic)** | `## Documentation update sweep` (rows for README, SKILL, install, architecture, contributing, testing, security), Phase 9 |
| **9b — Doc sweep (remaining + reference)** | `## Documentation update sweep` (remaining rows), Phase 9 |
| **9c — Mermaid diagrams** | `## Mermaid diagrams → SVG embeds in documentation` (entire) |
| **10 — Final QA + PR** | `## Verification`, `## Critical files to open during implementation`, Phase 10 |

### Why this map matters

- The `## Pseudocode` section is ~830 lines. An agent loading all of it for a single phase wastes ~200k tokens. The map cuts that to ~100 lines per phase on average.
- The `## Feature parity audit` is needed in Phase 2 only — never in Phase 1, 3, 4, etc.
- The `## Documentation update sweep` is irrelevant until Phase 9 — agents in Phases 1–8 should never load it.
- The `## Pre-implementation steps` is huge but only matters for Phase 0 — it's stale ballast for every other phase.

If a phase needs a section not listed in its row, the implementer adds it temporarily and notes it in the next plan revision so the map stays accurate.

## Context

`gemini-skill` currently ships a stdlib-only raw HTTP client ([core/infra/client.py](core/infra/client.py)) that all 19 adapters call via three functions: `api_call`, `stream_generate_content`, `upload_file`. It works but (1) has no SDK path, (2) reimplements retry/streaming/multipart by hand, and (3) misses features that `google-genai` exposes natively.

The goal is to add a **google-genai SDK backend** as the primary transport, keep the existing raw HTTP code as a **fallback backend**, and gate the whole thing behind a **coordinator** that owns priority/fallback logic. Adapters must stay backend-agnostic.

Installation must move to a **skill-local `.venv`** so `google-genai` is isolated from system Python. SKILL.md must invoke via `${CLAUDE_SKILL_DIR}/.venv/bin/python`. Vendoring the SDK is forbidden.

Raw-HTTP churn must be minimized — adapters already route through three thin entrypoints, so we can preserve their call sites by making those entrypoints a facade over the coordinator.

## Auth + env var storage model (UPDATED — settings.json instead of .env)

**User decision (2026-04-13):** The installed skill must store its env vars in `~/.claude/settings.json` (the user-global Claude Code settings file) instead of `~/.claude/skills/gemini/.env`. The repo-root `.env.example` stays as a template for **local development testing only** (running `python3 scripts/gemini_run.py` from a clone, outside Claude Code).

### Two distinct runtime modes

| Mode | How env vars are loaded | Used for |
|---|---|---|
| **Installed-skill mode** (default for end users) | Claude Code reads `~/.claude/settings.json` `env` block on session start and exports each key into the subprocess env. The skill just calls `os.environ.get("GEMINI_API_KEY")`. | Daily use via `/gemini` slash command or any other Claude Code invocation. |
| **Local-dev mode** (contributors only) | The auth resolver falls back to reading a `.env` file at the **repo root** (NOT `~/.claude/skills/gemini/.env`) when the env var is not set in the process environment. `.env.example` documents the expected keys. | `pytest`, manual `python3 scripts/gemini_run.py`, CI live-test job. |

The previously-installed `~/.claude/skills/gemini/.env` is **deprecated** — `install_main.py` will detect it on update and migrate its contents into `settings.json`, then delete the file (with user confirmation).

### Concrete `~/.claude/settings.json` shape after install

After a fresh install on a machine where `~/.claude/settings.json` did not previously exist, the file looks like this:

```json
{
  "env": {
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0"
  }
}
```

After install on a machine where `~/.claude/settings.json` already existed with other tools' config, the merged file looks like this (only `env` is touched; every other top-level key is preserved byte-identical):

```json
{
  "model": "claude-opus-4-6",
  "permissions": {
    "allow": ["Bash(git status)", "Bash(git diff)"],
    "deny": []
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "..." }] }
    ]
  },
  "mcp": {
    "servers": { "context7": { "command": "...", "args": [...] } }
  },
  "env": {
    "EXISTING_TOOL_KEY": "preserved-untouched",
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0"
  }
}
```

The user then opens `~/.claude/settings.json` in their editor and replaces `"GEMINI_API_KEY": ""` with their real key:

```json
{
  "env": {
    "GEMINI_API_KEY": "AIzaSyA-your-real-key-here",
    "...": "..."
  }
}
```

If they want raw HTTP as the primary backend and SDK as the fallback (e.g., to test the fallback path or because they don't want google-genai installed), they flip the two priority flags:

```json
{
  "env": {
    "GEMINI_IS_SDK_PRIORITY": "false",
    "GEMINI_IS_RAWHTTP_PRIORITY": "true",
    "GEMINI_API_KEY": "AIzaSy..."
  }
}
```

After editing settings.json, the user must **fully restart VSCode (⌘Q on macOS, not "Reload Window")** for Claude Code to pick up the new env values — settings.json is read at session start, not on every tool invocation. This is documented in [docs/install.md](docs/install.md) troubleshooting.

### Settings.json env block: keys, write strategy, security

The installer writes the following keys into `~/.claude/settings.json`'s `env` object:

| Key | Default written by installer | Notes |
|---|---|---|
| `GEMINI_API_KEY` | `""` (empty placeholder) | User edits manually after install — installer never asks for it interactively. |
| `GEMINI_IS_SDK_PRIORITY` | `"true"` | If true, the SDK backend runs first; raw HTTP is the fallback. Exactly one of the two priority flags must be true. |
| `GEMINI_IS_RAWHTTP_PRIORITY` | `"false"` | If true, raw HTTP runs first; SDK is the fallback. Exactly one of the two priority flags must be true. |
| `GEMINI_LIVE_TESTS` | `"0"` | Master gate for the live integration test suite. Set to `"1"` to enable. The image-gen live test is gated by the same flag — there is no separate image-gen toggle. |

**Backend priority semantics:**
- The two flags `GEMINI_IS_SDK_PRIORITY` and `GEMINI_IS_RAWHTTP_PRIORITY` independently mark whether each backend is enabled and which one is preferred.
- **Resolution rules:**
  | `GEMINI_IS_SDK_PRIORITY` | `GEMINI_IS_RAWHTTP_PRIORITY` | Primary | Fallback |
  |---|---|---|---|
  | `true`  | `false` | SDK      | raw HTTP (always available) |
  | `false` | `true`  | raw HTTP | SDK (always available)      |
  | `true`  | `true`  | **SDK** (per user rule: when both are enabled, SDK always wins) | raw HTTP |
  | `false` | `false` | **ConfigError** at coordinator build time — "At least one of GEMINI_IS_SDK_PRIORITY / GEMINI_IS_RAWHTTP_PRIORITY must be true. Edit ~/.claude/settings.json env block." |
- The "both true" case is **not an error** — it's a valid configuration meaning "both backends are enabled; use SDK first". Coordinator handles it via a single rule: `primary = "sdk" if cfg.is_sdk_priority else "raw_http"` (SDK takes precedence whenever it's enabled).
- The "both false" case is the only invalid combination because there is no backend to run.
- Fallback is always available whenever both backends are enabled; there is no separate "disable fallback" flag. To force a single backend only, set the other one to `false`.
- Values are parsed case-insensitively; `"True"`, `"true"`, `"1"`, `"yes"` → True; `"False"`, `"false"`, `"0"`, `"no"`, `""` → False.

### `GEMINI_API_KEY` interactive setup (special-case BEFORE the generic merge)

`GEMINI_API_KEY` is the one key the installer asks the user to fill in interactively, because it's the single piece of information that prevents the skill from working out of the box. Every other key has a sensible default; the API key is unique. The installer handles `GEMINI_API_KEY` as a special case **before** the generic merge logic in the next subsection runs.

Algorithm (special-case for `GEMINI_API_KEY` only):

1. **Detect existing value** — read `~/.claude/settings.json` (creating an empty `{}` in memory if the file doesn't exist) and check whether `env.GEMINI_API_KEY` is present.
2. **Branch A — key already present** (any value, including `""`):
   ```
   Found existing GEMINI_API_KEY in ~/.claude/settings.json.
   What would you like to do?
     [u] Update it — enter a new value now (the new value will replace the existing one)
     [k] Keep it — leave the existing value untouched (recommended)
   Choice [u/k] (default k):
   ```
   - On **keep** (or `Enter`, or non-tty stdin, or `--yes`): no change. The generic merge later will see the key already exists and treat it as a "skip" without re-prompting.
   - On **update**: prompt for the new value (see step 4 for the input prompt details).
3. **Branch B — key absent**:
   ```
   GEMINI_API_KEY is not yet set in ~/.claude/settings.json.
   You can paste your key now and the installer will save it for you.
   You may also leave this empty and edit ~/.claude/settings.json later by hand.
   Get a key at: https://aistudio.google.com/apikey
   ```
   Then prompt for the value (step 4). Empty input is allowed and means "leave the entry as an empty string `""` so I can fill it in later".
4. **Value-input prompt** (used by both branches when the user opts to set a value):
   ```
   Enter your GEMINI_API_KEY (input is hidden, press Enter to leave empty):
   ```
   - Use `getpass.getpass()` from stdlib so the input is **not echoed** to the terminal. This protects the key from over-the-shoulder snooping and from terminal scrollback.
   - Strip leading/trailing whitespace from the input (a common copy-paste mistake) but otherwise preserve it byte-for-byte.
   - Empty input is accepted and stored as `""`. Print a one-line confirmation: `GEMINI_API_KEY left empty — edit ~/.claude/settings.json before first use.`
   - Non-empty input is stored as the literal value. Print: `GEMINI_API_KEY saved (<N> characters).` — only the length, never the value itself.
   - **Basic sanity check** (warning, not error): if the value doesn't start with `AIzaSy` (the typical Google API key prefix), print `WARNING: this doesn't look like a Google API key (expected prefix 'AIzaSy'). Saved anyway — verify it's correct.` Don't reject — Google may add new key formats and we shouldn't block on a heuristic.
5. **Write the value into the in-memory settings buffer** so the generic merge step that follows sees it as already-present and doesn't re-prompt.
6. **Non-interactive contexts** (CI, non-tty stdin, `--yes` flag): skip the GEMINI_API_KEY prompt entirely. If the key is absent, the generic merge later will add it as `""` like any other default. Print a one-line stderr warning: `GEMINI_API_KEY left empty (non-interactive install) — edit ~/.claude/settings.json before first use.`

This special case lives in `core/cli/install_main.py::_prompt_gemini_api_key(settings_buffer: dict, *, yes: bool, interactive: bool) -> None`. It's called once during install, before `_merge_settings_env`. Tests:

- `test_prompt_api_key_keeps_existing_when_user_chooses_keep`
- `test_prompt_api_key_updates_existing_when_user_chooses_update`
- `test_prompt_api_key_handles_absent_key_with_user_supplied_value`
- `test_prompt_api_key_handles_absent_key_with_empty_input`
- `test_prompt_api_key_strips_whitespace_from_input`
- `test_prompt_api_key_uses_getpass_no_echo` (mock `getpass.getpass`, assert it's called)
- `test_prompt_api_key_warns_on_unusual_prefix_but_saves_anyway`
- `test_prompt_api_key_never_prints_value_only_length`
- `test_prompt_api_key_skipped_under_yes_flag`
- `test_prompt_api_key_skipped_under_non_tty_with_stderr_warning`
- `test_prompt_api_key_default_choice_is_keep_when_existing`
- `test_prompt_api_key_invalid_choice_reprompts`

### Generic settings.json merge (runs AFTER the API key special case)

Write strategy (UPDATED — interactive per-key conflict resolution):

The installer is purely additive for non-conflicting keys, and **interactive** for conflicting ones. For every key in `_DEFAULT_ENV_KEYS` that already exists in `settings.json`'s `env` block, the installer prompts the user once asking whether to **replace** or **skip** that specific key. Each conflict is decided independently; non-conflicting keys are added without prompting.

Algorithm:
1. **If `~/.claude/settings.json` does not exist** → create it with `{"env": { ...all _DEFAULT_ENV_KEYS... }}`, write atomically. Done. No prompts.
2. **If it exists but is malformed JSON** → ABORT install. Print:
   ```
   ERROR: ~/.claude/settings.json is not valid JSON.
   Please fix it manually and re-run setup/install.py.
   The installer will not overwrite a malformed settings file.
   ```
   Exit code 2.
3. **If it exists and is valid JSON, but the top-level `env` key is missing** → add `env: {...all _DEFAULT_ENV_KEYS...}`, atomically write the full file (preserving every other top-level key untouched). Done. No prompts.
4. **If it exists and `env` is present** → walk `_DEFAULT_ENV_KEYS` in order:
   - If the key is **absent** from `env`, add it with the default value silently. No prompt.
   - If the key is **already present** in `env` (regardless of value — including empty string `""`), prompt the user interactively:
     ```
     CONFLICT: ~/.claude/settings.json already has env.GEMINI_API_KEY set.
       Existing value: <REDACTED — see settings.json>
       Installer's default: ""
     What would you like to do?
       [r] Replace with the installer's default
       [s] Skip — keep your existing value (recommended)
       [q] Quit installation
     Choice [r/s/q] (default s):
     ```
     - On **replace**: overwrite the value in the in-memory merge buffer. The user has explicitly authorized this single key replacement.
     - On **skip**: leave the existing value untouched. Default action on `Enter` (safest — never destroys user data without an explicit "r").
     - On **quit**: ABORT install with exit code 4. No file changes.
     - On any other input: re-prompt (don't assume).
5. **After the scan**, atomically write the merged settings.json. Print a summary listing each key as `added`, `kept (skipped)`, or `replaced`. Never print the actual values.

Important nuances:
- The prompt **never displays the existing value** of a conflicting key — only the literal token `<REDACTED — see settings.json>`. This protects secrets from terminal scrollback and CI logs. The user can open `settings.json` themselves if they need to inspect.
- The prompt **does** display the installer's default (which is either an empty string or a known plaintext like `"true"` / `"sdk"`) because those are not secrets.
- "Already present" means the **key exists**, not "the value is non-empty". An entry like `"GEMINI_API_KEY": ""` still triggers a prompt — the user may have intentionally left it blank to fill in later, and we shouldn't replace that with another empty string silently.
- The `--yes` flag auto-answers every conflict with **skip** (the safest default, never destroys data). To replace a conflicting key non-interactively, the user must edit `settings.json` first to remove the key, then re-run install. There is intentionally no `--replace-all` flag — that footgun is not worth the convenience.
- Non-interactive contexts (CI, install via subprocess from another tool) detect a non-tty stdin and behave like `--yes`: skip every conflict, print the summary at the end. Add a one-line warning to stderr in that case so the user knows conflicts were skipped without prompting.
- The atomic write uses `core/infra/atomic_write.py` → `tempfile + os.replace` → never half-writes.
- Every other top-level key in the existing settings.json (`hooks`, `permissions`, `mcp`, `model`, etc.) is preserved byte-identical.

The interactive prompt is implemented via `input()` from stdlib (not a third-party TUI library) so it has zero new dependencies and works in any terminal.

Security profile (matches the table from earlier in the conversation):
- `~/.claude/settings.json` is user-global, plaintext, lives in the user's home dir, and is **not** in any git repo. Risk profile is identical to a `~/.claude/skills/gemini/.env` file — both are plaintext on disk readable by the user account.
- `~/.claude/settings.local.json` is project-local, gitignored — also safe for secrets.
- `<repo>/.claude/settings.json` is **typically committed**. The installer NEVER writes to this file. Documented as a footgun in [docs/install.md](docs/install.md).

### Auth resolver changes (`core/auth/auth.py`)

```python
"""Resolve the Gemini API key from environment, settings, or local .env (dev mode)."""

def resolve_key(*, env_dir: Path | None = None) -> str:
    """Return a Gemini API key from the highest-precedence source available.

    Precedence:
    1. GEMINI_API_KEY env var (set by Claude Code from settings.json, or by shell)
    2. (Local-dev only) GEMINI_API_KEY in <repo-root>/.env when env_dir points to a repo

    The skill deliberately does NOT honor GOOGLE_API_KEY — GEMINI_API_KEY is the
    one canonical name to avoid confusion about which key the skill is using.

    Raises AuthError if no key is found.

    Args:
        env_dir: Optional directory to scan for a .env fallback. Used by local-dev
            and tests that run the runner directly from a repo clone. The installed
            skill does NOT pass this argument — it relies entirely on Claude Code's
            settings.json → process env injection.
    """
    if (key := os.environ.get("GEMINI_API_KEY")):
        return key
    if env_dir is not None:
        loaded = _load_env_file(env_dir / ".env")
        if (key := loaded.get("GEMINI_API_KEY")):
            return key
    raise AuthError(
        "No Gemini API key found.\n"
        "Installed skill: edit ~/.claude/settings.json and add GEMINI_API_KEY to the env block.\n"
        "Local dev: copy .env.example to .env at the repo root and fill in GEMINI_API_KEY."
    )
```

Concretely: the existing `_SKILL_ROOT` constant in `core/transport/sdk/client_factory.py` and `core/transport/raw_http/client.py` stops being passed to `resolve_key()`. Both backends just call `resolve_key()` with no arguments. The skill-root constant is deleted entirely (search-and-destroy `_SKILL_ROOT`). Local-dev mode passes `env_dir=Path(__file__).resolve().parent.parent.parent` from `scripts/gemini_run.py` ONLY when running outside the installed skill (detect via "is `sys.argv[0]` under `~/.claude/skills/gemini/`?").

### Existing GEMINI_LIVE_IMAGE_GEN references — must be removed

[tests/integration/test_image_gen_nano_banana_2_live.py](tests/integration/test_image_gen_nano_banana_2_live.py) currently gates on `GEMINI_LIVE_IMAGE_GEN=1` as an extra opt-in beyond `GEMINI_LIVE_TESTS=1`. Per the user decision to remove the redundant flag, this refactor must:

- Remove the `GEMINI_LIVE_IMAGE_GEN` `pytest.mark.skipif` from `test_image_gen_nano_banana_2_live.py`. The test now runs whenever `GEMINI_LIVE_TESTS=1` (same gate as every other live test).
- Remove any `GEMINI_LIVE_IMAGE_GEN` mention from `.env.example`, docs/testing.md, README.md, and any docstrings in the test file.
- Add a CI regression grep step (combined with the GOOGLE_API_KEY one):
  ```bash
  ! grep -rn "GEMINI_LIVE_IMAGE_GEN\|GOOGLE_API_KEY\|GEMINI_RECORD_MOCKS" core/ adapters/ scripts/ tests/ docs/ reference/ README.md SKILL.md .env.example setup/
  ```
- Document the removal in the doc-sweep table — the testing doc loses its "you also need to set GEMINI_LIVE_IMAGE_GEN" paragraph.

The cost trade-off (image gen is billable on every run) is now governed only by whether the user runs `GEMINI_LIVE_TESTS=1` at all. If they want to skip the image-gen test specifically without disabling the whole live suite, they use pytest's `-k 'not nano_banana'` filter. Documented in `docs/testing.md`.

### Existing GOOGLE_API_KEY references — must be removed

The current `core/auth/auth.py` (existing code, not new in this refactor) checks `GOOGLE_API_KEY` before `GEMINI_API_KEY` per the explore report. That precedence was the previous behavior. **This refactor must delete that branch** so `GEMINI_API_KEY` is the one and only honored env var. Concrete cleanup:

- [core/auth/auth.py](core/auth/auth.py) — remove the `os.environ.get("GOOGLE_API_KEY")` branch and the dict lookup for `GOOGLE_API_KEY` in `_load_env_file`. Update the function docstring.
- [tests/core/auth/test_auth.py](tests/core/auth/test_auth.py) — update tests that assert `GOOGLE_API_KEY` precedence; replace with explicit "ignored" tests proving that setting `GOOGLE_API_KEY` alone yields `AuthError` (because we don't honor it).
- Search the repo for any other `GOOGLE_API_KEY` mention in code, docs, reference files, `.env.example`, install/health/dispatch modules, and tests; remove every one. Add a regression `grep` step in CI:
  ```bash
  ! grep -rn "GOOGLE_API_KEY" core/ adapters/ scripts/ tests/ docs/ reference/ README.md SKILL.md .env.example
  ```
  CI fails if any reference resurfaces.
- Documentation: `docs/install.md`, `README.md`, and any troubleshooting docs that mention "you can use GOOGLE_API_KEY too" must be updated to say only `GEMINI_API_KEY`.

### `.env.example` (kept, repurposed as dev-only)

The file stays in the repo root because contributors running tests locally still need a place to put their key. **It must list every key from `_DEFAULT_ENV_KEYS` in the same order**, so that a reader scanning either file sees the same surface. Keeping the two in lockstep is enforced by a CI check (a small Python script that imports `_DEFAULT_ENV_KEYS` from `core/cli/install_main.py`, parses `.env.example`, and asserts the key sets match exactly).

Full rewritten content:

```bash
# .env.example — TEMPLATE FOR LOCAL DEVELOPMENT ONLY
#
# This file is for contributors running the skill from a repo clone via
#     python3 scripts/gemini_run.py <command> [args]
#
# End users do NOT use this file — the installer writes env vars into
# ~/.claude/settings.json instead. See docs/install.md for the user flow.
#
# To use locally:
#   1. Copy this file to .env at the repo root: cp .env.example .env
#   2. Fill in GEMINI_API_KEY with a key from https://aistudio.google.com/apikey
#   3. Adjust the optional values below if you need non-default behavior.
#   4. Run: python3 scripts/gemini_run.py text "hello"
#
# .env at the repo root is gitignored. NEVER commit a real key.
# This file (.env.example) is committed and must contain only placeholders.
#
# IMPORTANT: every key in _DEFAULT_ENV_KEYS (defined in core/cli/install_main.py)
# must appear here, in the same order. CI fails if they drift.

# === Required ===
GEMINI_API_KEY=

# === Backend priority (exactly one must be true; default is sdk first) ===
GEMINI_IS_SDK_PRIORITY=true
GEMINI_IS_RAWHTTP_PRIORITY=false

# === Live test gate (set to 1 to enable the live integration test suite) ===
# WARNING: live tests make real API calls and cost a few cents per run.
GEMINI_LIVE_TESTS=0
```

Notes:
- The file uses `KEY=value` syntax (one per line, no quotes) so it parses with the existing `_load_env_file` helper in `core/auth/auth.py`.
- Optional keys are NOT commented out anymore — they have explicit default values, matching what the installer writes into `~/.claude/settings.json`. This makes a contributor's local `.env` configuration identical to what an end user would see in their settings.json.
- If a future PR adds a new key to `_DEFAULT_ENV_KEYS`, the same PR MUST add the matching line to `.env.example` or CI fails. The CI check is:
  ```python
  # tests/test_env_example_in_sync.py (new test file)
  from pathlib import Path
  from core.cli.install_main import _DEFAULT_ENV_KEYS

  def test_env_example_lists_all_default_keys():
      content = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
      example_keys = {line.split("=", 1)[0] for line in content.splitlines()
                      if line and not line.startswith("#") and "=" in line}
      assert example_keys == set(_DEFAULT_ENV_KEYS), (
          f"Drift between .env.example and _DEFAULT_ENV_KEYS:\n"
          f"  in example only: {example_keys - set(_DEFAULT_ENV_KEYS)}\n"
          f"  in defaults only: {set(_DEFAULT_ENV_KEYS) - example_keys}"
      )
  ```
  This test runs in every PR. Add it to the Phase 4 TDD checklist.

The repo-root `.env` (without `.example`) is gitignored — verify [.gitignore](.gitignore) lists it; add if missing.

### Install flow updates (overrides the earlier install_main.py spec)

```python
def main(argv: Sequence[str]) -> int:
    """End-to-end install: copy → checksums → venv → pip → verify → API key prompt → settings merge."""
    args = _parse_args(argv)
    install_dir = Path("~/.claude/skills/gemini").expanduser()
    settings_path = Path("~/.claude/settings.json").expanduser()

    _copy_files(SOURCE, install_dir)
    if not args.skip_checksum:
        _verify_checksums(install_dir)
    venv_path = install_dir / ".venv"
    _create_venv(venv_path)
    _pip_install_requirements(venv_path, install_dir / "setup" / "requirements.txt")
    _verify_sdk_importable(venv_path)

    # NEW: build an in-memory merge buffer of the existing settings.json content,
    # then handle the GEMINI_API_KEY special case interactively, then run the
    # generic per-key merge for the rest of the defaults.
    settings_buffer = _read_settings_or_empty(settings_path)
    _prompt_gemini_api_key(settings_buffer, yes=args.yes, interactive=sys.stdin.isatty())
    _merge_settings_env(settings_buffer, _DEFAULT_ENV_KEYS, yes=args.yes, interactive=sys.stdin.isatty())
    _atomic_write_settings(settings_path, settings_buffer)

    # NEW: detect legacy .env from previous installs and migrate
    legacy_env = install_dir / ".env"
    if legacy_env.exists():
        _migrate_legacy_env_to_settings(legacy_env, settings_path, prompt=not args.yes)

    _print_summary(venv_path, sdk_version, settings_path)
    return 0

_DEFAULT_ENV_KEYS: dict[str, str] = {
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0",  # default DISABLED — set to "1" to opt in to live API tests (cost)
}

def _merge_settings_env(settings_path: Path, defaults: Mapping[str, str]) -> None:
    """Merge default Gemini env keys into settings.json without clobbering existing values.

    Behavior:
    - If settings.json doesn't exist, create it with `{"env": {...defaults}}`.
    - If settings.json exists but is malformed, raise InstallError (do not overwrite).
    - If settings.json exists and is valid, ensure the `env` key exists and add any
      missing default keys without modifying values that are already set.
    - Write atomically via atomic_write_json with mode 0o600.
    """

def _migrate_legacy_env_to_settings(legacy_env: Path, settings_path: Path, *, prompt: bool) -> None:
    """One-time migration from ~/.claude/skills/gemini/.env to ~/.claude/settings.json.

    Reads the legacy .env, merges any non-empty values into settings.json's env block
    (still without clobbering existing values), then prompts the user to confirm
    deletion of the legacy file. With --yes, deletes without prompting.
    """
```

New tests (full coverage of the merge algorithm — interactive prompt branch tests use `monkeypatch.setattr("builtins.input", ...)` to script user choices):

- `test_merge_settings_creates_file_when_missing` — settings.json absent → file created with all defaults under `env`. No prompts called.
- `test_merge_settings_creates_env_block_when_missing` — file exists, `env` key missing → `env` added with all defaults. No prompts called.
- `test_merge_settings_adds_only_missing_keys_silently` — file exists with `env: {OTHER_TOOL_KEY: "val"}` → all defaults added, `OTHER_TOOL_KEY` preserved, no prompts called.
- `test_merge_settings_aborts_on_malformed_json` — file contains invalid JSON → `InstallError` raised, file untouched on disk, exit code 2.
- `test_merge_settings_prompts_on_duplicate_key_with_empty_string` — file already has `GEMINI_API_KEY: ""` → prompt is shown exactly once for that key. **Critical: empty string still triggers the prompt.**
- `test_merge_settings_prompts_on_duplicate_key_with_real_value` — file has `GEMINI_API_KEY: "AIza..."` → prompt shown; the prompt text contains `<REDACTED — see settings.json>` and does NOT contain `AIza`.
- `test_merge_settings_skip_keeps_existing_value` — user types `s` → value unchanged, summary lists key as "kept (skipped)".
- `test_merge_settings_replace_overwrites_value` — user types `r` → value replaced with the installer's default.
- `test_merge_settings_quit_aborts_install` — user types `q` → exit code 4, no file changes.
- `test_merge_settings_default_choice_is_skip` — user just presses Enter → behaves like `s`.
- `test_merge_settings_invalid_input_reprompts` — user types `xyz` → re-prompt loop, doesn't assume.
- `test_merge_settings_multiple_conflicts_prompted_independently` — file has `GEMINI_API_KEY` AND `GEMINI_IS_SDK_PRIORITY` → two separate prompts, decisions tracked per key.
- `test_merge_settings_never_prints_secret_values` — capture stdout/stderr across all conflict tests; assert no `AIza...` substring or any value from the env block leaks. Only `<REDACTED — see settings.json>` token appears.
- `test_merge_settings_preserves_other_top_level_keys` — file has `{hooks: {...}, permissions: {...}, env: {}}` → after merge, `hooks` and `permissions` are byte-identical.
- `test_merge_settings_preserves_unknown_env_keys` — file has `env: {SOMETHING_ELSE: "x"}` and no GEMINI_* keys → after merge, `SOMETHING_ELSE` preserved AND all defaults added (no prompts because no overlap).
- `test_merge_settings_atomic_write_on_failure_keeps_original` — simulate disk-full mid-write → original file is unchanged.
- `test_yes_flag_auto_skips_all_conflicts` — pass `--yes`; conflict prompts are not shown; every conflict is treated as `skip`; summary reports each as "kept (skipped)".
- `test_non_tty_stdin_auto_skips_with_warning` — simulate non-tty stdin (CI mode); same as `--yes` plus a one-line stderr warning.
- `test_migrate_legacy_env_to_settings_happy_path` — legacy `~/.claude/skills/gemini/.env` exists with values that are NOT yet in settings.json → values are merged in, no prompts.
- `test_migrate_legacy_env_with_conflict_prompts` — legacy `.env` has `GEMINI_API_KEY=foo` AND settings.json already has `GEMINI_API_KEY=bar` → prompt shown using the same per-key flow; user picks replace/skip/quit.
- `test_migrate_legacy_env_with_user_decline_keeps_legacy_file` — interactive prompt declined → file kept.

### Documentation updates (additions to the doc-sweep table)

| Doc | New requirement |
|---|---|
| [README.md](README.md) | Quick Start: post-install step is "edit `~/.claude/settings.json` and set `GEMINI_API_KEY`". Show the JSON snippet. Explain that this is user-global, persists across all Claude Code sessions, and is the same security profile as a `.env` file in your home dir. Add a one-paragraph "Local development" subsection pointing contributors at `.env.example` → repo-root `.env`. |
| [SKILL.md](SKILL.md) | One-line note: "API key and backend config are read from `~/.claude/settings.json` env block. See README for setup." |
| [docs/install.md](docs/install.md) | Major rewrite of the "where does my key go" section. Add the three-flavor settings.json table (user-global / project-shared / project-local) with the safety profile. Show how to migrate from a legacy `~/.claude/skills/gemini/.env`. Add troubleshooting: "I edited settings.json and Claude Code still says no key" → restart VSCode (⌘Q), not Reload Window. |
| [docs/security.md](docs/security.md) | Update the auth section: settings.json is the canonical key store; `.env` files are a local-dev convenience. Document the "never commit project-shared settings.json with secrets" footgun. Note that the installer never writes to project-shared `settings.json`. |
| [docs/contributing.md](docs/contributing.md) | New "Local development setup" subsection: copy `.env.example` to `.env` at repo root, edit, run tests. Make clear this `.env` is repo-local and gitignored — distinct from the deprecated `~/.claude/skills/gemini/.env`. |
| [docs/testing.md](docs/testing.md) | Live tests: prefer setting `GEMINI_API_KEY` in the shell or in repo-root `.env` (not in user-global settings.json) so tests don't depend on Claude Code being installed. |
| `.env.example` | Rewrite header per the snippet above. |
| New: `docs/env-vars-reference.md` | Single source of truth listing every env var, its purpose, default, and where to set it (settings.json vs repo .env vs shell). Linked from README and install.md. |

## Pre-implementation steps

Before writing any code, run these git steps from the repo root in order. Each must succeed before the next.

1. `git status` — confirm the working tree is clean. If there are uncommitted changes, stop and ask the user.
2. `git checkout main` — leave the current `feat/initial-implementation` branch.
3. `git pull --ff-only origin main` — fast-forward to the latest. If this is not fast-forward, stop and ask the user.
4. `git checkout -b refactor/dual-backend-sdk-and-raw-http` — create the working branch off freshly-pulled main.
5. `git status` to confirm we are on the new branch with a clean tree.

6. **Create and activate a development virtual environment, then install all libraries the refactor needs.** This must happen BEFORE any code is written so every TDD loop, every test run, every linter call uses an isolated, reproducible Python environment. Do NOT use system Python. The skill's runtime `.venv` (created by Phase 5's installer) is a separate, end-user-facing venv at `~/.claude/skills/gemini/.venv` — that one comes later. The development venv created here lives at the repo root and is the one all contributors use locally.

   Steps (all run from the repo root):

   a. **Create the dev venv** at the repo root:
      ```bash
      python3 --version  # confirm 3.9+
      python3 -m venv .venv
      ```
      The `.venv/` directory is already gitignored (verify: `grep -q '^\.venv/' .gitignore || echo 'WARNING: add .venv/ to .gitignore'`).

   b. **Activate the venv**:
      ```bash
      source .venv/bin/activate
      ```
      Confirm: `which python` should return a path under `.venv/bin/`. Confirm: `python -c "import sys; print(sys.prefix)"` should print the `.venv` path.

   c. **Upgrade pip inside the venv** so subsequent installs use the latest resolver:
      ```bash
      python -m pip install --upgrade pip
      ```

   d. **Install the runtime dependency** (`google-genai`) at the version this refactor pins. Phase 5 will create `setup/requirements.txt` with this same pin; for now we install it directly so Phases 1-4 can `Mock(spec=genai.Client)` and run their tests. This is the same step CR-6 calls for in CI:
      ```bash
      python -m pip install google-genai==1.33.0
      ```

   e. **Update `setup/requirements.txt` and `setup/requirements-dev.txt`** so the pinned versions are committed to source control before any code uses them. Phase 5's installer reads `setup/requirements.txt` to populate the runtime venv at `~/.claude/skills/gemini/.venv`; updating both files in pre-impl means:
      - There is one canonical source of truth for what the refactor pins, even before Phase 5 lands.
      - The dev venv (this venv at the repo root) and the future runtime venv install the exact same versions.
      - The `tests/test_env_example_in_sync.py` and `setup/requirements.txt` consistency tests in Phase 5 already have valid input.

      Edit `setup/requirements.txt` to contain (creating the file if it doesn't exist):
      ```
      # Runtime dependencies for gemini-skill. Pinned exactly — do not loosen.
      # To upgrade: bump the version, run setup/install.py, run the live test suite under both backends, then merge.
      # Reference: https://github.com/googleapis/python-genai
      google-genai==1.33.0
      ```

      Edit `setup/requirements-dev.txt` to add the dev/test dependencies (preserving any lines already present from prior PRs):
      ```
      # Existing dev deps (preserve whatever is already here) +
      pytest>=8.0
      pytest-cov>=4.1
      pytest-asyncio==0.23.7
      deepdiff==7.0.1
      mypy>=1.8
      ruff>=0.5
      black==24.8.0
      ```

      `black` is the canonical Python formatter for this refactor. The pre-push hook described below auto-formats every Python file before allowing a push.

      Commit both files in a separate commit on the new branch with message `chore(deps): pin runtime + dev dependencies for dual-backend refactor`. This commit lands BEFORE any production code change so that bisecting is clean — if a later commit breaks something, the dependency state is the same as it is now.

   f. **Install the dev dependencies INTO the activated venv from the requirements file** (so the venv state is exactly what `setup/requirements-dev.txt` describes):
      ```bash
      python -m pip install -r setup/requirements-dev.txt
      ```
      This is the canonical install command — it pulls every line from the file. Re-running it is idempotent. New contributors joining mid-refactor run the same command and get the same versions.

   g. **Verify everything imports cleanly**:
      ```bash
      python -c "import google.genai; print('google-genai', google.genai.__version__)"
      python -c "import pytest, pytest_asyncio, deepdiff, mypy, ruff; print('dev deps ok')"
      ```
      Both lines must print successfully. If `google.genai` import fails, do not proceed — debug the venv before continuing.

   h. **Run the existing test suite once** to confirm the dev venv can execute the current codebase before any refactor changes land. This is the baseline:
      ```bash
      pytest --tb=short -q
      ```
      Note the pass/fail count. Phase 1 must not regress this baseline (excluding the tests that are intentionally being modified).

   i. **Stay in the activated venv** for the rest of the refactor. Every TDD loop, every `pytest`, every `mypy --strict`, every `ruff` run, every `python scripts/gemini_run.py` invocation in local-dev mode must happen with this venv active. To re-activate in a new terminal session: `cd /Users/springfield/dev/gemini-skill && source .venv/bin/activate`.

   j. **Install a pre-push git hook that auto-formats with `black` and re-commits if anything changed.** This guarantees that no unformatted Python is ever pushed to the remote, and that the auto-format change is captured as its own commit so reviewers can see exactly what changed.

      Create `.git/hooks/pre-push` with the following content (and `chmod +x` it):
      ```bash
      #!/usr/bin/env bash
      # Pre-push hook: auto-format Python with black; if anything changed, stage,
      # commit, and re-push. This hook is local (lives under .git/hooks/) so it
      # is NOT version-controlled — every contributor installs it via the
      # bootstrap script described below.
      set -euo pipefail

      # Activate the dev venv so we use the pinned black version.
      REPO_ROOT="$(git rev-parse --show-toplevel)"
      if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
        # shellcheck source=/dev/null
        source "$REPO_ROOT/.venv/bin/activate"
      else
        echo "[pre-push] WARNING: dev .venv not found at $REPO_ROOT/.venv — skipping black format pass"
        exit 0
      fi

      # Verify black is installed in the venv.
      if ! command -v black >/dev/null 2>&1; then
        echo "[pre-push] ERROR: black not installed in dev venv. Run: pip install -r setup/requirements-dev.txt"
        exit 1
      fi

      echo "[pre-push] Running black on the staged Python files..."

      # Find tracked Python files in the working tree (we format the whole tree, not just the diff,
      # so we never push a half-formatted commit).
      mapfile -t PY_FILES < <(git ls-files '*.py')
      if [ ${#PY_FILES[@]} -eq 0 ]; then
        echo "[pre-push] No Python files tracked — skipping."
        exit 0
      fi

      # Run black. Capture whether it modified anything.
      if ! black --line-length 100 --target-version py39 "${PY_FILES[@]}"; then
        echo "[pre-push] ERROR: black failed (syntax error?)"
        exit 1
      fi

      # If black changed any files, stage them, create a formatting commit, and abort the push
      # so the user re-pushes (which re-runs this hook on the new tip — idempotent).
      if ! git diff --quiet; then
        echo "[pre-push] black reformatted some files — staging and committing..."
        git add -u
        git commit -m "style(format): auto-format with black via pre-push hook"
        echo ""
        echo "[pre-push] A formatting commit was created. Re-run 'git push' to push it."
        echo "[pre-push] (The push you just attempted has been blocked so the new commit is included.)"
        exit 1
      fi

      echo "[pre-push] black: no changes needed."
      exit 0
      ```

      Add a bootstrap helper at `scripts/install_git_hooks.sh` (committed to the repo) that copies this file into `.git/hooks/pre-push` and makes it executable. Document it in `docs/contributing.md`:
      ```bash
      bash scripts/install_git_hooks.sh
      ```
      Every new contributor runs this once after cloning. The script is idempotent — running it twice does nothing on the second run.

      **Important behavioral notes:**
      - The hook runs on `git push` (not on `git commit`) — formatting happens at the LAST possible moment so quick TDD-loop commits aren't slowed down.
      - When black makes a change, the hook **blocks the push** with exit code 1 after creating the formatting commit. The user simply re-runs `git push`. The second push has nothing left to format and goes through.
      - The hook is **per-machine**, lives in `.git/hooks/`, and is therefore NOT version-controlled. The bootstrap script is the version-controlled installer.
      - The hook activates the repo-root `.venv` so it always uses the pinned `black==24.8.0` from `setup/requirements-dev.txt`. If the venv is missing, the hook warns and skips (it does not block the push) so contributors who haven't run pre-impl step 6 yet can still push their first commit.
      - Tests for the bootstrap script: `tests/scripts/test_install_git_hooks.sh` (a small bash test that runs the bootstrap in a tmpdir, verifies the hook exists, verifies it is executable, runs it on a fixture file with a formatting violation, asserts the commit was created).

   Notes:
   - The dev `.venv` at the repo root is **not** the same as the runtime `~/.claude/skills/gemini/.venv` that Phase 5's installer creates. The dev venv is for *contributors running tests*; the runtime venv is for *end users running the installed skill*. Both pin the same `google-genai==1.33.0` from `setup/requirements.txt` (which lands in Phase 5).
   - The dev venv is repo-local and gitignored. Never commit `.venv/`.
   - If the dev venv ever gets corrupted (e.g. `pip install` of an unrelated package breaks something), delete it and re-run steps a–f.
   - On Windows, replace `source .venv/bin/activate` with `.venv\Scripts\activate.bat`.

7. **Copy this plan file into the repo** at `docs/planning/refactor-dual-backend-sdk-and-raw-http.md` so it is versioned alongside the code it describes. Source: `/Users/springfield/.claude/plans/piped-drifting-glade.md`. Create the `docs/planning/` directory if it does not exist. Commit this copy as the first commit on the branch with message `docs(planning): add dual-backend transport refactor plan` so reviewers can read the plan in PR context.

8. **Migrate the developer's existing `.env` into `~/.claude/settings.json`** (one-time, done by hand here BEFORE any code lands). This is intentionally a manual step in the pre-implementation phase rather than a code-driven migration, because:
   - The developer running this refactor already has working keys in either `~/.claude/skills/gemini/.env` (legacy installed-skill location) or the repo-root `.env` (local-dev location).
   - The new code will not be in place yet, so we can't rely on `_merge_settings_env` from `core/cli/install_main.py` — that's Phase 5 work.
   - Doing it now means the developer can run the new test suite from the very first TDD loop using the same key-resolution path that end users will hit.

   Steps (run from the repo root, no LLM agent needed — straight shell work):

   a. **Inventory existing key sources.** Check both legacy locations:
      ```bash
      [ -f ~/.claude/skills/gemini/.env ] && echo "found legacy installed-skill .env" && cat ~/.claude/skills/gemini/.env
      [ -f .env ] && echo "found repo-root .env" && cat .env
      ```
      Note: these `cat` calls print the key to the terminal. Run them in a fresh terminal window you'll close immediately after; do not save the scrollback.

   b. **Read existing `~/.claude/settings.json`** (if present):
      ```bash
      [ -f ~/.claude/settings.json ] && cat ~/.claude/settings.json | python3 -m json.tool
      ```
      If the file is malformed JSON, fix it manually first — the future installer will refuse to touch malformed files, and we want to validate the new contract from day one.

   c. **Check for duplicate keys before merging.** For each of the env keys listed in `_DEFAULT_ENV_KEYS` (`GEMINI_API_KEY`, `GEMINI_IS_SDK_PRIORITY`, `GEMINI_IS_RAWHTTP_PRIORITY`, `GEMINI_LIVE_TESTS`), check whether `~/.claude/settings.json` already has it under `env`:
      ```bash
      python3 -c '
      import json, sys
      from pathlib import Path
      p = Path.home() / ".claude" / "settings.json"
      data = json.loads(p.read_text()) if p.exists() else {}
      env = data.get("env", {})
      keys = ["GEMINI_API_KEY", "GEMINI_IS_SDK_PRIORITY", "GEMINI_IS_RAWHTTP_PRIORITY", "GEMINI_LIVE_TESTS"]
      conflicts = [k for k in keys if k in env]
      if conflicts:
          print("CONFLICTS (do NOT overwrite):", ", ".join(conflicts))
          sys.exit(1)
      print("no conflicts; safe to merge")
      '
      ```
      If conflicts are reported, **stop and resolve them by hand** — same rule as the future installer. Decide for each conflicting key whether to keep the existing value or replace with a new one, edit `settings.json` accordingly, then re-run the conflict check until it reports no conflicts.

   d. **Merge the keys** (only those that are absent — never overwrite). Open `~/.claude/settings.json` in your editor and add the following under the `env` object (creating `env` if it doesn't exist; preserving every other top-level key untouched):
      ```json
      "env": {
        "GEMINI_API_KEY": "<paste from your existing .env>",
        "GEMINI_IS_SDK_PRIORITY": "true",
        "GEMINI_IS_RAWHTTP_PRIORITY": "false",
        "GEMINI_LIVE_TESTS": "0"
      }
      ```
      Save. Verify the file is still valid JSON: `python3 -m json.tool < ~/.claude/settings.json > /dev/null && echo OK`.

   e. **Keep the repo-root `.env`** (if any). It's still used for local-dev mode when running `python3 scripts/gemini_run.py` directly from the repo without going through Claude Code — the auth resolver's `env_dir` fallback reads it. Verify it's gitignored:
      ```bash
      grep -q '^\.env$' .gitignore && echo "gitignored OK" || echo "WARNING: .env is NOT gitignored — fix .gitignore now"
      ```

   This pre-implementation migration mirrors exactly what the Phase 5 installer will do automatically for end users. By doing it manually now, the developer validates the contract end-to-end before writing the code that automates it — if any step is awkward, fix it in the plan before Phase 5 starts.

9. Only then begin Phase 1 of the TDD workflow (writing `tests/transport/test_policy.py` first), with the dev venv from step 6 still active.

If any pre-implementation step fails, the implementer must surface the failure and pause for instructions rather than improvising (no `git stash`, no `--force`, no `git pull --rebase` unless the user approves).

## Architecture summary

```
adapters/*  ──►  core.transport (facade: api_call / stream_generate_content / upload_file)
                        │
                        ▼
                TransportCoordinator
                  ├─ reads Config.is_sdk_priority / is_rawhttp_priority (exactly one true)
                  ├─ tries primary via Transport protocol
                  ├─ on eligible failure → tries fallback
                  └─ returns normalized dict OR raises final APIError
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   SdkTransport              RawHttpTransport
   (google-genai)            (current client.py logic)
          │                           │
          ▼                           ▼
   SDK client objects          urllib Request/Response
   → normalized to             → already returns the
     REST-shaped dict            REST-shaped dict
```

Both transports return the **same dict shape** the existing `extract_text`/`extract_parts` helpers already expect (Gemini REST v1beta envelope: `{candidates:[{content:{parts:[...]}}], usageMetadata:{...}}`). The SDK backend serializes SDK response objects back into that envelope so [core/adapter/helpers.py](core/adapter/helpers.py) and every adapter stay untouched.

Auth stays centralized in [core/auth/auth.py](core/auth/auth.py) `resolve_key(env_dir=...)`. The installed skill calls `resolve_key()` with no arguments — it relies entirely on Claude Code injecting `GEMINI_API_KEY` from `~/.claude/settings.json` into the process env. The `env_dir` argument is only passed by `scripts/gemini_run.py` in local-dev mode (running from a repo clone). The `_SKILL_ROOT` constant is deleted entirely. See the `## Auth + env var storage model` section for the full design.

### Fallback eligibility rules

Fallback runs **only** for transport-class failures. Enforced in `core/transport/policy.py::is_fallback_eligible(error) -> bool`:

**Eligible** (fallback runs):
- `ImportError` / `ModuleNotFoundError` (SDK not installed)
- Transport/network: `URLError`, `socket.timeout`, `ConnectionError`, SDK's `ServerError`/`DeadlineExceeded`
- HTTP 5xx, 429 after the backend exhausts its own retries
- Backend-specific unsupported-capability (`CapabilityUnavailableError` raised from within a backend)
- Backend-side response-parsing failure

**Not eligible** (error propagates immediately):
- `AuthError` — bad key is bad on both backends
- HTTP 4xx except 429 (bad request, permission, not found)
- Safety/policy block returned as a successful response
- `ValueError`/`TypeError`/`AssertionError` from shared code (programmer bugs)
- `CostLimitError` (shared policy, not transport)

## Proposed folder structure

```
core/
  transport/
    __init__.py              # public facade: api_call, stream_generate_content, upload_file
    base.py                  # Transport protocol + TransportError taxonomy
    coordinator.py           # TransportCoordinator: primary/fallback execution
    policy.py                # is_fallback_eligible() decision table
    normalize.py             # SDK-response → REST-envelope dict
    sdk/
      __init__.py
      transport.py           # SdkTransport implements Transport protocol
      client_factory.py      # lazy google.genai.Client construction, auth wiring
    raw_http/
      __init__.py
      transport.py           # RawHttpTransport implements Transport protocol
      client.py              # MOVED from core/infra/client.py (content mostly unchanged)
  infra/
    client.py                # SHIM: re-exports from core.transport for backward compat
    config.py                # + is_sdk_priority / is_rawhttp_priority
    errors.py                # + TransportError base, BackendUnavailableError
```

Adapters keep their existing `from core.infra.client import api_call, stream_generate_content, upload_file` — that module becomes a 5-line re-export shim pointing at `core.transport`. Zero adapter edits.

## Final repository layout (after refactor)

Tree below shows the **complete** file layout the implementation must produce. **Bold** = new file. *Italic* = modified file. Everything else is unchanged.

```
gemini-skill/
├── .env.example
├── .github/workflows/
│   ├── ci.yml                                        (* updated: --cov-fail-under=100 on core/transport)
│   └── release.yml
├── .gitignore                                        (* updated: ignore .venv/ if not already)
├── LICENSE
├── README.md                                         (* updated: venv-based install instructions)
├── SKILL.md                                          (* updated: ${CLAUDE_SKILL_DIR}/.venv/bin/python invocation)
├── VERSION
│
├── adapters/                                         (UNCHANGED — zero adapter edits)
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── batch.py
│   │   ├── cache.py
│   │   ├── embeddings.py
│   │   ├── file_search.py
│   │   ├── files.py                                  (* extended: + download subcommand)
│   │   ├── token_count.py
│   ├── experimental/
│   │   ├── __init__.py
│   │   ├── computer_use.py
│   │   └── deep_research.py
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── imagen.py                                 ** NEW ** Imagen 3 text-to-image
│   │   ├── live.py                                   ** NEW ** Live API realtime (async)
│   │   ├── multimodal.py
│   │   ├── streaming.py
│   │   ├── structured.py
│   │   └── text.py
│   ├── media/
│   │   ├── __init__.py
│   │   ├── image_gen.py                              (* extended: + --aspect-ratio / --image-size)
│   │   ├── music_gen.py
│   │   └── video_gen.py
│   └── tools/
│       ├── __init__.py
│       ├── code_exec.py
│       ├── function_calling.py
│       ├── maps.py
│       └── search.py                                 (* extended: + --show-grounding)
│
├── core/
│   ├── __init__.py
│   ├── adapter/                                      (UNCHANGED)
│   │   ├── __init__.py
│   │   ├── contract.py
│   │   └── helpers.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── dispatch.py                               (* updated: IS_ASYNC adapter detection)
│   │   ├── health_main.py                            (* updated: report backend + venv + SDK version)
│   │   ├── install_main.py                           (* updated: thin orchestrator only — calls installer/ submodules)
│   │   ├── installer/                                ** NEW subpackage (split from install_main.py)
│   │   │   ├── __init__.py                           **
│   │   │   ├── settings_merge.py                     ** NEW: settings.json merge + duplicate-key conflict resolution
│   │   │   ├── api_key_prompt.py                     ** NEW: GEMINI_API_KEY interactive setup
│   │   │   ├── venv.py                               ** NEW: .venv creation + pip install requirements
│   │   │   └── legacy_migration.py                   ** NEW: legacy ~/.claude/skills/gemini/.env migration
│   │   └── update_main.py                            (* updated: re-install pinned deps without --upgrade)
│   ├── auth/                                         (* updated: GOOGLE_API_KEY branch removed)
│   │   ├── __init__.py
│   │   └── auth.py                                   (* extended: only honors GEMINI_API_KEY)
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── atomic_write.py
│   │   ├── checksums.py                              ** NEW ** (TODO → feature: install/update integrity)
│   │   ├── client.py                                 (* REWRITTEN as 5-line shim → core.transport)
│   │   ├── config.py                                 (* updated: is_sdk_priority/is_rawhttp_priority + computed properties)
│   │   ├── cost.py
│   │   ├── errors.py                                 (* updated: BackendUnavailableError + APIError extension)
│   │   ├── filelock.py
│   │   ├── mime.py
│   │   ├── sanitize.py
│   │   └── timeouts.py
│   ├── routing/                                      (UNCHANGED)
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── router.py
│   │   └── tool_state.py
│   ├── state/                                        (UNCHANGED)
│   │   ├── __init__.py
│   │   ├── file_state.py
│   │   ├── identity.py
│   │   ├── session_state.py
│   │   └── store_state.py
│   └── transport/                                    ** NEW PACKAGE **
│       ├── __init__.py                               ** facade: sync + async api_call/stream/upload
│       ├── base.py                                   ** Transport + AsyncTransport protocols + dataclasses
│       ├── coordinator.py                            ** TransportCoordinator (sync + async, missing-surface cache)
│       ├── policy.py                                 ** is_fallback_eligible (incl. AttributeError/ImportError/TypeError)
│       ├── normalize.py                              ** sdk_response_to_rest_envelope (incl. grounding_metadata)
│       ├── raw_http/
│       │   ├── __init__.py                           **
│       │   ├── client.py                             ** MOVED from core/infra/client.py (content unchanged)
│       │   └── transport.py                          ** RawHttpTransport (sync only)
│       └── sdk/
│           ├── __init__.py                           **
│           ├── client_factory.py                     ** lazy genai.Client (API-key auth only)
│           ├── transport.py                          ** SdkTransport (sync)
│           └── async_transport.py                    ** SdkAsyncTransport via client.aio.*
│
├── docs/
│   ├── architecture.md                               (* updated: dual-backend diagram + fallback policy)
│   ├── capabilities.md
│   ├── commands.md
│   ├── contributing.md                               (* updated: TDD + 100% coverage rule + pinned deps)
│   ├── how-it-works.md                               (* updated: SDK vs raw HTTP path)
│   ├── install.md                                    (* updated: venv steps + setup/requirements.txt)
│   ├── model-routing.md
│   ├── planning/
│   │   ├── implementation-plan.md
│   │   └── refactor-dual-backend-sdk-and-raw-http.md ** NEW (this plan, copied in pre-impl step 6)
│   ├── python-guide.md
│   ├── security.md                                   (* updated: SDK trust boundary + pinned dep rationale)
│   ├── testing.md                                    (* updated: 100% coverage gate)
│   ├── update-sync.md                                (* updated: pinned-version upgrade workflow)
│   └── usage.md
│
├── reference/                                        (UNCHANGED)
│   ├── batch.md
│   ├── cache.md
│   ├── code_exec.md
│   ├── computer_use.md
│   ├── deep_research.md
│   ├── embed.md
│   ├── file_search.md
│   ├── files.md
│   ├── function_calling.md
│   ├── image_gen.md
│   ├── index.md
│   ├── maps.md
│   ├── multimodal.md
│   ├── music_gen.md
│   ├── search.md
│   ├── streaming.md
│   ├── structured.md
│   ├── text.md
│   ├── token_count.md
│   └── video_gen.md
│
├── registry/                                         (UNCHANGED)
│   ├── capabilities.json
│   └── models.json
│
├── scripts/
│   ├── gemini_run.py                                 (* updated: re-exec under .venv if available)
│   └── health_check.py
│
├── setup/
│   ├── install.py                                    (UNCHANGED launcher; logic in install_main.py)
│   ├── requirements.txt                              ** NEW ** runtime deps, pinned (google-genai==X.Y.Z)
│   ├── requirements-dev.txt                          (existing dev/test deps — unchanged)
│   ├── run_tests.sh
│   └── update.py
│
└── tests/
    ├── __init__.py
    ├── adapters/                                     (UNCHANGED — every existing adapter test stays green)
    │   ├── conftest.py
    │   ├── data/{test_batch,test_cache,test_embeddings,test_file_search,test_files,test_token_count}.py
    │   ├── experimental/{test_computer_use,test_deep_research}.py
    │   ├── generation/{test_multimodal,test_streaming,test_structured,test_text}.py
    │   ├── media/{test_image_gen,test_music_gen,test_video_gen}.py
    │   └── tools/{test_code_exec,test_function_calling,test_maps,test_search}.py
    ├── scripts/                                      (* backfilled — was empty)
    │   ├── __init__.py
    │   ├── test_gemini_run.py                        ** NEW
    │   └── test_health_check.py                      ** NEW
    ├── core/
    │   ├── adapter/{test_contract,test_helpers}.py
    │   ├── auth/test_auth.py
    │   ├── cli/
    │   │   ├── test_dispatch.py                      (* extended: IS_ASYNC adapter detection)
    │   │   ├── test_health_main.py                   (* extended: backend + venv + SDK version assertions)
    │   │   ├── test_install_main.py                  (* slim — only the thin orchestrator)
    │   │   ├── installer/                            ** NEW subpackage matching core/cli/installer/
    │   │   │   ├── __init__.py                       **
    │   │   │   ├── test_settings_merge.py            ** NEW: 17 merge-algorithm tests
    │   │   │   ├── test_api_key_prompt.py            ** NEW: 12 prompt tests
    │   │   │   ├── test_venv.py                      ** NEW: venv creation + pip install tests
    │   │   │   └── test_legacy_migration.py          ** NEW: legacy .env migration tests
    │   │   └── test_update_main.py                   (* extended: no-silent-upgrade assertions)
    │   ├── infra/
    │   │   ├── test_atomic_write.py
    │   │   ├── test_checksums.py                     ** NEW
    │   │   ├── test_client.py                        (* updated: imports moved client from new location)
    │   │   ├── test_config.py                        (* extended: backend config field tests)
    │   │   ├── test_cost.py
    │   │   ├── test_errors.py                        (* extended: BackendUnavailableError + APIError ctx)
    │   │   ├── test_filelock.py
    │   │   ├── test_mime.py
    │   │   ├── test_sanitize.py
    │   │   └── test_timeouts.py
    │   ├── routing/{test_registry,test_router,test_tool_state}.py
    │   └── state/{test_file_state,test_identity,test_session_state,test_store_state}.py
    ├── transport/                                    ** NEW PACKAGE **
    │   ├── __init__.py                               **
    │   ├── test_base.py                              **
    │   ├── test_coordinator.py                       **
    │   ├── test_facade.py                            **
    │   ├── test_normalize.py                         **
    │   ├── test_policy.py                            **
    │   ├── test_raw_http_transport.py                **
    │   ├── sdk/
    │   │   ├── __init__.py                           **
    │   │   ├── test_client_factory.py                **
    │   │   └── test_transport.py                     **
    │   └── fixtures/                                 ** captured SDK model_dump() outputs as JSON
    │       ├── __init__.py                           **
    │       ├── generate_content_text.json            **
    │       ├── generate_content_multipart.json       **
    │       ├── generate_content_inline_image.json    **
    │       ├── generate_content_tool_calls.json      **
    │       ├── stream_chunk.json                     **
    │       ├── file_upload.json                      **
    │       ├── safety_block.json                     **
    │       └── usage_metadata.json                   **
    ├── fixtures/                                     (UNCHANGED)
    │   ├── __init__.py
    │   ├── v1/__init__.py
    │   └── v1beta/__init__.py
    ├── integration/                                  (UNCHANGED — all 20 live smoke tests stay)
    │   └── test_*_live.py (×20)
```

After install on the user machine, the runtime layout is:

```
~/.claude/
├── settings.json                (user-global, env block holds GEMINI_* keys — see auth section)
└── skills/gemini/
    ├── .venv/                   ** NEW ** skill-local virtual environment
    │   ├── bin/python           ** the interpreter SKILL.md invokes
    │   ├── bin/pip
    │   └── lib/python3.X/site-packages/google/genai/...
    ├── setup/
    │   └── requirements.txt     ** NEW ** copied from repo, pins google-genai (read by install_main.py)
    ├── SKILL.md
    ├── VERSION
    ├── core/...                 (mirrors repo core/, including new core/transport/)
    ├── adapters/...
    ├── reference/...
    ├── registry/...
    ├── scripts/gemini_run.py
    └── setup/update.py
    (NOTE: no .env file here — env vars live in ~/.claude/settings.json instead)
```

## File-by-file plan

### Version pinning policy

`google-genai` is **pinned exactly** in `setup/requirements.txt` (e.g. `google-genai==1.x.y`). Three guarantees:

1. **Reproducible installs**: every fresh `setup/install.py` produces an identical `.venv`.
2. **No silent upgrades**: `update.py` re-runs `pip install -r setup/requirements.txt` *without* `--upgrade`, so pip is a no-op when the pinned version is already present and only acts when the user explicitly bumps the pin.
3. **Manual upgrade path**: to upgrade, the user (or a maintainer in a PR) edits `setup/requirements.txt`, bumps the version, runs `setup/install.py`, and the new version replaces the old one. Tests + the live integration suite must pass under the new pin before the PR merges.

The pinned version is also asserted at runtime in the health check: `health` reports both the pinned version (read from `setup/requirements.txt`) and the installed version (read from `google.genai.__version__`) and warns if they drift — that drift is the signal someone bypassed the install flow.

### New files

| File | Purpose |
|---|---|
| `core/transport/__init__.py` | Public facade. Exports `api_call`, `stream_generate_content`, `upload_file`. Each function instantiates (or looks up a cached) `TransportCoordinator` and delegates. |
| `core/transport/base.py` | `Transport` `Protocol` with `api_call`, `stream_generate_content`, `upload_file`, `name` (str). Plus `TransportResult` / `TransportFailure` dataclasses used by the coordinator. |
| `core/transport/coordinator.py` | `TransportCoordinator(primary, fallback, policy)`. Built from `Config.from_config()` which reads the two priority flags. Fallback is always available (no enable flag). Method `execute(op_name, call)` — runs primary, catches failures, consults `policy.is_fallback_eligible`, runs fallback or raises `APIError` with combined context. Writes a per-process "last backend used" marker for live-test verification. |
| `core/transport/policy.py` | `is_fallback_eligible(exc) -> bool` decision table (matches the eligibility rules above). Pure function, fully unit-testable. |
| `core/transport/normalize.py` | `sdk_response_to_rest_envelope(sdk_response) -> dict` — serializes `google.genai.types.GenerateContentResponse` and friends into the REST envelope shape `{candidates, usageMetadata, promptFeedback}`. Mirrors for streaming chunks and file objects. |
| `core/transport/sdk/client_factory.py` | `get_client() -> genai.Client` — lazy singleton, calls `resolve_key()` with no arguments (relies on settings.json → process env), passes `api_key=...` to `genai.Client`. Raises `BackendUnavailableError` if `google.genai` import fails. |
| `core/transport/sdk/transport.py` | `SdkTransport` implements `Transport`. Maps: `api_call("models/X:generateContent", body)` → `client.models.generate_content(model=X, **kwargs_from_body)`; `stream_generate_content` → `client.models.generate_content_stream`; `upload_file` → `client.files.upload`. Normalizes every response via `normalize.py`. |
| `core/transport/raw_http/transport.py` | `RawHttpTransport` implements `Transport`. Thin class that delegates to the moved `core/transport/raw_http/client.py` functions. No behavior change. |
| `tests/transport/test_coordinator.py` | Primary success, primary fail → fallback success, both fail, fallback disabled, non-eligible error (e.g. `AuthError`) skips fallback. |
| `tests/transport/test_policy.py` | Table-driven eligibility tests for every error class. |
| `tests/transport/test_normalize.py` | SDK response fixtures → expected REST envelope dicts. Covers text, multipart, inline media, tool calls, streaming chunks, file upload. |
| `tests/transport/test_sdk_transport.py` | Mocks `genai.Client`; asserts request shape translation and response normalization. No network. |
| `tests/transport/test_raw_http_transport.py` | Thin smoke test — behavior already covered by existing `tests/core/infra/test_client.py`. |
| `tests/transport/test_facade.py` | `api_call` / `stream_generate_content` / `upload_file` call the coordinator with current config. |

### Modified files

| File | Change |
|---|---|
| `core/infra/client.py` | Rewrite as a 5-line shim: `from core.transport import api_call, stream_generate_content, upload_file`. The `_SKILL_ROOT` constant is **deleted** entirely (no longer used anywhere — auth now reads from process env via `resolve_key()` without an `env_dir`). Existing tests that asserted `env_dir=_SKILL_ROOT` are rewritten to assert `resolve_key()` is called with no arguments. |
| `core/transport/raw_http/client.py` | **Moved** from `core/infra/client.py`, content unchanged EXCEPT `_SKILL_ROOT` and the `env_dir=_SKILL_ROOT` argument to `resolve_key()` are deleted. All retry, SSE, multipart logic preserved verbatim. |
| `core/infra/config.py` | Add fields to `Config` dataclass: `is_sdk_priority: bool = True`, `is_rawhttp_priority: bool = False`. Validate that exactly one is true. Expose computed `primary_backend` / `fallback_backend` properties for backward compat with the rest of the plan's pseudocode. |
| `core/infra/errors.py` | Extend `APIError` to optionally carry `primary_backend`, `fallback_backend`, `primary_error`, `fallback_error` for the "both failed" case. **Note: `BackendUnavailableError` is NOT added here — it lives in `core/transport/base.py` because it's transport-specific (layering: `core/infra/` must not depend on transport semantics).** `core/infra/errors.py` may import from `core/transport/base.py` only for the cross-package re-export at the package boundary, never the reverse. |
| `core/transport/base.py` | Add `BackendUnavailableError(GeminiSkillError)` here (raised when a backend can't even start — e.g. SDK not importable, or a capability isn't supported by either backend). It inherits from the existing `core/infra/errors.GeminiSkillError` so callers can catch the base class without knowing about transport. |
| `core/cli/health_main.py` | Report: GEMINI_IS_SDK_PRIORITY value, GEMINI_IS_RAWHTTP_PRIORITY value, computed primary/fallback, SDK importable yes/no, venv path, `google-genai` version. |
| `SKILL.md` | Invocation line changes from `python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py"` to `"${CLAUDE_SKILL_DIR}/.venv/bin/python" "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py"`. Windows handling in `scripts/gemini_run.py` bootstrap if needed. |
| `scripts/gemini_run.py` | Minimal addition: detect whether it's running under the skill-local venv; if not and `.venv/bin/python` exists, re-exec under it. Keeps the launcher idempotent for users who call `python3 scripts/gemini_run.py` directly. |
| `core/cli/install_main.py` | Add steps after copying files: (1) create `~/.claude/skills/gemini/.venv` via `venv.EnvBuilder(with_pip=True, upgrade_deps=True)`, (2) **install `google-genai` into that venv** by invoking `~/.claude/skills/gemini/.venv/bin/python -m pip install -r ~/.claude/skills/gemini/setup/requirements.txt` as a subprocess — using the venv's own interpreter is equivalent to activating it for pip purposes and guarantees the package lands inside `.venv/lib/.../site-packages` (NOT system Python), (3) verify by running `<venv-python> -c "import google.genai, sys; assert '.venv' in sys.executable; print(google.genai.__version__)"` — this asserts both that the import works AND that it resolved from inside the venv, (4) print the venv python path and the installed SDK version, (5) on `update`, detect existing `.venv`, skip recreation, and **re-run `pip install -r setup/requirements.txt` (NOT `--upgrade`)** so the pinned version is enforced and the SDK is never silently upgraded. Failure path: if venv creation or `pip install` fails, warn loudly, set `GEMINI_IS_SDK_PRIORITY=false` and `GEMINI_IS_RAWHTTP_PRIORITY=true` in the installer's settings.json merge so the skill still works via raw HTTP only, and tell the user how to re-run install once the venv issue is resolved. |
| `setup/requirements.txt` (NEW, repo root) | Pinned dependencies file copied into the install directory by `install_main.py`. Contents: `google-genai==X.Y.Z` (pin the exact version chosen at refactor time — pick the latest stable at implementation moment). Comment header explains: "This file pins runtime dependencies for the gemini-skill venv. Do not loosen pins. To upgrade, bump the version explicitly and run `setup/install.py`." Pip will refuse to silently change versions because the pin is exact. |
| `setup/install.py` | No logic change — still calls `install_main.py`. |
| `tests/core/infra/test_client.py` | Update import path — the three functions now live in `core/transport/raw_http/client.py`. **Rewrite** the existing `_SKILL_ROOT` / `env_dir=_SKILL_ROOT` assertions to assert `resolve_key` is called with NO arguments. |
| `tests/core/cli/test_install_main.py` (if exists, else new) | Assert venv is created, `google-genai` is installed (mock `subprocess.run`), update path preserves venv. |

### Adapters: **zero file-level changes**

Every adapter's `from core.infra.client import api_call, ...` keeps resolving via the shim. This is the "preserve working raw HTTP code" guarantee. Only if `core.transport` proves stable do we optionally migrate adapter imports to `from core.transport import ...` later — out of scope for this refactor.

## Key implementation notes

**SDK request translation.** The current raw HTTP `body` dicts follow the REST JSON schema: `{contents, generationConfig, tools, systemInstruction, ...}`. The SDK's `client.models.generate_content` accepts `model`, `contents`, `config` (a `GenerateContentConfig` object). `SdkTransport.api_call` parses the endpoint path (`models/{model}:{method}`) to pick the SDK method, then passes `contents` through unchanged and maps `generationConfig`→`config=GenerateContentConfig(**body["generationConfig"])`. `tools`, `systemInstruction`, `safetySettings` map 1:1. Adapters stay unaware.

**SDK response normalization.** `normalize.sdk_response_to_rest_envelope` reconstructs the REST shape. Since adapters call `extract_text(response)` which reads `response["candidates"][0]["content"]["parts"][i]["text"]`, the SDK's `.candidates[0].content.parts[0].text` can be serialized back with `response.model_dump(exclude_none=True)` — `google-genai` uses pydantic, so `model_dump()` gives us the REST-shaped dict for free. This is the key simplification that makes the SDK backend cheap.

**Streaming.** SDK's `generate_content_stream` yields `GenerateContentResponse` chunks. Wrap with a generator that calls `model_dump()` on each — adapters/generation/streaming.py iterates the same shape it does today.

**File upload.** SDK `client.files.upload(file=path, config={"mime_type": ..., "display_name": ...})` returns a `File` object — `model_dump()` again gives the REST envelope.

**Lazy SDK import.** `core/transport/sdk/client_factory.py` must `import google.genai` inside the function, not at module top, so `RawHttpTransport` keeps working if SDK isn't installed. `ImportError` → raise `BackendUnavailableError` → coordinator treats as fallback-eligible → raw HTTP runs.

**Coordinator caching.** `TransportCoordinator` is built once per process and stashed on a module-level `_COORDINATOR` in `core/transport/__init__.py`. Config is read at first use; the install flow is out-of-process so this is safe.

## Feature parity audit: SDK vs raw HTTP

**Source of truth (added per user request):**
- Repo: https://github.com/googleapis/python-genai
- Docs site: https://googleapis.github.io/python-genai/
- Context7 library ID: `/googleapis/python-genai`
- PyPI: https://pypi.org/project/google-genai/
- Pinned version (latest stable as of plan time): `google-genai==1.33.0` — implementer must confirm and pin in `setup/requirements.txt`. Bumping this version requires updating this audit.

These URLs MUST appear in [docs/architecture.md](docs/architecture.md) and [docs/contributing.md](docs/contributing.md) as the canonical reference for what the SDK can and cannot do.

This audit catalogs **every** endpoint and feature the raw HTTP backend currently exercises (derived from grepping `api_call`/`stream_generate_content`/`upload_file` in all 19 adapters), cross-referenced with the live Context7 docs for `/googleapis/python-genai`. Each row records: the raw HTTP endpoint, the `google-genai` SDK equivalent, and a parity verdict.

Verdicts marked **✅ Confirmed** are backed by Context7 docs evidence retrieved while writing this plan. Verdicts marked **⚠️ Verify at impl time** are handled at runtime via the **try-SDK-then-auto-fallback** strategy chosen by the user (see "User decisions" section below) — the coordinator attempts the SDK call and treats `AttributeError`/`ImportError`/`TypeError` as fallback-eligible, routing to raw HTTP without manual config.

### Endpoint parity table

| # | Raw HTTP call | Adapter | SDK equivalent | Verdict |
|---|---|---|---|---|
| 1 | `POST models/{m}:generateContent` (text) | text.py | `client.models.generate_content(model, contents, config)` | ✅ Confirmed |
| 2 | `POST models/{m}:generateContent` w/ `responseSchema` | structured.py | `GenerateContentConfig(response_schema=..., response_mime_type='application/json')` | ✅ Confirmed |
| 3 | `POST models/{m}:generateContent` w/ `inlineData` parts | multimodal.py | `contents=[uploaded_file, text]` or `Part.from_bytes(data, mime_type)` | ✅ Confirmed |
| 4 | `POST models/{m}:streamGenerateContent` (SSE) | streaming.py | `client.models.generate_content_stream(model, contents, config)` | ✅ Confirmed (true streaming, upgrade over current buffered SSE) |
| 5 | `POST models/{m}:countTokens` | token_count.py | `client.models.count_tokens(model, contents)` | ✅ Confirmed |
| 6 | `POST models/{m}:embedContent` | embeddings.py | `client.models.embed_content(model, contents, config=EmbedContentConfig(...))` | ✅ Confirmed (also supports `output_dimensionality` natively) |
| 7 | `POST models/{m}:generateContent` w/ functionDeclarations | function_calling.py | `tools=[Tool(function_declarations=[...])]` | ✅ Confirmed |
| 8 | `POST models/{m}:generateContent` w/ codeExecution | code_exec.py | `tools=[Tool(code_execution=ToolCodeExecution())]` | ✅ Confirmed |
| 9 | `POST models/{m}:generateContent` w/ googleSearch | search.py | `tools=[Tool(google_search=GoogleSearch())]` (Gemini 2.x+); 1.5 uses `google_search_retrieval` | ✅ Confirmed |
| 10 | `POST models/{m}:generateContent` w/ googleMaps | maps.py | ⚠️ Auto-fallback at runtime — Context7 docs do not show a `GoogleMaps` tool class. SDK transport will attempt it; on `AttributeError`/`TypeError` the coordinator routes via raw HTTP and caches the gap. |
| 11 | `POST models/{m}:generateContent` w/ `responseModalities=["IMAGE"]` (Gemini-native image gen, e.g. `gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview` Nano Banana 2) | image_gen.py | `client.models.generate_content(model, contents, config=GenerateContentConfig(response_modalities=['IMAGE']))`; iterate `response.parts`, each part has `.inline_data` and `.as_image()` helper | ✅ Confirmed |
| 11b | (NEW capability path) Imagen text-to-image | n/a yet | `client.models.generate_images(model='imagen-3.0-generate-002', prompt, config=GenerateImagesConfig(...))` | ✅ Confirmed — **separate SDK surface**, not currently in skill (see "New SDK features" below) |
| 12 | Veo video gen — `POST models/{m}:predictLongRunning` + ops polling | video_gen.py | `client.models.generate_videos(model='veo-2.0-generate-001', prompt, image, config=GenerateVideosConfig(...))` returns Operation; poll via `client.operations.get(operation)` | ✅ Confirmed |
| 13 | Lyria music gen | music_gen.py | ⚠️ Auto-fallback at runtime — Context7 docs do not show a music_gen surface. SDK transport will attempt it; on `AttributeError` the coordinator routes via raw HTTP and caches the gap. |
| 14 | Computer Use tool | computer_use.py | ⚠️ Auto-fallback at runtime — Context7 docs do not show a `ComputerUse` tool class. SDK transport will attempt it; on `AttributeError`/`TypeError` the coordinator routes via raw HTTP and caches the gap. |
| 15 | `POST interactions` + `GET interactions/{id}` (Deep Research) | deep_research.py | **REVISED** — Context7 docs confirm `client.interactions.create(input, agent='deep-research-pro-preview-12-2025', background=True)` and `client.interactions.get(id=...)` exist in the SDK | ✅ Confirmed (was previously assumed raw-HTTP-only — flip to SDK-supported) |
| 16 | `POST /upload/v1beta/files` multipart upload | files.py upload | `client.files.upload(file=path, config={'mime_type': ..., 'display_name': ...})` | ✅ Confirmed |
| 17 | `GET files` (list) | files.py list | `client.files.list()` | ✅ Confirmed |
| 18 | `GET files/{name}` | files.py get | `client.files.get(name=name)` | ✅ Confirmed |
| 19 | `DELETE files/{name}` | files.py delete | `client.files.delete(name=name)` | ✅ Confirmed |
| 19b | (NEW) File download | n/a yet | `client.files.download(file=uploaded_file)` + `uploaded_file.save(path)` | ✅ Confirmed — **not currently in skill** |
| 20 | `POST cachedContents` (create) | cache.py create | `client.caches.create(model, config)` | ✅ Confirmed |
| 21 | `GET cachedContents` (list) | cache.py list | `client.caches.list()` | ✅ Confirmed |
| 22 | `GET cachedContents/{name}` | cache.py get | `client.caches.get(name=name)` | ✅ Confirmed |
| 23 | `DELETE cachedContents/{name}` | cache.py delete | `client.caches.delete(name=name)` | ✅ Confirmed |
| 24 | `POST batchJobs` create | batch.py | `client.batches.create(model, src, config)` | ✅ Confirmed |
| 25 | `GET batchJobs` list | batch.py | `client.batches.list()` | ✅ Confirmed |
| 26 | `GET batchJobs/{name}` | batch.py | `client.batches.get(name=name)` | ✅ Confirmed |
| 27 | `POST batchJobs/{name}:cancel` | batch.py | `client.batches.cancel(name=name)` | ✅ Confirmed |
| 28-32 | `fileSearchStores` create/upload/query/list/delete | file_search.py | ⚠️ Auto-fallback at runtime — Context7 docs do not show `client.file_search_stores`. SDK transport will attempt it; on `AttributeError` the coordinator routes via raw HTTP and caches the gap. |
| 33 | `GET operations/{name}` (long-running poll) | file_search.py, video_gen.py | `client.operations.get(operation)` | ✅ Confirmed |

### Cross-cutting features that must reach parity

Beyond endpoints, the SDK transport must preserve every cross-cutting behavior the raw HTTP client provides:

| Feature | Raw HTTP behavior | SDK transport requirement |
|---|---|---|
| **Auth via header** | `x-goog-api-key` header, never URL-embedded | Pass `api_key=resolve_key()` to `genai.Client(api_key=...)`. Verify the SDK uses headers, not URL params (it does as of recent versions, but the test must assert no key leaks into logged URLs). |
| **Env-var loading** | `resolve_key()` reads `GEMINI_API_KEY` from process env (set by Claude Code from settings.json). | Identical — the SDK client factory uses the same call site. Local-dev `.env` fallback is opt-in via `env_dir=` from `scripts/gemini_run.py`. |
| **Retry: 429/5xx exponential backoff (3 retries)** | Custom `_execute_with_retry` | The SDK has built-in retry, but the policy may differ. SDK transport must either (a) configure the SDK's retry to match (3 retries, exponential, 429+5xx, exclude 504-on-POST), or (b) wrap each SDK call in our own retry loop using the existing `classify_retry` logic from [core/infra/errors.py](core/infra/errors.py). **Decision: option (b)** — wrap, so retry policy stays centralized and identical across both backends. |
| **504 GET single-retry, 504 POST no-retry** | Hardcoded in `_execute_with_retry` | Same wrapper handles it. |
| **`urllib.error.URLError` / `socket.timeout` retry** | Network errors retry | Map SDK's `google.api_core.exceptions.ServiceUnavailable`, `DeadlineExceeded`, `Aborted` to the same retry path. |
| **macOS SSL cert error → actionable message** | `client.py` detects `ssl.SSLCertVerificationError` and prints brew/cert install hints | SDK transport catches the same exception class, raises the same `APIError` with the same hint message. Same helper function, factored out into `core/transport/raw_http/client.py` and imported by SDK transport. |
| **Mime type CRLF guard (`_validate_mime_type`)** | Regex check before multipart upload | Apply the same validation in `SdkTransport.upload_file` *before* calling `client.files.upload` — defense in depth, doesn't trust the SDK to sanitize. |
| **Error message extraction** | `_extract_error_message` parses Gemini error JSON | SDK exceptions already carry parsed messages; SDK transport maps `google.api_core.exceptions.GoogleAPIError.message` into `APIError(message, status_code)`. Resulting `str(APIError)` must be byte-equivalent across backends for the same upstream error so adapter tests aren't backend-aware. |
| **Timeout enforcement** | `timeout=30` (default) / `timeout=120` (upload) per call | Pass `request_options={'timeout': N}` (or the SDK's equivalent kwarg in the installed version) to every SDK call. Verify the timeout is enforced — write a test that mocks a slow response and asserts `APIError` is raised within the bound. |
| **API key never appears in logs/errors** | Sanitization in `core/infra/sanitize.py` | SDK transport must not log raw URLs or request headers. Add a regression test that captures stderr/logging during a forced failure and asserts the key string is absent. |
| **Streaming SSE → adapter loop** | `stream_generate_content` yields parsed dicts | `SdkTransport.stream_generate_content` wraps the SDK's streaming generator and `model_dump()`s each chunk into the REST envelope. The adapter ([adapters/generation/streaming.py](adapters/generation/streaming.py)) must iterate without changes — backed by a parity test that asserts identical chunk dicts from both backends for a recorded fixture. |
| **`responseSchema` / `responseMimeType` / `responseModalities`** | Passed through `generationConfig` dict | SDK uses `response_schema`, `response_mime_type`, `response_modalities` snake_case fields on `GenerateContentConfig`. SDK transport's request translator does the dict→config conversion; covered by `test_sdk_transport.py`. |
| **`systemInstruction`** | Top-level body field | Maps to `config.system_instruction` — translator handles it. |
| **`safetySettings`** | Top-level body field | Maps to `config.safety_settings=[SafetySetting(...)]` — translator handles it. |
| **Cached content reference** | Body field `cachedContent: "cachedContents/{id}"` | Maps to `config.cached_content="cachedContents/{id}"` — translator handles it. |
| **Cost tracking hooks** | `core/infra/cost.py` defined but not wired (per audit) | SDK and raw HTTP must both feed `usageMetadata` into cost tracking the same way once it's wired. SDK responses carry `usage_metadata` which `model_dump()` serializes as `usageMetadata` (snake→camel) — verify in normalize tests. |
| **Dispatch policy gates (`--execute`, `--i-understand-privacy`)** | Enforced in `core/cli/dispatch.py`, before transport | Unchanged — these run before the coordinator is reached, both backends. |
| **Dry-run mode** | Adapters short-circuit before calling `api_call` | Unchanged — the transport layer is never reached in dry-run mode. |

### New SDK features NOT currently in the skill (candidates to add)

The Context7 audit surfaced several `google-genai` capabilities that the skill does **not** currently expose. These are net-new features the SDK refactor enables effectively for free (because we'll have a working SDK client). They are listed here for the user to pick from — the plan does not assume any of them ship with this refactor unless explicitly approved.

1. **Live API (`client.aio.live.connect`)** — bidirectional realtime audio/video streaming with Gemini Live models (`gemini-live-2.5-flash-preview`). Async-only. Would be a new adapter `adapters/generation/live.py` plus a new capability entry. Requires the skill to grow an async transport surface; non-trivial but high-impact for voice/agent use cases.

2. **Imagen text-to-image (`client.models.generate_images`)** — distinct from Gemini-native image gen. Uses Imagen 3 models (`imagen-3.0-generate-002`). Higher photoreal quality than Gemini-native. Would be a new sub-capability under image_gen or a new `imagen_gen` capability with its own adapter.

3. **Gemini 3 Pro Image with `image_config`** — `gemini-3-pro-image-preview` with explicit `aspect_ratio` ("16:9", "9:16", "1:1", etc.) and `image_size` ("1K", "2K", "4K"). Currently the skill's image_gen adapter doesn't expose these knobs. Would be a flag addition to the existing `image_gen` adapter.

4. **Async client (`client.aio`)** — every method has an async twin under `client.aio`. Could enable a new `--parallel` flag on adapters that issue many calls (batch, embeddings of many texts), or unlock the Live API. Would require the skill to gain an async dispatch path (currently fully sync).

5. **File download (`client.files.download`)** — round-trip files uploaded earlier. Would be a new subcommand `files download <name> <out-path>` on the existing `files` adapter.

6. **Grounding metadata extraction** — the SDK exposes `response.candidates[0].grounding_metadata` with `web_search_queries`, `grounding_chunks`, `search_entry_point.rendered_content`. The skill's `search` adapter currently prints text only; could optionally emit the grounding metadata as JSON. Small enhancement.

These are listed in priority-of-impact order (top = most users would benefit). The user will be prompted (via AskUserQuestion below) to pick which to include in this refactor PR vs defer to follow-up PRs.

## User decisions (recorded 2026-04-13)

The user reviewed the SDK feature gap and made the following decisions. All "New SDK features" listed above are **in scope** for this refactor:

- ✅ **Group A (small):** Imagen text-to-image, Gemini 3 Pro Image config flags, File download subcommand, Search grounding metadata JSON — all approved.
- ✅ **Group B (large):** Live API, Async dispatch — approved. **Fine-tuning and Vertex AI mode REMOVED** per follow-up user decision (skill is API-key-only; no Vertex/ADC support).
- ✅ **Uncertain capabilities** (`maps`, `music_gen`, `computer_use`, `file_search`): **Try SDK with auto-fallback**. Coordinator attempts SDK first; `ImportError`/`AttributeError`/`TypeError` raised from missing tool classes is **fallback-eligible** and routes to raw HTTP automatically. No registry field needed — the coordinator detects the gap at runtime per call and caches it per-process.
- ✅ **Pin:** `google-genai==1.33.0` in `setup/requirements.txt`.

These decisions update the plan as follows.

### Architectural revision: explicit capability registry replaces fallback heuristics

**Per architect review.** The earlier plan relied on `_looks_like_genai_attr_miss` string-matching `"Client"` / `"types"` / `"google.genai"` in `AttributeError` messages to decide if an exception meant "SDK doesn't expose this surface". That's too loose — `"Client"` is an extremely common substring and would silently swallow legitimate bugs that happen to mention any class with `"Client"` in its name.

**New approach: explicit capability registration on `SdkTransport`.**

```python
# core/transport/sdk/transport.py
class SdkTransport:
    name: Literal["sdk"] = "sdk"

    # Capabilities the SDK is KNOWN to support at the pinned version (1.33.0).
    # Updated by the implementer when bumping the pin and re-running the parity audit.
    # Keys match the dispatch command names in core/cli/dispatch.py::ALLOWED_COMMANDS.
    _SUPPORTED_CAPABILITIES: ClassVar[frozenset[str]] = frozenset({
        "text", "structured", "multimodal", "streaming",
        "embed", "token_count",
        "function_calling", "code_exec", "search",
        "image_gen", "video_gen",
        "files", "cache", "batch",
        "deep_research",  # client.interactions
        "imagen",         # client.models.generate_images (Phase 7)
        "live",           # client.aio.live (Phase 7, async only)
        # Capabilities NOT in this set fall through to raw HTTP without an SDK probe:
        # - maps             (no GoogleMaps tool class in 1.33.0 per Context7)
        # - music_gen        (no Lyria surface in 1.33.0)
        # - computer_use     (no ComputerUse tool class in 1.33.0)
        # - file_search      (no client.file_search_stores in 1.33.0)
    })

    def supports(self, capability: str) -> bool:
        """Return True iff the SDK is known to handle this capability at the pinned version."""
        return capability in self._SUPPORTED_CAPABILITIES
```

The `TransportCoordinator` consults `primary.supports(capability)` BEFORE attempting the SDK call. If `False`, the call goes straight to raw HTTP without any try/except — deterministic, no false positives, no log noise. If `True`, the coordinator dispatches to the SDK; any exception is interpreted via the typed-error policy below.

**Typed SDK error handling (replaces AttributeError heuristics).**

`SdkTransport` wraps every SDK call in a context manager that catches `google.genai.errors.*` and `google.api_core.exceptions.*` (when present), mapping each to our internal exception classes:

```python
# core/transport/sdk/transport.py
@contextmanager
def _wrap_sdk_errors(capability: str) -> Iterator[None]:
    """Map google.genai.errors.* and google.api_core.exceptions.* into our error classes.

    The coordinator's policy decides fallback eligibility based on OUR error classes,
    NOT on raw SDK exceptions. This keeps policy.py free of SDK-specific knowledge and
    eliminates string-matching fragility.
    """
    try:
        yield
    except ImportError as exc:
        # Lazy import inside _wrap_sdk_errors raised — SDK truly missing.
        raise BackendUnavailableError(f"google-genai not importable: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — we re-raise everything after mapping
        # Try the typed google.genai.errors hierarchy first.
        try:
            from google.genai import errors as genai_errors  # lazy
            if isinstance(exc, genai_errors.ClientError):
                # 4xx — never eligible for fallback (request was malformed/auth/permission)
                raise APIError(str(exc), status_code=getattr(exc, "code", 400)) from exc
            if isinstance(exc, genai_errors.ServerError):
                # 5xx — eligible
                raise APIError(str(exc), status_code=getattr(exc, "code", 500)) from exc
            if isinstance(exc, genai_errors.APIError):
                raise APIError(str(exc), status_code=getattr(exc, "code", None)) from exc
        except ImportError:
            pass  # google.genai.errors not present in this SDK version
        # Fall back to google.api_core if the SDK still re-raises that.
        try:
            from google.api_core import exceptions as gapic_exc  # lazy
            if isinstance(exc, gapic_exc.PermissionDenied):
                raise AuthError(str(exc)) from exc
            if isinstance(exc, gapic_exc.ResourceExhausted):
                raise APIError(str(exc), status_code=429) from exc
            if isinstance(exc, gapic_exc.DeadlineExceeded):
                raise APIError(str(exc), status_code=504) from exc
            if isinstance(exc, gapic_exc.GoogleAPIError):
                raise APIError(str(exc), status_code=getattr(exc, "code", None)) from exc
        except ImportError:
            pass
        # Anything we haven't mapped is a programmer bug — re-raise unmodified.
        raise
```

**Updated `core/transport/policy.py`**: the `_looks_like_genai_attr_miss` and `_is_sdk_tool_kwarg_error` heuristics are **removed**. Policy now only consults: `BackendUnavailableError` (eligible), `APIError` with `status_code` (eligible iff 429 or 5xx), `URLError`/`socket.timeout`/`ConnectionError` (eligible), `AuthError`/`ValueError`/`TypeError`/`AssertionError` (NOT eligible), `CostLimitError` (NOT eligible). Pure type-based decisions, zero string matching.

**Coordinator change**: the `_execute` loop becomes:
```python
def _execute(self, capability: str, op_name: str, call: Callable[[Transport], T]) -> T:
    if not self._primary.supports(capability):
        # Deterministic route to fallback. No probe, no log noise — this is the documented
        # behavior for capabilities the primary doesn't claim to support.
        if self._fallback is None:
            raise BackendUnavailableError(
                f"Capability '{capability}' is not supported by primary backend "
                f"'{self._primary.name}' and no fallback is configured."
            )
        return self._call_with_marker(self._fallback, call, capability)
    try:
        return self._call_with_marker(self._primary, call, capability)
    except BaseException as primary_exc:
        if not is_fallback_eligible(primary_exc):
            raise
        if self._fallback is None:
            raise APIError(
                message=f"Primary {self._primary.name} failed and no fallback configured: {primary_exc}",
                primary_backend=self._primary.name,
                primary_error=str(primary_exc),
            ) from primary_exc
        # Structured log so silent SDK→raw_http degradation is visible in production.
        logger.warning(
            "transport_fallback primary=%s fallback=%s capability=%s reason=%s",
            self._primary.name, self._fallback.name, capability, type(primary_exc).__name__,
        )
        try:
            return self._call_with_marker(self._fallback, call, capability)
        except BaseException as fallback_exc:
            raise APIError(
                message=(f"Both backends failed. Primary {self._primary.name}: {primary_exc}. "
                         f"Fallback {self._fallback.name}: {fallback_exc}."),
                primary_backend=self._primary.name,
                fallback_backend=self._fallback.name,
                primary_error=str(primary_exc),
                fallback_error=str(fallback_exc),
            ) from fallback_exc
```

The `_MissingSurfaceCache` is **deleted entirely** — no longer needed. Capability support is statically declared, not discovered at runtime.

### Eligibility rule update (auto-fallback for missing SDK surfaces)

`core/transport/policy.py::is_fallback_eligible(exc)` now treats these additional exception types as fallback-eligible (they indicate "SDK doesn't expose this surface"):

- `ImportError` / `ModuleNotFoundError` for `google.genai.types.<ToolClass>`
- `AttributeError` raised when the SDK transport tries `client.models.<method>` and the method doesn't exist (e.g. `client.file_search_stores`)
- `AttributeError` raised when constructing a `Tool(<unknown_kwarg>=...)` (e.g. `Tool(google_maps=GoogleMaps())` when the SDK lacks that field)
- `TypeError` raised when a Tool/Config class rejects a kwarg the raw HTTP body included

These joins exist alongside (not replacing) the original transport-class fallback rules. The decision table grows but the structure is unchanged.

The fallback path **logs** a one-line warning the first time per process per (capability, missing-attribute) tuple so the maintainer sees which capabilities are silently routing to raw HTTP — that's the signal to flip them to first-class SDK once the SDK adds the surface. Logged to stderr through [core/infra/sanitize.py](core/infra/sanitize.py) so the API key is never accidentally included.

### New adapters and adapter extensions in scope

| Change | Files | Notes |
|---|---|---|
| **NEW adapter** `adapters/generation/imagen.py` | + `tests/adapters/generation/test_imagen.py` + `reference/imagen.md` + `tests/integration/test_imagen_live.py` | Wraps `client.models.generate_images` (Imagen 3). New capability `imagen_gen` registered in [registry/capabilities.json](registry/capabilities.json) with mutating=true. |
| **NEW adapter** `adapters/generation/live.py` | + `tests/adapters/generation/test_live.py` + `reference/live.md` + `tests/integration/test_live_live.py` | Async-only, uses `client.aio.live.connect`. Triggers async dispatch path. New capability `live` registered. |
| **EXTENSION** `adapters/media/image_gen.py` | Modified + tests | Add `--aspect-ratio` and `--image-size` flags. Pass through `GenerateContentConfig.image_config` for Gemini 3 Pro Image models. SDK-only; raw HTTP backend rejects with a clear error if the user passes the flag while forced to raw HTTP. |
| **EXTENSION** `adapters/data/files.py` | Modified + tests | Add `files download <name> <out-path>` subcommand. SDK calls `client.files.download(file)` then `file.save(out_path)`; raw HTTP path uses `GET <files/{name}>?alt=media`. |
| **EXTENSION** `adapters/tools/search.py` | Modified + tests | Add `--show-grounding` flag → emit grounding_metadata as JSON alongside the response text. Backend-agnostic: both backends populate `response.candidates[0].grounding_metadata` in the normalized envelope. |

### Async dispatch path

The skill is currently fully sync. To support Live API and a future `--parallel` flag without rewriting every adapter:

- `core/transport/base.py` — gain an `AsyncTransport` protocol with `async` versions of the three methods.
- `core/transport/sdk/transport.py` — gain `SdkAsyncTransport` wrapping `client.aio.*`.
- `core/transport/raw_http/transport.py` — does NOT implement async (raw HTTP stays sync; async-only capabilities like Live API are SDK-only and never fall back to raw HTTP).
- `core/transport/coordinator.py` — gain `async def execute_async(...)` mirror.
- `core/transport/__init__.py` — gain async facade exports `async_api_call`, `async_stream_generate_content`, `async_upload_file`.
- `core/cli/dispatch.py` — when an adapter declares `IS_ASYNC = True`, run it via `asyncio.run(adapter_module.run_async(**kwargs))`. Sync adapters take the existing path. No churn for the 19 existing sync adapters.
- A new `--parallel` flag is **not added in this PR** — it's a follow-up. The async path is built only as far as Live API requires.

### `setup/requirements.txt` content (pinned)

```
# Runtime dependencies for gemini-skill. Pinned exactly — do not loosen.
# To upgrade: edit this file, run setup/install.py, then run the live test suite
# (GEMINI_LIVE_TESTS=1 pytest tests/integration/) under both backends before merging.
# Reference: https://github.com/googleapis/python-genai
google-genai==1.33.0
# (Vertex AI mode is intentionally not supported — no google-auth pin.)
```

### Normalize layer hardening (architect review fix)

The earlier plan said `model_dump(exclude_none=True, by_alias=True)` would emit camelCase REST envelope shape "for free". Architect review flagged this as fragile — `google-genai` field aliases are inconsistent across nested types, and TypedDicts are not runtime-validated, so shape drift will go uncaught.

**Revised approach:**

1. **Explicit snake→camel mapping table** in `core/transport/normalize.py`:
   ```python
   # Field name translations between the SDK's pydantic models and the REST JSON envelope
   # the existing adapters expect. Generated from the pinned google-genai 1.33.0 by walking
   # the GeminiResponse TypedDict and inspecting each pydantic model's actual emitted field
   # names. Maintained by hand; CI test enforces no drift.
   _SNAKE_TO_CAMEL: Mapping[str, str] = {
       "usage_metadata": "usageMetadata",
       "prompt_feedback": "promptFeedback",
       "finish_reason": "finishReason",
       "safety_ratings": "safetyRatings",
       "grounding_metadata": "groundingMetadata",
       "function_call": "functionCall",
       "function_response": "functionResponse",
       "executable_code": "executableCode",
       "code_execution_result": "codeExecutionResult",
       "inline_data": "inlineData",
       "mime_type": "mimeType",
       "display_name": "displayName",
       "size_bytes": "sizeBytes",
       "prompt_token_count": "promptTokenCount",
       "candidates_token_count": "candidatesTokenCount",
       "total_token_count": "totalTokenCount",
       "block_reason": "blockReason",
       "web_search_queries": "webSearchQueries",
       "grounding_chunks": "groundingChunks",
       "search_entry_point": "searchEntryPoint",
       "rendered_content": "renderedContent",
       # ... extend as new fields are surfaced
   }
   ```

2. **`sdk_response_to_rest_envelope` does NOT trust `by_alias`**: it uses `model_dump(exclude_none=True)` (snake_case output) and recursively walks the dict applying `_SNAKE_TO_CAMEL` to every key. Extra safety: after translation, validate the result against the `GeminiResponse` TypedDict shape using a manual `_validate_envelope` that checks required nested keys are present.

3. **Recorded fixtures pinned to `google-genai==1.33.0`**: every fixture in `tests/transport/fixtures/` is a real `model_dump()` output captured against the pinned SDK version. The fixtures live in version control, and a separate test (`test_normalize_fixtures_against_pinned_sdk.py`) asserts that translating each fixture through `sdk_response_to_rest_envelope` produces the expected REST envelope. When bumping the SDK pin, this test fails first and the implementer regenerates fixtures via a `scripts/record_normalize_fixtures.py` helper that calls the real API once per fixture (gated on `GEMINI_LIVE_TESTS=1` and a separate `GEMINI_RECORD_FIXTURES=1` flag).

4. **Parity test uses `DeepDiff` with `ignore_order=True`**, NOT byte equality. `dict` ordering in `model_dump()` is not guaranteed identical across pydantic versions or backend types. `tests/transport/test_parity.py`:
   ```python
   from deepdiff import DeepDiff
   diff = DeepDiff(raw_http_response, sdk_response, ignore_order=True, exclude_regex_paths=[r"\['_meta'\]"])
   assert not diff, f"Backend response divergence: {diff}"
   ```
   Add `deepdiff` to `setup/requirements-dev.txt`.

5. **Runtime envelope validator** (debug aid, not a hot-path cost): when the env var `GEMINI_DEBUG_VALIDATE_ENVELOPE=1` is set, every normalized response is validated against the TypedDict shape by walking the keys. Mismatches log a warning. Off by default; on in CI for unit tests.

### Tests that enforce parity

- `tests/transport/test_parity.py` — for every endpoint in the table marked ✅ Confirmed, runs the same recorded request through `RawHttpTransport` (with mocked `urlopen`) and `SdkTransport` (with mocked `genai.Client`) and asserts the **normalized response dict is byte-identical**. Fixtures live in `tests/transport/fixtures/`.
- `tests/transport/test_auto_fallback.py` — coordinator with `primary_backend=sdk` and a forced `AttributeError` from the SDK transport (simulating a missing tool class) invokes raw HTTP via the fallback path. Asserts the per-process cache marks the capability as "SDK-unavailable" so subsequent calls skip the SDK probe.
- `tests/transport/test_async_coordinator.py` — async path mirrors of the sync coordinator tests.

## Code commenting requirement (override of default minimal-comments style)

**The user has explicitly opted out of the default "minimal comments" style for this project.** Every file written or substantially modified by this refactor must carry educational comments aimed at a reader who is **new to Python**. The goal is to help a learner understand both *what* the code does and *why* it exists, without having to context-switch to external docs.

Mandatory comment levels:

1. **File-level docstring** (every `.py` file). Top-of-file triple-quoted string explaining:
   - The file's purpose in one paragraph.
   - Where it fits in the larger architecture (e.g. "This is the SDK transport — one of two backends behind the TransportCoordinator. See core/transport/coordinator.py for how primary/fallback selection works.").
   - Any non-obvious assumptions or invariants.
   - For new learners: a one-sentence "What you'll learn from this file" hook (e.g. "This file demonstrates the Adapter pattern: same interface, two implementations.").

2. **Class-level docstring** (every `class`). Triple-quoted string immediately under the `class Foo:` line explaining:
   - What the class represents (the noun).
   - Its responsibilities (what it does).
   - Its collaborators (what it talks to).
   - For new learners: a brief note on which Python concept it illustrates (e.g. Protocol, dataclass, context manager, generator, async iterator).

3. **Function/method-level docstring** (every `def` and `async def`, including private `_helpers` and test functions). Use Google-style or reST-style docstrings consistently. Must include:
   - A one-line summary.
   - A longer description if the behavior is non-obvious.
   - `Args:` with type and meaning of each parameter.
   - `Returns:` with shape and meaning.
   - `Raises:` for every exception the function can raise (including those raised by callees that it doesn't catch).
   - For new learners: where appropriate, an inline example in a `Example:` block showing how to call it.

4. **Inline code comments** at the level of "explain the why, not the what" — but with a wider definition of "non-obvious" than the default style. For learners:
   - Comment any non-trivial control flow (early returns, loops with non-obvious termination, retry loops).
   - Comment any Python-specific idiom that a beginner might not recognize (e.g. `*args`/`**kwargs` unpacking, walrus operator, list comprehensions with conditional, context managers, decorators, generator expressions).
   - Comment any third-party API call that's doing something non-obvious (e.g. why `genai.Client(api_key=...)` is the only client construction we use, given we deliberately do not support Vertex mode).
   - Comment the *reason* behind any defensive check (e.g. `# We re-validate the mime type here even though the SDK does too — defense in depth, see core/transport/raw_http/client.py for the original CRLF guard rationale.`).
   - Comment any `# noqa` or `# type: ignore` with the specific reason.

5. **Test-file comments** — tests are documentation too. Each test function gets a docstring explaining what behavior is being verified and why it matters. Group related tests with a `class TestFoo:` whose docstring describes the contract under test.

6. **What NOT to comment**:
   - Don't restate identifiers (`x = 5  # set x to 5`) — even a beginner can read that.
   - Don't reference issue numbers, PR numbers, or "added by X on date Y" — the comment will rot.
   - Don't include emoji unless the user asks.

7. **Style**:
   - Use full sentences with proper punctuation.
   - Wrap at 100 columns.
   - Prefer `"""` for docstrings and `#` for inline comments. Never use `'''`.
   - Code reviewers will check this — a PR with sparse comments fails review.

This requirement applies **only to files this refactor writes or substantially modifies**. Existing untouched files are not in scope (a separate PR can backfill comments later if desired).

## Strict typing requirement (no `Any`)

Every Python file written or substantially modified by this refactor must be **fully type-annotated**, and the type `typing.Any` is **banned** from the new code surface.

Concrete rules:

1. **Every function parameter and return type is annotated.** No bare `def foo(x):` — must be `def foo(x: int) -> str:`.
2. **Every class attribute has a type.** Use dataclass fields with annotations or explicit class-level annotations. No untyped instance variables.
3. **Every module-level constant has a type.** Example: `_DEFAULT_TIMEOUT: int = 30`, not `_DEFAULT_TIMEOUT = 30`.
4. **No `Any` and no `object` as a fallback.** If you don't know the precise type, use one of:
   - A `TypedDict` for dict-shaped data with known keys.
   - A `Protocol` for duck-typed interfaces.
   - A `dataclass` or `pydantic.BaseModel` for record-shaped data.
   - A `Union[...]` or `X | Y` for genuine sum types.
   - A `TypeVar` bound to a Protocol for generics.
   - `Mapping[str, str]`, `Sequence[int]`, `Iterable[T]`, etc. for collections — never `dict`, `list`, `tuple` without parameters.
5. **The Gemini REST envelope is a `TypedDict`, not `dict[str, Any]`.** Define it once in `core/transport/normalize.py` (e.g. `class GeminiResponse(TypedDict)` with `candidates: list[Candidate]`, `usageMetadata: UsageMetadata | None`, `promptFeedback: PromptFeedback | None`). All adapters and helpers consume this typed shape. The current loose `dict[str, Any]` in helpers.py is an existing technical debt to clean up *for files this refactor touches*.
6. **No `# type: ignore` without a specific narrow reason** documented as a comment on the same line. `# type: ignore  # google-genai 1.33.0 does not export Foo type publicly; tracked at <link>`.
7. **`mypy --strict` (or `pyright --strict`) must pass on the new code surface.** Add a CI step that runs `mypy --strict core/transport/ adapters/generation/imagen.py adapters/generation/live.py` (and any other files this refactor writes or modifies). The CI gate is mandatory; PR cannot merge with strict-mode errors.
8. **`Any` is allowed only at the boundary with the `google.genai` SDK** *and only when explicitly cast back to a precise type immediately*. Pattern:
   ```python
   raw: object = client.models.generate_content(...)
   response: GeminiResponse = _to_envelope(raw)  # validates + casts
   ```
   The `_to_envelope` function is the one place where the imprecise SDK type meets the strict envelope, and it must do runtime validation (e.g. via pydantic's `model_validate` or manual key checks) so the cast is sound.
9. **`from __future__ import annotations` at the top of every new file** so `X | Y` syntax works on Python 3.9 (the minimum target).
10. **Tests are typed too.** Test functions and fixtures are annotated. Mock return values use precise types. `unittest.mock.MagicMock` is replaced with `Mock(spec=ConcreteClass)` so the mock has a real type.

How this is enforced:

- `setup/requirements-dev.txt` adds `mypy>=1.8` (or `pyright>=1.1.350`).
- `setup/run_tests.sh` runs `mypy --strict` on the new file surface before pytest.
- `.github/workflows/ci.yml` runs the same step.
- Code review checks: no `Any`, no untyped function, no untyped parameter.

This requirement applies **only to files this refactor writes or substantially modifies**. Existing untouched files are not in scope and may continue to use `dict[str, Any]` until a separate cleanup PR.

## TDD workflow & 100% coverage requirement (mandatory, non-negotiable)

**All implementation is test-driven. Tests are written FIRST, before any production code. Target: 100% line + branch coverage on every new module under `core/transport/`, every new adapter, every new core/auth file, every new core/infra file, every modified install/update/health module, and every backfilled `tests/scripts/` file.**

Per file, the loop is strictly:
1. **RED** — Write the failing test first. Run it; confirm it fails for the right reason (NameError, AssertionError, etc.).
2. **GREEN** — Write the minimum production code to make the test pass.
3. **REFACTOR** — Clean up with tests green. Run the full suite again.
4. **COVERAGE GATE** — Run `pytest --cov=<module> --cov-branch --cov-report=term-missing --cov-fail-under=100`. If the gate fails, add tests for the uncovered branches before moving on. Do NOT lower the threshold. Do NOT add `# pragma: no cover` to silence it.

Implementation order (each step is RED→GREEN→REFACTOR→COVERAGE before moving on, and EVERY step starts with a failing test commit):

1. `tests/transport/test_policy.py` → `core/transport/policy.py` — pure decision table, easiest to drive 100%. Every error class in the eligibility rules gets an explicit test row (eligible + not-eligible + boundary cases).
2. `tests/transport/test_base.py` → `core/transport/base.py` — Protocol shape, TypedDict structure, dataclass equality.
3. `tests/transport/test_normalize.py` → `core/transport/normalize.py` — fixtures for every adapter response category (text, multipart, inline image, tool calls, streaming chunk, file upload, usageMetadata, promptFeedback, safety block, grounding metadata). Use captured real SDK `model_dump()` outputs as JSON fixtures so the tests pin the contract.
4. `tests/core/infra/test_client.py` (update import paths) → move `core/infra/client.py` → `core/transport/raw_http/client.py`. Tests must stay green with zero behavior change. Verify coverage on the moved module is unchanged from baseline.
5. `tests/transport/test_raw_http_transport.py` → `core/transport/raw_http/transport.py` — every method delegates; mock the underlying client.py functions; assert call-through and exception passthrough.
6. (removed — no Vertex auth file in scope)
7. `tests/transport/sdk/test_client_factory.py` → `core/transport/sdk/client_factory.py` — API-key client construction, ImportError → BackendUnavailableError, lru_cache behavior, cache reset.
8. `tests/transport/sdk/test_transport.py` → `core/transport/sdk/transport.py` — every endpoint mapping (generateContent, streamGenerateContent, countTokens, embedContent, files.upload/list/get/delete/download, caches.*, batches.*, interactions.*, generate_videos, generate_images, operations.get). Each mapping needs: happy path, SDK exception → APIError translation, normalize call verification, kwargs translation, mime type validation in upload.
9. `tests/transport/sdk/test_async_transport.py` → `core/transport/sdk/async_transport.py` — async mirrors.
10. `tests/transport/test_coordinator.py` → `core/transport/coordinator.py` — full matrix:
    - primary success (fallback never invoked)
    - primary fail (eligible) → fallback success
    - primary fail (eligible) → fallback fail → combined APIError with both messages
    - primary fail (not eligible) → propagates immediately, fallback never invoked
    - both priority flags true → SDK is primary, raw HTTP is fallback (valid config)
    - both priority flags false → ConfigError surfaced at coordinator build time
    - only one true → that backend runs alone with no fallback target
    - primary == fallback → config validation rejects
    - missing-surface cache: AttributeError on first call → second call skips primary
    - async path: BackendUnavailableError raised when async_primary is None
    - coordinator caching across multiple calls
11. `tests/transport/test_facade.py` → `core/transport/__init__.py` — facade reads config, builds coordinator, delegates each public function (sync + async).
12. `tests/transport/test_parity.py` — for every ✅ Confirmed endpoint, assert byte-identical normalized response from both backends using mocked transports.
13. `tests/transport/test_auto_fallback.py` — coordinator with primary=sdk and forced AttributeError invokes raw HTTP via fallback path; verify cache.
14. `tests/core/infra/test_config.py` extensions → `core/infra/config.py` — defaults, JSON file overrides, env var overrides for the two priority flags, case-insensitive bool parsing, validation errors (both flags false), computed primary/fallback property tests, backward compat with old config files missing the fields.
15. `tests/core/infra/test_errors.py` extensions → `core/infra/errors.py` — BackendUnavailableError hierarchy, APIError carrying primary/fallback context, format_user_error rendering.
16. `tests/core/infra/test_checksums.py` → `core/infra/checksums.py` — generate, verify, mismatch detection, missing file, extra file, byte-for-byte equality.
17. `tests/core/cli/test_install_main.py` extensions → `core/cli/install_main.py` — venv creation, pip install, SDK verification, idempotent re-install, install-failure path, checksum verification, --skip-checksum flag, Windows interpreter path, file permissions.
18. `tests/core/cli/test_update_main.py` extensions → `core/cli/update_main.py` — pinned-version preservation (no silent upgrades), pre-update checksum verification, refusal on user-modified files, venv preservation across updates.
19. `tests/core/cli/test_health_main.py` extensions → `core/cli/health_main.py` — every reported field has an assertion (is_sdk_priority, is_rawhttp_priority, computed primary/fallback, SDK importable, venv path, pinned vs installed version, drift detection, checksum status).
20. `tests/scripts/test_gemini_run.py` → `scripts/gemini_run.py` — Python version guard, sys.path insertion, venv re-exec (in-venv, not-in-venv-but-venv-exists, no-venv), Windows path, argv pass-through, exit code propagation.
21. `tests/scripts/test_health_check.py` → `scripts/health_check.py` — thin launcher delegation.
22. `tests/core/infra/test_client.py` (final shim) → `core/infra/client.py` — verify the 5-line shim re-exports the three functions. Confirm `_SKILL_ROOT` no longer exists anywhere (`! grep -rn "_SKILL_ROOT" core/ tests/`).
23. `tests/core/cli/test_dispatch.py` extensions → `core/cli/dispatch.py` — IS_ASYNC adapter detection runs via `asyncio.run`.
24. `tests/adapters/generation/test_imagen.py` → `adapters/generation/imagen.py`.
25. `tests/adapters/generation/test_live.py` → `adapters/generation/live.py` — uses `pytest-asyncio`, mocks the async session.
26. `tests/adapters/media/test_image_gen.py` extensions → `adapters/media/image_gen.py` — new flags happy path + invalid value rejection.
27. `tests/adapters/data/test_files.py` extensions → `adapters/data/files.py` — new download subcommand.
28. `tests/adapters/tools/test_search.py` extensions → `adapters/tools/search.py` — `--show-grounding` JSON output.
29. `tests/integration/test_*_live.py` extensions and additions — every existing live test runs under both backends per the live-test matrix; new adapters get their own live tests (gated appropriately).

CI gates that enforce this:
- `pytest --cov=core/transport --cov=core/infra/checksums --cov=core/cli/install_main --cov=core/cli/update_main --cov=core/cli/health_main --cov=scripts --cov=adapters/generation/imagen --cov=adapters/generation/live --cov-branch --cov-fail-under=100` runs on every PR.
- `mypy --strict` on the same surface (per the strict typing section).
- Code review checks: every PR commit must contain test changes alongside production changes (no commit may add a non-test file without a corresponding test file change in the same commit, except for trivial doc updates).

Test infrastructure rules:
- **No live network in unit tests.** Everything mocks `urlopen`, `genai.Client`, and `subprocess.run`.
- **No coverage exclusions** (`# pragma: no cover`) on new code. If a branch is genuinely unreachable, prove it with a test that asserts the precondition.
- **Mutation-resistant**: tests assert observable behavior (return values, recorded mock calls, raised exception type + message), not just "function ran without error".
- **Test files use `Mock(spec=ConcreteClass)`**, not bare `MagicMock`, so the mock is type-checked against the real interface.
- Existing live tests in `tests/integration/` stay gated behind `GEMINI_LIVE_TESTS=1` and serve as end-to-end verification only — they do NOT count toward the 100% coverage target (which is measured on unit tests).

## Execution phases, model selection & effort budgeting

The refactor is large. Splitting it into focused phases gives token-efficient context windows (each phase only loads files it actually needs), enables checkpointing, and lets us pick the cheapest capable Claude model per phase. **Each phase is a separate session.** Don't try to run the whole refactor in one continuous conversation — context will balloon.

Conventions used below:
- **Model**: which Claude model to invoke for the phase. `haiku-4-5` for mechanical / well-specified work, `sonnet-4-6` for normal coding, `opus-4-6[1m]` only when the phase needs the 1M context window OR cross-cutting reasoning over many files.
- **Effort**: Claude Code thinking-budget level. `low` (~4k thinking tokens), `medium` (~16k), `high` (~32k+). Set via `/effort` or in agent prompts.
- **Token efficiency notes**: which files to load up front, which to defer. Aim to keep working context under 100k tokens per phase.
- **Exit gate**: what must be true before moving to the next phase. Each gate is verified by running the listed command and checking it passes.

### Phase 0 — Pre-implementation (~30 min, free of LLM cost)
**Goal**: Branch hygiene + plan capture.
- **Model**: not LLM-bound; this is shell work. If running through Claude, use `haiku-4-5` / `low`.
- **Steps**: pre-implementation steps 1–6 from the top of this plan (`git checkout main`, pull, new branch, copy plan into `docs/planning/`, first commit).
- **Token efficiency**: load nothing. Just shell.
- **Exit gate**: `git status` clean on `refactor/dual-backend-sdk-and-raw-http`, plan file committed.

### Phase 1 — Foundation: typed contracts, policy, normalize, raw HTTP move (~3 hrs LLM time)
**Goal**: Land the new `core/transport/` skeleton with the moved raw HTTP backend + the policy and normalize modules. **All TDD; every file gets a failing test first.**
- **Files**: TDD steps 1–5 from the TDD section above.
  - `core/transport/policy.py`, `base.py`, `normalize.py`, `raw_http/client.py` (move), `raw_http/transport.py`, plus their tests.
- **Model**: `sonnet-4-6` / **medium** effort. The work is well-specified (this plan is the spec) and mostly mechanical translation of pseudocode to typed code with comments. Sonnet is the sweet spot.
- **Token efficiency**: load only `core/infra/client.py`, `core/infra/errors.py`, `core/auth/auth.py`, the pseudocode section of this plan, and the relevant existing test files. ~30k tokens. Do NOT load adapters in this phase.
- **Exit gate**: `pytest tests/transport/ tests/core/infra/test_client.py --cov=core/transport --cov-branch --cov-fail-under=100` green. `mypy --strict core/transport/` green. Commit.

### Phase 2 — SDK transport (sync) + SDK client factory (~4 hrs)
**Goal**: SDK backend reaches feature parity with raw HTTP for every ✅ Confirmed endpoint.
- **Files**: TDD steps 7–8.
  - `core/transport/sdk/client_factory.py`, `core/transport/sdk/transport.py`, plus tests.
- **Model**: `sonnet-4-6` / **high** effort. Endpoint translation is the trickiest mechanical work — many cases, easy to miss one. Higher thinking budget reduces correction loops.
- **Token efficiency**: load Phase 1 outputs + `setup/requirements.txt` + the parity table from this plan. Use Context7 (`/googleapis/python-genai`) on demand for any specific endpoint shape rather than loading the SDK source. ~50k tokens.
- **Exit gate**: `pytest tests/transport/sdk/ --cov-fail-under=100` green. `pytest tests/transport/test_parity.py` green (every confirmed endpoint produces byte-identical normalized envelopes from both backends). Commit.

### Phase 3 — Coordinator + facade + auto-fallback + missing-surface cache (~2 hrs)
**Goal**: Wire SDK + raw HTTP together behind the coordinator. This is the architectural heart of the refactor; small file count but high subtlety.
- **Files**: TDD steps 10–13.
  - `core/transport/coordinator.py`, `core/transport/__init__.py`, `tests/transport/test_coordinator.py`, `test_facade.py`, `test_auto_fallback.py`.
- **Model**: `sonnet-4-6` / **high** effort. Decision logic + cache + error wrapping warrants thinking budget.
- **Token efficiency**: load Phase 1 + 2 outputs and the coordinator + policy pseudocode. ~40k tokens.
- **Exit gate**: full coordinator test matrix green at 100% coverage. The `core/infra/client.py` shim still resolves for existing adapter tests (run `pytest tests/adapters/` — must stay 100% green with zero adapter changes). Commit.

### Phase 4 — Errors + checksums (config moved to Phase 1) — model: `haiku`, effort: `medium`

- [ ] **Switch model to `haiku`, effort to `medium`** before writing any code; verify via `/status` + shim cleanup (~2 hrs)
**Goal**: Bolt the new config fields and error types onto the existing `core/infra/`. Add the `checksums.py` feature and convert the doc TODOs.
- **Files**: TDD steps 14–16, 22.
- **Model**: `haiku-4-5` / **medium** effort. Mechanical edits to existing well-tested modules; haiku handles this fine and saves cost.
- **Token efficiency**: load only the existing `core/infra/{config,errors}.py`, their tests, and the pseudocode. ~25k tokens.
- **Exit gate**: `pytest tests/core/infra/ --cov=core/infra --cov-fail-under=100` green. Commit.

### Phase 5 — Install/update/health + venv + requirements.txt + scripts (~3 hrs)
**Goal**: Skill-local venv, pinned-deps install, drift detection, re-exec under venv, checksum integration.
- **Files**: TDD steps 17–21 + new `setup/requirements.txt` + SKILL.md interpreter update.
- **Model**: `sonnet-4-6` / **medium** effort. Subprocess + filesystem work is sonnet-friendly; haiku risks subtle cross-platform bugs.
- **Token efficiency**: load Phase 4 outputs + existing `core/cli/{install,update,health}_main.py`, `scripts/gemini_run.py`, `SKILL.md`. ~35k tokens. Defer doc updates to Phase 9.
- **Exit gate**: `pytest tests/core/cli/ tests/scripts/ --cov-fail-under=100` green. Manual install dry-run (in a temp HOME): venv created, `google-genai==1.33.0` installed, `import google.genai` succeeds, `health_check.py` reports correctly. Commit.

### Phase 6 — Async transport + dispatch async path — model: `sonnet`, effort: `high`

- [ ] **Switch model to `sonnet`, effort to `high`** before writing any code; verify via `/status` (~3 hrs)
**Goal**: Lay the async dispatch foundation needed by the Live API adapter.
- **Files**: TDD step 9 + dispatch extension (step 23) + `core/transport/sdk/async_transport.py` + coordinator's `execute_*_async` mirrors.
- **Model**: `sonnet-4-6` / **high** effort. Async correctness needs thinking budget.
- **Token efficiency**: load Phase 1 + 3 outputs only. ~30k tokens.
- **Exit gate**: `pytest tests/transport/sdk/test_async_transport.py tests/transport/test_async_coordinator.py --cov-fail-under=100` green. Commit.

### Phase 7 — New adapters: imagen, live + adapter extensions (~4 hrs)
**Goal**: Net-new SDK features the user approved.
- **Files**: TDD steps 24–28.
  - New: `adapters/generation/imagen.py`, `adapters/generation/live.py`.
  - Extended: `adapters/media/image_gen.py`, `adapters/data/files.py`, `adapters/tools/search.py`.
  - All adapter tests + reference docs for new adapters.
- **Model**: `sonnet-4-6` / **medium** effort. Adapters follow a well-established pattern in this repo; medium effort is enough.
- **Token efficiency**: load 3–4 representative existing adapters as templates (`adapters/generation/text.py`, `adapters/media/image_gen.py`, `adapters/data/files.py`) + the new-features pseudocode + Phase 2 SDK transport for endpoint reference. ~50k tokens.
- **Exit gate**: every new/modified adapter at 100% unit-test coverage. Commit.

### Phase 8 — Live integration matrix — model: `haiku`, effort: `low`

- [ ] **Switch model to `haiku`, effort to `low`** before writing any test files; verify via `/status` (~2 hrs LLM + ~10 min real API time)
**Goal**: Get all 20 existing live tests + 2 new live tests (`test_imagen_live.py`, `test_live_live.py`) green under both backends.

- **Files**: extend `tests/integration/conftest.py` with backend selection helper, add `tests/integration/test_imagen_live.py`, `test_live_live.py`, update `.github/workflows/ci.yml` matrix.
- **Model**: `haiku-4-5` / **low** effort. Test files are templated and predictable.
- **Token efficiency**: load 2–3 existing `tests/integration/test_*_live.py` as templates + pseudocode. ~20k tokens.

**Live integration test design (full detail):**

The 20 existing live smoke tests in [tests/integration/](tests/integration/) currently exercise the raw HTTP path implicitly. After this refactor, they must run end-to-end against both backends. Concretely:

1. **Backend selection via env var.** The two priority flags `GEMINI_IS_SDK_PRIORITY` / `GEMINI_IS_RAWHTTP_PRIORITY` are read from the process environment by [core/infra/config.py](core/infra/config.py)'s `_parse_bool_env` helper. The live test runner flips them per-run via `env=` on `subprocess.run`. No live-test-specific env overrides; the production config path is the test path.

2. **Each live test stays single-backend per run.** Do not parametrize each test internally — the existing `subprocess.run([sys.executable, gemini_run.py, ...])` shape stays. Instead, the test runner is invoked twice with different env (see exit gate below).

3. **CI matrix** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) gains a `backend: [sdk, raw_http]` matrix dimension on the live job. The live job is gated (only runs on `workflow_dispatch` or main pushes, never on PRs from forks) so secrets aren't exposed.

4. **Auto-fallback verification.** For capabilities where the SDK doesn't expose the surface (deep_research, file_search, music_gen, computer_use, maps — all candidates per the parity audit), the `sdk` matrix run still executes the test; the test verifies the run was routed via raw HTTP under SDK primary by checking the "last backend used" marker the coordinator writes to a tmpfile during each subprocess invocation. A small assertion helper in `tests/integration/conftest.py` reads that marker and exposes it as a fixture.

5. **Test runner setup uses the venv interpreter.** Each `tests/integration/test_*_live.py` already builds the subprocess command as `[sys.executable, str(_RUNNER), ...]`. Update the helper (or add a fixture) so `sys.executable` resolves to `~/.claude/skills/gemini/.venv/bin/python` when running the installed-skill flavor of the suite, OR to the repo's local `.venv` interpreter when running from the repo. A `_RUNNER_PYTHON` constant in `tests/integration/conftest.py` centralizes this so all 22 tests pick it up uniformly with no per-file duplication.

6. **Parity guarantee.** Each live test asserts the same observable success criteria regardless of backend (e.g. `test_text_live` asserts non-empty stdout — true for both backends). The whole point of the dual-backend matrix is that adapters never see the backend, so identical assertions must pass under both.

7. **Cost protection.** The live suite is already cheap (~few cents) but running both backends doubles the cost. To run only one backend locally, simply omit one of the two pytest invocations below (the developer chooses which to run). The `GEMINI_LIVE_TESTS=1` gate remains the master on/off switch.

8. **Document in [docs/testing.md](docs/testing.md)** in Phase 9 — add a "Running live tests against both backends" section with the exact two commands below and the cost note.

- **Exit gate**:
  - `GEMINI_LIVE_TESTS=1 GEMINI_IS_SDK_PRIORITY=true  GEMINI_IS_RAWHTTP_PRIORITY=false pytest tests/integration/ -v` all green.
  - `GEMINI_LIVE_TESTS=1 GEMINI_IS_SDK_PRIORITY=false GEMINI_IS_RAWHTTP_PRIORITY=true  pytest tests/integration/ -v` all green.
  - Marker-file assertions verify the right backend handled each call (no silent fallbacks during a "raw HTTP only" run).
  - Commit.

### Phase 9 — Documentation sweep (~3 hrs)
**Goal**: Bring every doc and reference file in line with the refactor.
- **Files**: every entry in the doc-sweep table — `README.md`, `SKILL.md`, all `docs/*.md`, all 19 `reference/*.md`, the planning file's "implemented" footer.
- **Model**: `sonnet-4-6` / **medium** effort. Writing prose at scale benefits from sonnet; haiku produces flatter copy.
- **Token efficiency**: do this in **two sub-batches** to keep context small:
  - 9a: README + SKILL + 4 high-traffic docs (install, architecture, contributing, testing). ~40k tokens.
  - 9b: remaining docs + all 19 reference files. ~50k tokens.
- **Exit gate**: `grep -rn "stdlib-only\|zero dependencies\|urllib" docs/ README.md SKILL.md reference/` returns nothing stale. A reader following only README + docs/install.md can install + run a command. Commit.

### Phase 10 — Final QA + PR — model: `opus-1m`, effort: `high`

- [ ] **Switch model to `opus-4-6[1m]`, effort to `high`** before starting the cross-cutting review pass; verify via `/status` (~1 hr)
**Goal**: Cross-cutting verification + open the PR.
- **Steps**: run the full coverage matrix one more time, run mypy --strict on the new surface, run both live-test backend matrices, manual install on a clean HOME, manual `/gemini text "hello"` from a fresh VSCode session, open PR with a description that links to `docs/planning/refactor-dual-backend-sdk-and-raw-http.md`.
- **Model**: `opus-4-6[1m]` / **high** effort. End of refactor needs a senior reviewer pass over diffs across the whole project; opus + 1M context is the right tool for "did we miss anything cross-cutting?".
- **Token efficiency**: this is the ONE phase where loading everything is intentional — that's the point of opus 1M here.
- **Exit gate**: PR opened, CI green (coverage + mypy + lint + unit tests; live tests gated), URL pasted back to user.

### Agent assignment per phase

Each phase delegates work to one or more named subagents available in this Claude Code environment. The phase owner (the human-driven main thread) loads the plan, dispatches the right agent(s), reviews their output, and gates the phase exit. Agents are reused across phases when their specialty matches.

Available agent inventory (from this environment):
- **`Plan`** — solutions architect / planning specialist. Designs implementation strategy, spots architectural trade-offs, identifies critical files. Use for cross-cutting design before any code lands.
- **`Explore`** — codebase explorer. Fast searches and "how does X work" questions. Use whenever a phase needs to understand existing code without modifying it.
- **`ecc:architect`** — software architecture specialist for system design and scalability decisions. Use for the SDK/raw HTTP contract design, fallback policy review, normalize-layer design.
- **`ecc:tdd-guide`** — Test-Driven Development specialist. Enforces write-tests-first and 80%+ coverage (we override to 100%). Use as the loop driver for every TDD cycle.
- **`ecc:python-reviewer`** — Python code review specialist (PEP 8, type hints, idioms, security). Use after every Python file lands.
- **`ecc:typescript-reviewer`** — not used in this refactor (no TS code).
- **`ecc:code-reviewer`** — generic code review specialist. Use as a second-pass review on cross-cutting changes.
- **`ecc:security-reviewer`** — security vulnerability detection. Use after every auth/transport/install file lands. Mandatory before merging anything that touches `core/auth/`, `core/transport/`, `core/cli/install_main.py`.
- **`ecc:performance-optimizer`** — bottleneck identification. Use on the streaming and async paths (Phase 6) and on the coordinator's missing-surface cache.
- **`ecc:refactor-cleaner`** — dead-code cleanup (knip / depcheck / ts-prune analogs). Use after Phase 4 (config/errors cleanup) and Phase 10 (final QA) to catch any leftover `_SKILL_ROOT` / `GOOGLE_API_KEY` / `vertex` references.
- **`ecc:database-reviewer`** — not used (no SQL).
- **`ecc:e2e-runner`** — end-to-end test specialist. Use in Phase 8 to drive the live test matrix.
- **`ecc:doc-updater`** — documentation and codemap specialist. Use in Phase 9 (doc sweep).
- **`ecc:docs-lookup`** — fetches up-to-date library docs via Context7. Use whenever the SDK surface is uncertain (mostly Phase 2).
- **`ecc:gan-generator`** + **`ecc:gan-evaluator`** — adversarial dual-review pair. Use on Phase 3 (coordinator) and Phase 10 (final QA) for high-stakes changes that benefit from a generator/evaluator loop.
- **`ecc:harness-optimizer`** / **`ecc:loop-operator`** — meta agents for tuning the harness. Not directly used in production work; only invoked if a phase loop stalls.
- **`Agent` (general-purpose)** — fallback for anything not covered by a specialist.

### Per-phase agent matrix

| Phase | Primary agent | Supporting agents | Why |
|---|---|---|---|
| 0 — Pre-impl | (human) | — | Shell-only git + plan-copy work, no LLM agent needed. |
| 1 — Foundation (policy / base / normalize / raw HTTP move) | `ecc:tdd-guide` | `Explore` (one-shot to map existing client.py before move), `ecc:python-reviewer` (review each landed file), `ecc:security-reviewer` (review the moved client.py to confirm no regression in CRLF guard / SSL handling) | TDD-led with strict typing and 100% coverage; reviewers verify quality at every commit. |
| 2 — SDK transport + client_factory | `ecc:tdd-guide` | `ecc:docs-lookup` (Context7 calls per uncertain SDK surface), `ecc:python-reviewer`, `ecc:security-reviewer` (auth wiring), `ecc:architect` (one-shot review of the endpoint dispatch strategy in transport.py before implementation begins) | SDK surface is large and uncertain; lookup agent prevents guessing. |
| 3 — Coordinator + facade + auto-fallback | `ecc:architect` (design pass first) → `ecc:tdd-guide` (drive TDD) | `ecc:gan-generator` + `ecc:gan-evaluator` (adversarial loop for the decision logic), `ecc:python-reviewer`, `ecc:performance-optimizer` (review the missing-surface cache), `ecc:security-reviewer` (review error-message sanitization in combined-error reporting) | Architectural heart of the refactor — highest-stakes file, gets the dual-agent adversarial loop. |
| 4 — Config + errors + checksums | `ecc:tdd-guide` | `ecc:python-reviewer`, `ecc:refactor-cleaner` (sweep for dead `primary_backend` / `fallback_enabled` / `_SKILL_ROOT` / `GOOGLE_API_KEY` references), `ecc:security-reviewer` (checksum integrity is a security feature — must be reviewed) | Mechanical extension; refactor-cleaner ensures the old constants are gone. |
| 5 — Install / update / health / venv / settings.json merge | `ecc:tdd-guide` | `ecc:python-reviewer`, `ecc:security-reviewer` (settings.json write path, 0o600 perms, malformed-JSON abort, no secret leakage in conflict reports — MANDATORY review), `Explore` (one-shot to find any other tool that writes ~/.claude/settings.json so we know what we must preserve) | The settings.json merge is the single highest-risk surface; security review is non-negotiable. |
| 6 — Async transport + dispatch async path | `ecc:tdd-guide` | `ecc:python-reviewer`, `ecc:performance-optimizer` (async correctness + concurrency review), `ecc:architect` (review of how IS_ASYNC adapters integrate with the existing dispatch flow) | Async correctness needs a performance-aware second pair of eyes. |
| 7 — New adapters + adapter extensions (imagen, live, image_gen flags, files download, search grounding) | `ecc:tdd-guide` | `ecc:python-reviewer` (per adapter), `ecc:docs-lookup` (verify Imagen / Live API SDK shape before implementing), `Explore` (read 3 representative existing adapters as templates) | Adapters are templated; main risk is mis-translating SDK surface, which lookup agent prevents. |
| 8 — Live integration test matrix | `ecc:e2e-runner` | `ecc:tdd-guide` (drives test creation), `ecc:python-reviewer` (review the conftest helper) | E2E specialist owns the live matrix; TDD agent ensures tests are written before extending fixtures. |
| 9a — Doc sweep (README, SKILL, install, architecture, contributing, testing) | `ecc:doc-updater` | `ecc:docs-lookup` (fetch any external doc references), `ecc:code-reviewer` (review prose for accuracy against the code) | Documentation specialist owns prose; lookup agent for accuracy on external references. |
| 9b — Doc sweep (remaining docs + 19 reference files) | `ecc:doc-updater` | `ecc:code-reviewer` | Same as 9a; smaller per-file footprint. |
| 9c — Mermaid diagrams → PNG | `ecc:doc-updater` | `Plan` (one-shot to validate which diagrams add the most value before authoring), `ecc:code-reviewer` (verify each PNG renders matches the corresponding architectural decision) | Doc updater owns the Mermaid sources; Plan agent picks the diagrams worth the cost. |
| 10 — Final QA + PR | `ecc:gan-evaluator` (cross-cutting senior pass) + `ecc:code-reviewer` | `ecc:security-reviewer` (final security pass over `core/auth/`, `core/transport/sdk/client_factory.py`, install settings merge), `ecc:refactor-cleaner` (one last sweep for dead code / stale references), `ecc:e2e-runner` (run both backend matrices), `ecc:python-reviewer` (final type/style pass) | The "did we miss anything cross-cutting" gate. Multiple specialists run in parallel against the merged diff. |

### Model + effort switching protocol (must be enforced at phase boundaries)

The plan assigns a specific Claude model and effort level per phase (see the "Summary of model + effort allocation" table below). These assignments are **not advisory** — they are a load-bearing part of the cost / quality / latency trade-off. The implementer MUST switch the active model and effort level at every phase boundary. Concrete enforcement:

1. **At the start of every new phase, the very first action is to switch the model.** Use the Claude Code `/model` slash command (or the equivalent harness setting) to set the model named in the phase row. Examples:
   - Starting Phase 1 → run `/model claude-sonnet-4-6` (the harness alias may be `sonnet`).
   - Starting Phase 4 → run `/model claude-haiku-4-5` (alias `haiku`).
   - Starting Phase 10 → run `/model claude-opus-4-6[1m]` (alias `opus-1m`).
   The exact model IDs are listed in the table; the slash-command names depend on the harness's alias mapping.

2. **At the start of every new phase, the second action is to set the effort level.** Use `/effort low|medium|high` (or the harness equivalent). The effort row in the per-phase table is the floor — do NOT use a lower effort than listed. You MAY use a higher effort if the phase is going badly and you need more thinking budget, but only after surfacing the reason in the conversation.

3. **Verify the switch took effect** before writing any code in the new phase. Run a one-line sanity check:
   - The harness usually prints the active model and effort in its status line. Read it and confirm.
   - If unsure, ask the user to confirm by running `/status` or equivalent.

4. **Never carry the previous phase's model into a new phase silently.** If you forget to switch (e.g. you finish Phase 2 on sonnet/high and start Phase 4 without `/model haiku`), you will burn ~3× the budget for no quality benefit. Catch this in the phase-boundary checklist below.

5. **Within a phase, the model and effort do NOT change.** No mid-phase switching to "save tokens" — phase boundaries are the only legitimate switch points. The phase rows are calibrated against the work at the listed level; switching mid-phase invalidates the calibration and produces inconsistent output quality.

6. **Reviewer subagents inherit the parent's model unless overridden.** When you spawn `ecc:python-reviewer` or `ecc:security-reviewer` or any other agent, those agents run on whichever model is currently active for the parent thread, UNLESS you explicitly pass `model: "haiku" | "sonnet" | "opus"` to the `Agent` tool. For most reviewer passes, accept the inherited model — that's what the per-phase row anticipates. The exception is Phase 10's `ecc:gan-evaluator` adversarial pass, which should be explicitly invoked with `model: "opus"` even if the parent thread is on sonnet.

7. **Phase-boundary checklist** (run before writing the first failing test of every new phase):
   - [ ] `/model <name>` matches the value in the per-phase row
   - [ ] `/effort <level>` matches (or exceeds) the value in the per-phase row
   - [ ] Verified active settings via status line / `/status`
   - [ ] Loaded ONLY the sections listed in the per-phase content loading map (see top of plan)
   - [ ] Spawned the required reviewer subagents named in the agent matrix row
   - [ ] If overriding any default (e.g. higher effort than listed), the reason is stated in the conversation and noted in the PR description

8. **At the end of every phase**, before committing, leave a one-line marker in the conversation: `[phase N complete: <model> @ <effort>, exit gate green]`. This marker is what the next session uses to confirm the phase truly closed — without it, a fresh session can't tell whether to start Phase N+1 or finish Phase N.

9. **If a phase can't make progress at the listed model/effort**, do NOT just escalate silently. Pause, surface the issue to the user, and ask whether to bump the model (`sonnet → opus`) or the effort (`medium → high`) for the rest of the phase. Document the bump in the PR description.

10. **Cost telemetry**: at the end of every phase, record the actual Claude API cost in the conversation (visible via the harness usage display) so the next session knows whether the per-phase estimates are tracking. If a phase exceeds 1.5× its budget without delivering the exit gate, halt and re-plan with the user before continuing.

### Agent invocation rules

1. **Specialists are mandatory at gates, not optional.** Phase exits require at least one review pass from the listed reviewer agents. A green test suite alone does not meet the phase gate — you also need the reviewer agent's "approved" report.
2. **Reviewer agents run in parallel whenever they're independent.** For example in Phase 5, `ecc:python-reviewer` and `ecc:security-reviewer` review the same files in parallel (single message, multiple Agent tool calls), then the human-driven main thread reconciles their findings.
3. **`ecc:tdd-guide` is the loop driver, not the implementer.** It writes failing tests first, then either delegates implementation to `Agent` (general-purpose) or implements the minimum directly. Either way, the TDD loop is what governs what gets written next.
4. **Adversarial loops (`ecc:gan-generator` + `ecc:gan-evaluator`)** run in Phase 3 (coordinator) and Phase 10 (final QA) only — they're expensive and reserved for files where the cost of a subtle bug is highest.
5. **`Explore` is read-only and runs only when a phase needs context that's not already in the loaded files.** Never use it to re-read files we already have. One-shot per phase, max two per phase if exploring two distinct areas.
6. **`ecc:docs-lookup` is the only authorized way to fetch SDK documentation.** Don't paste SDK docs into the agent prompts manually — use Context7 via this agent so the docs are pinned to the installed `google-genai` version.
7. **`ecc:refactor-cleaner` runs at least twice**: once in Phase 4 (after the config/errors sweep) and once in Phase 10 (final QA). The Phase 4 run catches dead constants from this refactor; the Phase 10 run catches anything that snuck in across all phases.
8. **Reviewer disagreements escalate to `Plan`**: if `ecc:python-reviewer` and `ecc:security-reviewer` give conflicting feedback, `Plan` (the architect agent) breaks the tie with a written rationale committed to the PR description.

### Summary of model + effort allocation

| Phase | Model | Effort | Why |
|---|---|---|---|
| 0 — Pre-impl | (shell, haiku) | low | Mechanical git work |
| 1 — Foundation | sonnet-4-6 | medium | Well-specified TDD |
| 2 — SDK backend | sonnet-4-6 | high | Many endpoints, easy to miss |
| 3 — Coordinator | sonnet-4-6 | high | Subtle decision logic |
| 4 — Config + errors + checksums | haiku-4-5 | medium | Mechanical extension of existing modules |
| 5 — Install + venv | sonnet-4-6 | medium | Cross-platform subprocess work |
| 6 — Async path | sonnet-4-6 | high | Async correctness |
| 7 — New adapters | sonnet-4-6 | medium | Templated against existing adapters |
| 8 — Live test matrix | haiku-4-5 | low | Templated test files |
| 9 — Doc sweep | sonnet-4-6 | medium | Prose at scale |
| 10 — Final QA + PR | opus-4-6[1m] | high | Cross-cutting senior pass over the whole diff |

**Total estimated LLM working time: ~28 hours** (across phases, not counting waiting on real API calls or human review). **Estimated cost** depends on cache hits but should land roughly in the low hundreds of dollars given heavy use of haiku/sonnet and only one opus phase at the end.

**Token efficiency rules of thumb across phases:**
1. Each phase loads only the files it touches + its direct dependencies. Cross-phase artifacts are referenced by path, not re-loaded.
2. Tests are loaded alongside their production files in the same phase — never in a separate phase.
3. Generated/captured SDK fixtures (in `tests/transport/fixtures/`) are loaded only in phase 2 and never again.
4. The full pseudocode block of this plan is loaded once per phase as the spec — but only the relevant subsection, not the whole plan.
5. The 19 `reference/*.md` files are loaded ONLY in Phase 9b, never earlier — they don't inform the code.
6. After each phase, tell the user "phase N done, exit gate hit" and let them start a fresh session for phase N+1. Don't try to chain phases in one conversation.

## Pseudocode for every file to be created or substantially modified

Pseudocode below is **shape, not implementation** — it shows signatures, key control flow, and the contract each file owes its callers. Real implementation will be more detailed and follow the strict-typing + commenting rules above. Files are grouped by package.

### Package: `core/transport/` (new)

#### `core/transport/__init__.py`
```python
"""Public facade for the dual-backend Gemini transport layer.

Adapters import api_call/stream_generate_content/upload_file from here (or via
the core/infra/client.py shim). The facade owns the lazy TransportCoordinator
singleton and delegates each call.
"""
from __future__ import annotations
from collections.abc import Iterator
from pathlib import Path

from core.transport.base import GeminiResponse, StreamChunk, FileMetadata
from core.transport.coordinator import TransportCoordinator

_COORDINATOR: TransportCoordinator | None = None  # process-wide cache

def _get_coordinator() -> TransportCoordinator:
    """Lazy-build the coordinator from current Config."""
    global _COORDINATOR
    if _COORDINATOR is None:
        _COORDINATOR = TransportCoordinator.from_config()
    return _COORDINATOR

def reset_coordinator() -> None:
    """Test-only hook to drop the cached coordinator between runs."""
    global _COORDINATOR
    _COORDINATOR = None

def api_call(
    endpoint: str,
    body: Mapping[str, object] | None = None,
    method: str = "POST",
    api_version: str = "v1beta",
    timeout: int = 30,
) -> GeminiResponse:
    """Sync entrypoint mirroring the legacy core.infra.client.api_call signature."""
    return _get_coordinator().execute_api_call(endpoint, body, method, api_version, timeout)

def stream_generate_content(
    model: str,
    body: Mapping[str, object],
    api_version: str = "v1beta",
    timeout: int = 30,
) -> Iterator[StreamChunk]:
    return _get_coordinator().execute_stream(model, body, api_version, timeout)

def upload_file(
    file_path: Path | str,
    mime_type: str,
    display_name: str | None = None,
    timeout: int = 120,
) -> FileMetadata:
    return _get_coordinator().execute_upload(file_path, mime_type, display_name, timeout)

# Async mirrors for the Live API and other future async needs.
async def async_api_call(...) -> GeminiResponse: ...
async def async_stream_generate_content(...) -> AsyncIterator[StreamChunk]: ...
async def async_upload_file(...) -> FileMetadata: ...
```

#### `core/transport/base.py`
```python
"""Transport protocol + normalized response types.

Every backend (raw HTTP and SDK) implements Transport. Both must return
identically-shaped GeminiResponse dicts so adapters stay backend-agnostic.
"""
from typing import Protocol, TypedDict, Literal, runtime_checkable
from collections.abc import Iterator, AsyncIterator, Mapping

class Part(TypedDict, total=False):
    text: str
    inlineData: InlineData
    functionCall: FunctionCall
    functionResponse: FunctionResponse
    executableCode: ExecutableCode
    codeExecutionResult: CodeExecutionResult

class Content(TypedDict):
    role: Literal["user", "model"]
    parts: list[Part]

class Candidate(TypedDict, total=False):
    content: Content
    finishReason: str
    safetyRatings: list[SafetyRating]
    groundingMetadata: GroundingMetadata

class UsageMetadata(TypedDict, total=False):
    promptTokenCount: int
    candidatesTokenCount: int
    totalTokenCount: int

class GeminiResponse(TypedDict, total=False):
    candidates: list[Candidate]
    usageMetadata: UsageMetadata
    promptFeedback: PromptFeedback

class StreamChunk(GeminiResponse): ...

class FileMetadata(TypedDict):
    name: str
    displayName: str
    mimeType: str
    sizeBytes: str
    state: str
    uri: str

@runtime_checkable
class Transport(Protocol):
    name: Literal["sdk", "raw_http"]
    def api_call(self, endpoint: str, body: Mapping[str, object] | None,
                 method: str, api_version: str, timeout: int) -> GeminiResponse: ...
    def stream_generate_content(self, model: str, body: Mapping[str, object],
                                api_version: str, timeout: int) -> Iterator[StreamChunk]: ...
    def upload_file(self, file_path: Path | str, mime_type: str,
                    display_name: str | None, timeout: int) -> FileMetadata: ...

@runtime_checkable
class AsyncTransport(Protocol):
    """Same shape, async. Only SDK implements this; raw HTTP is sync-only."""
    name: Literal["sdk"]
    async def api_call(self, ...) -> GeminiResponse: ...
    async def stream_generate_content(self, ...) -> AsyncIterator[StreamChunk]: ...
    async def upload_file(self, ...) -> FileMetadata: ...
```

#### `core/transport/policy.py`
```python
"""Decision table for fallback eligibility.

Pure function. No I/O. Easy to unit-test exhaustively.
"""
from core.infra.errors import (
    AuthError, APIError, CapabilityUnavailableError, BackendUnavailableError,
    ModelNotFoundError, CostLimitError,
)

# Sentinel set: exception classes that NEVER allow fallback (programmer / auth bugs).
_NO_FALLBACK: tuple[type[Exception], ...] = (
    AuthError, ModelNotFoundError, CostLimitError,
    AssertionError, TypeError,  # programmer bugs (caveat: see TypeError exception below)
    ValueError,
)

def is_fallback_eligible(exc: BaseException, *, attempted_capability: str | None = None) -> bool:
    """Decide whether an exception from the primary backend permits fallback.

    Eligible: backend availability errors, transport network errors, transient
    server errors, missing-SDK-surface errors (AttributeError/ImportError on a
    google.genai symbol), and TypeError raised when constructing an SDK Tool
    with a kwarg the SDK version doesn't support.

    Not eligible: auth, programmer bugs, request validation, cost limits,
    safety blocks (which arrive as successful responses, not exceptions).
    """
    # 1. Hard "no" list short-circuits unless we recognize the special TypeError case.
    if isinstance(exc, _NO_FALLBACK):
        if isinstance(exc, TypeError) and _is_sdk_tool_kwarg_error(exc):
            return True  # SDK version too old to know this kwarg → fall back
        return False
    # 2. APIError with 4xx (except 429) → no fallback.
    if isinstance(exc, APIError) and exc.status_code is not None:
        if 400 <= exc.status_code < 500 and exc.status_code != 429:
            return False
        return True  # 429, 5xx, network → eligible
    # 3. Backend availability / capability gaps.
    if isinstance(exc, (BackendUnavailableError, CapabilityUnavailableError, ImportError, ModuleNotFoundError)):
        return True
    # 4. AttributeError from accessing an SDK symbol that doesn't exist.
    if isinstance(exc, AttributeError) and _looks_like_genai_attr_miss(exc):
        return True
    # 5. Network / socket / SSL.
    if isinstance(exc, (URLError, socket.timeout, ConnectionError)):
        return True
    return False

def _is_sdk_tool_kwarg_error(exc: TypeError) -> bool:
    """Detect 'unexpected keyword argument' from google.genai Tool/Config classes."""
    msg = str(exc)
    return "unexpected keyword argument" in msg and ("Tool" in msg or "Config" in msg)

def _looks_like_genai_attr_miss(exc: AttributeError) -> bool:
    """Detect missing attributes on google.genai client/types modules."""
    msg = str(exc)
    return "google.genai" in msg or "Client" in msg or "types" in msg
```

#### `core/transport/coordinator.py`
```python
"""Primary/fallback transport coordinator.

Owns the order of backend invocation, the missing-surface cache, and the
combined-error reporting when both backends fail.
"""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class _MissingSurfaceCache:
    """Per-process record of (capability, backend, attribute) tuples already known to fail.

    First call probes the SDK; on AttributeError we record the gap and skip the
    SDK probe on subsequent calls in the same process. Cache is dropped on
    coordinator reset (test hook) or process exit.
    """
    _seen: set[tuple[str, str]] = field(default_factory=set)
    def is_known_missing(self, capability: str, surface: str) -> bool: ...
    def mark_missing(self, capability: str, surface: str) -> None: ...

class TransportCoordinator:
    def __init__(self, primary: Transport, fallback: Transport | None,
                 async_primary: AsyncTransport | None = None) -> None: ...

    @classmethod
    def from_config(cls) -> "TransportCoordinator":
        """Build from core.infra.config.load_config() — used by the facade."""
        cfg = load_config()
        primary = _build_backend(cfg.primary_backend, cfg)
        fallback = _build_backend(cfg.fallback_backend, cfg) if cfg.fallback_backend != cfg.primary_backend else None
        async_primary = _build_async_backend(cfg.primary_backend, cfg)  # SDK only
        return cls(primary, fallback, async_primary)

    # Sync execution
    def execute_api_call(self, endpoint, body, method, api_version, timeout) -> GeminiResponse:
        return self._execute("api_call", lambda t: t.api_call(endpoint, body, method, api_version, timeout))

    def execute_stream(...) -> Iterator[StreamChunk]: ...
    def execute_upload(...) -> FileMetadata: ...

    def _execute(self, op_name: str, call: Callable[[Transport], T]) -> T:
        """Try primary; on eligible failure, try fallback; on both fail, raise combined APIError."""
        capability = _derive_capability_from_op(op_name)  # for cache lookup
        # Skip primary if we already know it lacks this surface in this process.
        if self._cache.is_known_missing(capability, self._primary.name):
            return self._call_fallback_only(call, capability)
        try:
            return call(self._primary)
        except BaseException as primary_exc:
            if not is_fallback_eligible(primary_exc, attempted_capability=capability):
                raise
            # Cache missing-surface signals so we don't re-probe.
            if isinstance(primary_exc, (AttributeError, ImportError, ModuleNotFoundError, BackendUnavailableError)):
                self._cache.mark_missing(capability, self._primary.name)
            if self._fallback is None:  # both flags pointed to the same backend → no fallback exists
                raise APIError(
                    message=f"Primary backend {self._primary.name} failed and fallback is disabled.",
                    primary_backend=self._primary.name,
                    primary_error=str(primary_exc),
                ) from primary_exc
            try:
                return call(self._fallback)
            except BaseException as fallback_exc:
                raise APIError(
                    message=f"Both backends failed. Primary {self._primary.name}: {primary_exc}. "
                            f"Fallback {self._fallback.name}: {fallback_exc}.",
                    primary_backend=self._primary.name,
                    fallback_backend=self._fallback.name,
                    primary_error=str(primary_exc),
                    fallback_error=str(fallback_exc),
                ) from fallback_exc

    # Async execution mirror — only available when primary is SDK.
    async def execute_api_call_async(self, ...) -> GeminiResponse:
        if self._async_primary is None:
            raise BackendUnavailableError("Async dispatch requires the SDK backend.")
        # Async path does NOT fall back to raw HTTP (raw HTTP is sync-only).
        return await self._async_primary.api_call(...)
```

#### `core/transport/normalize.py`
```python
"""Convert google.genai SDK response objects into the REST envelope shape.

The SDK uses pydantic models; calling .model_dump(exclude_none=True) gives us
a dict that's nearly the REST shape. This module fixes any snake_case →
camelCase mismatches and validates the result against the GeminiResponse
TypedDict.
"""

def sdk_response_to_rest_envelope(sdk_obj: object) -> GeminiResponse:
    """Cast an SDK response (pydantic) into the GeminiResponse TypedDict.

    Raises TypeError if sdk_obj is not a recognized SDK response class.
    """
    if hasattr(sdk_obj, "model_dump"):
        raw = sdk_obj.model_dump(exclude_none=True, by_alias=True)
        # by_alias=True emits camelCase per the field aliases the SDK sets.
        return _validate_envelope(raw)
    raise TypeError(f"Cannot normalize {type(sdk_obj).__name__}")

def sdk_stream_chunk_to_envelope(chunk: object) -> StreamChunk: ...
def sdk_file_to_metadata(file_obj: object) -> FileMetadata: ...

def _validate_envelope(raw: Mapping[str, object]) -> GeminiResponse:
    """Sanity-check the dict has the expected top-level keys.

    Raises APIError if the shape doesn't match — that means the SDK changed
    and we need to update normalize.py.
    """
```

#### `core/transport/raw_http/client.py`
**MOVED** verbatim from `core/infra/client.py`. Only changes:
- DELETE the `_SKILL_ROOT` constant entirely; remove the `env_dir=_SKILL_ROOT` argument from every `resolve_key()` call.
- Add module-level `__all__` listing the three public functions.
- Add file-level docstring explaining "this is the raw HTTP backend, retained as a fallback after the dual-backend refactor — see core/transport/coordinator.py for routing."
- All retry, SSE, multipart, error-extraction, mime-validation logic preserved unchanged.

#### `core/transport/raw_http/transport.py`
```python
"""RawHttpTransport — Transport protocol implementation backed by urllib.

This is the existing raw HTTP code path, wrapped in a class that conforms to
the Transport protocol so the coordinator can swap it with the SDK backend.
"""
from typing import Literal, Mapping
from core.transport.base import Transport, GeminiResponse, StreamChunk, FileMetadata
from core.transport.raw_http import client as _raw

class RawHttpTransport:
    name: Literal["raw_http"] = "raw_http"

    def api_call(self, endpoint, body, method, api_version, timeout) -> GeminiResponse:
        # Delegate to the existing function. It already returns a dict matching GeminiResponse.
        return _raw.api_call(endpoint=endpoint, body=body, method=method,
                             api_version=api_version, timeout=timeout)

    def stream_generate_content(self, model, body, api_version, timeout) -> Iterator[StreamChunk]:
        yield from _raw.stream_generate_content(model=model, body=body,
                                                api_version=api_version, timeout=timeout)

    def upload_file(self, file_path, mime_type, display_name, timeout) -> FileMetadata:
        return _raw.upload_file(file_path=file_path, mime_type=mime_type,
                                display_name=display_name, timeout=timeout)
```

#### `core/transport/sdk/client_factory.py`
```python
"""Lazy google.genai.Client factory — API-key auth only.

This skill deliberately does NOT support Vertex AI mode. The client is always
constructed with `api_key=resolve_key()`. Vertex support, ADC auth, and the
google-auth dependency are out of scope.
"""
from functools import lru_cache
from core.infra.errors import BackendUnavailableError
from core.auth.auth import resolve_key

@lru_cache(maxsize=1)
def get_client() -> "genai.Client":
    """Return a configured google.genai.Client. Raises BackendUnavailableError on import failure."""
    try:
        from google import genai  # lazy import — keeps raw HTTP path working without the SDK
    except ImportError as exc:
        raise BackendUnavailableError(
            "google-genai is not installed. Run setup/install.py to create the skill venv."
        ) from exc
    return genai.Client(api_key=resolve_key())

def get_async_client() -> "genai.client.AsyncClient":
    """SDK exposes the async surface as client.aio — return that."""
    return get_client().aio
```

#### `core/transport/sdk/transport.py`
```python
"""SdkTransport — Transport protocol implementation backed by google-genai.

Translates legacy REST-shaped requests into SDK calls and normalizes the SDK's
pydantic response objects back into GeminiResponse dicts so adapters never
notice which backend ran.
"""
from typing import Literal, Mapping
from core.transport.base import Transport, GeminiResponse, StreamChunk, FileMetadata
from core.transport.normalize import (
    sdk_response_to_rest_envelope, sdk_stream_chunk_to_envelope, sdk_file_to_metadata,
)
from core.transport.sdk.client_factory import get_client

class SdkTransport:
    name: Literal["sdk"] = "sdk"

    def __init__(self) -> None:
        pass

    @property
    def _client(self) -> "genai.Client":
        return get_client()

    def api_call(self, endpoint, body, method, api_version, timeout) -> GeminiResponse:
        """Parse the legacy REST endpoint string and dispatch to the right SDK method."""
        model, action = _parse_endpoint(endpoint)  # e.g. "models/gemini-2.5-flash:generateContent"
        match action:
            case "generateContent":
                cfg = _body_to_generate_content_config(body)
                contents = _body_to_contents(body)
                with _wrap_sdk_errors():
                    sdk_resp = self._client.models.generate_content(
                        model=model, contents=contents, config=cfg)
                return sdk_response_to_rest_envelope(sdk_resp)
            case "countTokens":
                with _wrap_sdk_errors():
                    sdk_resp = self._client.models.count_tokens(model=model, contents=_body_to_contents(body))
                return sdk_response_to_rest_envelope(sdk_resp)
            case "embedContent":
                ...
            case "files":  # list
                ...
            case "cachedContents":
                ...
            case "batchJobs":
                ...
            case "interactions":  # deep research
                ...
            # ... etc for every endpoint in the parity table
            case _:
                raise BackendUnavailableError(f"SDK transport does not yet handle {action}")

    def stream_generate_content(self, model, body, api_version, timeout) -> Iterator[StreamChunk]:
        cfg = _body_to_generate_content_config(body)
        contents = _body_to_contents(body)
        with _wrap_sdk_errors():
            for chunk in self._client.models.generate_content_stream(model=model, contents=contents, config=cfg):
                yield sdk_stream_chunk_to_envelope(chunk)

    def upload_file(self, file_path, mime_type, display_name, timeout) -> FileMetadata:
        _validate_mime_type(mime_type)  # defense in depth — same regex as raw_http/client.py
        with _wrap_sdk_errors():
            sdk_file = self._client.files.upload(
                file=str(file_path),
                config={"mime_type": mime_type, "display_name": display_name},
            )
        return sdk_file_to_metadata(sdk_file)

@contextmanager
def _wrap_sdk_errors() -> Iterator[None]:
    """Map google.api_core / google.genai exceptions into GeminiSkillError subclasses."""
    try:
        yield
    except google.api_core.exceptions.PermissionDenied as exc:
        raise AuthError(str(exc)) from exc
    except google.api_core.exceptions.ResourceExhausted as exc:
        raise APIError(str(exc), status_code=429) from exc
    except google.api_core.exceptions.GoogleAPIError as exc:
        raise APIError(str(exc), status_code=getattr(exc, "code", None)) from exc
```

#### `core/transport/sdk/async_transport.py`
```python
"""SdkAsyncTransport — async mirror of SdkTransport using client.aio.*

Used by adapters that opt in via IS_ASYNC = True (currently only adapters/generation/live.py).
"""
class SdkAsyncTransport:
    name: Literal["sdk"] = "sdk"
    async def api_call(self, ...) -> GeminiResponse: ...  # same shape as sync, but await client.aio.*
    async def stream_generate_content(self, ...) -> AsyncIterator[StreamChunk]: ...
    async def upload_file(self, ...) -> FileMetadata: ...
    async def live_connect(self, model: str, config: LiveConnectConfig) -> AsyncContextManager["LiveSession"]:
        return self._client.aio.live.connect(model=model, config=config)
```

### Package: `core/auth/` (modified — GOOGLE_API_KEY removed)

#### `core/auth/auth.py` (modified)

```python
"""Resolve the Gemini API key from environment or local-dev .env file.

GOOGLE_API_KEY is intentionally NOT honored — GEMINI_API_KEY is the one
canonical name to avoid confusion. See docs/security.md for rationale.
"""
def resolve_key(*, env_dir: Path | None = None) -> str:
    """See the auth resolver pseudocode in the 'Auth resolver changes' section above.

    Implementation rule: only check os.environ["GEMINI_API_KEY"] and the optional
    repo-root .env file. Do NOT check GOOGLE_API_KEY anywhere — strip the existing
    branch from the current code.
    """
```

The full pseudocode is in the [Auth resolver changes](#auth-resolver-changes-coreauthauthpy) section above; this entry exists so the file-by-file pseudocode pass has a clear marker that `core/auth/auth.py` is in scope for modification.

### Package: `core/infra/` (modified)

#### `core/infra/client.py` (rewritten as shim)
```python
"""Backward-compat shim — re-exports the dual-backend facade.

Existing adapters import from this module path; they don't need to change.
The shim only forwards.
"""
from core.transport import api_call, stream_generate_content, upload_file
__all__ = ["api_call", "stream_generate_content", "upload_file"]
```

#### `core/infra/config.py` (extended)
```python
@dataclass
class Config:
    # ... existing fields ...
    is_sdk_priority: bool = True       # from GEMINI_IS_SDK_PRIORITY
    is_rawhttp_priority: bool = False  # from GEMINI_IS_RAWHTTP_PRIORITY

    @property
    def primary_backend(self) -> Literal["sdk", "raw_http"]:
        """SDK wins whenever it's enabled (per user rule)."""
        return "sdk" if self.is_sdk_priority else "raw_http"

    @property
    def fallback_backend(self) -> Literal["sdk", "raw_http"] | None:
        """Returns the other backend if it's also enabled; None if only one is on."""
        if self.is_sdk_priority and self.is_rawhttp_priority:
            return "raw_http"  # SDK is primary, raw HTTP is fallback
        # Only one backend is enabled → no fallback target
        return None

    def __post_init__(self) -> None:
        if not self.is_sdk_priority and not self.is_rawhttp_priority:
            raise ValueError(
                "Both GEMINI_IS_SDK_PRIORITY and GEMINI_IS_RAWHTTP_PRIORITY are false. "
                "At least one must be true. Edit ~/.claude/settings.json env block."
            )

def _parse_bool_env(name: str, default: bool) -> bool:
    """Parse a settings.json env value as bool. Truthy: 'true','1','yes' (case-insensitive)."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes")

def load_config(config_dir: Path | None = None) -> Config:
    # ... existing JSON load ...
    cfg.is_sdk_priority     = _parse_bool_env("GEMINI_IS_SDK_PRIORITY", default=True)
    cfg.is_rawhttp_priority = _parse_bool_env("GEMINI_IS_RAWHTTP_PRIORITY", default=False)
    return cfg
```

#### `core/infra/errors.py` (extended)
```python
class BackendUnavailableError(GeminiSkillError):
    """A transport backend cannot be used (e.g. SDK not importable)."""

class APIError(GeminiSkillError):
    def __init__(self, message: str, status_code: int | None = None,
                 primary_backend: str | None = None,
                 fallback_backend: str | None = None,
                 primary_error: str | None = None,
                 fallback_error: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.primary_backend = primary_backend
        self.fallback_backend = fallback_backend
        self.primary_error = primary_error
        self.fallback_error = fallback_error
```

#### `core/infra/checksums.py` (NEW)
```python
"""SHA-256 checksum generation and verification for installed files."""
def generate_checksums(root: Path, included: Iterable[Path]) -> dict[str, str]: ...
def verify_checksums(root: Path, expected: Mapping[str, str]) -> list[str]:
    """Returns list of mismatched relative paths; empty list means all good."""
def write_checksums_file(checksums: Mapping[str, str], path: Path) -> None: ...
def read_checksums_file(path: Path) -> dict[str, str]: ...
```

### Package: `core/cli/` (modified)

#### `core/cli/install_main.py` (extended)
```python
def main(argv: Sequence[str]) -> int:
    """End-to-end install: copy → checksums → venv → pip → verify → write config."""
    args = _parse_args(argv)
    install_dir = Path("~/.claude/skills/gemini").expanduser()

    _copy_files(SOURCE, install_dir)
    if not args.skip_checksum:
        _verify_checksums(install_dir)
    venv_path = install_dir / ".venv"
    _create_venv(venv_path)             # venv.EnvBuilder(with_pip=True, upgrade_deps=True)
    _pip_install_requirements(venv_path, install_dir / "setup" / "requirements.txt")
    _verify_sdk_importable(venv_path)   # subprocess: <venv-py> -c "import google.genai; print(version)"
    _print_summary(venv_path, sdk_version)
    return 0

def _create_venv(path: Path) -> None: ...
def _pip_install_requirements(venv: Path, req: Path) -> None:
    """Run <venv>/bin/python -m pip install -r <req>. NO --upgrade flag (pinned)."""
def _verify_sdk_importable(venv: Path) -> str:
    """Run <venv>/bin/python -c '...'; return version. Raise InstallError on failure."""
```

#### `core/cli/update_main.py` (extended)
```python
def main(argv: Sequence[str]) -> int:
    install_dir = Path("~/.claude/skills/gemini").expanduser()
    venv_path = install_dir / ".venv"
    _verify_pre_update_checksums(install_dir)  # refuse if user-modified
    _copy_files(SOURCE, install_dir, preserve=[".env", ".venv"])
    if venv_path.exists():
        _pip_install_requirements(venv_path, install_dir / "setup" / "requirements.txt")
    else:
        _create_venv(venv_path)
        _pip_install_requirements(venv_path, ...)
    _verify_sdk_importable(venv_path)
    return 0
```

#### `core/cli/health_main.py` (extended)
```python
def main(argv: Sequence[str]) -> int:
    cfg = load_config()
    print(f"Primary backend: {cfg.primary_backend}")
    print(f"Fallback backend: {cfg.fallback_backend}")
    print(f"  GEMINI_IS_SDK_PRIORITY={cfg.is_sdk_priority}")
    print(f"  GEMINI_IS_RAWHTTP_PRIORITY={cfg.is_rawhttp_priority}")
    venv_python = Path("~/.claude/skills/gemini/.venv/bin/python").expanduser()
    print(f"Venv python: {venv_python} (exists={venv_python.exists()})")
    pinned = _read_pinned_version(install_dir / "setup" / "requirements.txt")
    installed = _get_installed_sdk_version(venv_python)
    print(f"google-genai: pinned={pinned}, installed={installed}")
    if pinned != installed:
        print("WARNING: SDK version drift detected. Run setup/install.py to reset.")
    print(f"Checksum status: {_verify_checksums(install_dir)}")
    return 0
```

### Package: `scripts/` (modified)

#### `scripts/gemini_run.py` (extended)
```python
"""Entry point invoked from SKILL.md. Re-execs under the skill venv if available."""
def main() -> int:
    _check_python_version()                 # >= 3.9
    _maybe_reexec_under_venv()              # NEW
    sys.path.insert(0, str(_repo_root()))
    from core.cli.dispatch import main as dispatch_main
    return dispatch_main(sys.argv[1:])

def _maybe_reexec_under_venv() -> None:
    venv_python = Path("~/.claude/skills/gemini/.venv/bin/python").expanduser()
    if sys.platform == "win32":
        venv_python = Path("~/.claude/skills/gemini/.venv/Scripts/python.exe").expanduser()
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
```

### New adapters

#### `adapters/generation/imagen.py`
```python
"""Imagen 3 text-to-image generator (uses client.models.generate_images)."""
def get_parser() -> argparse.ArgumentParser: ...
def run(prompt: str, model: str | None = None, num_images: int = 1,
        output_dir: str | None = None, execute: bool = False, **kwargs: object) -> None:
    if not execute:
        emit_dry_run(...); return
    config_obj = GenerateImagesConfig(number_of_images=num_images, output_mime_type="image/jpeg")
    body = {"_sdk_only_imagen": True, "prompt": prompt, "config": config_obj}
    response = api_call(f"models/{resolved_model}:generateImages", body=body)
    for i, img in enumerate(response["generatedImages"]):
        path = save_to_file(img["image"]["data"], output_dir, ext=".jpg")
        emit_json({"path": str(path), ...})
```

#### `adapters/generation/live.py`
```python
"""Live API adapter — async, uses client.aio.live.connect."""
IS_ASYNC: bool = True

def get_parser() -> argparse.ArgumentParser: ...
async def run_async(prompt: str, model: str = "gemini-live-2.5-flash-preview",
                    modalities: list[str] | None = None, **kwargs: object) -> None:
    cfg = LiveConnectConfig(response_modalities=modalities or ["TEXT"])
    transport = SdkAsyncTransport()
    async with await transport.live_connect(model, cfg) as session:
        await session.send_client_content(turns=Content(role="user", parts=[Part(text=prompt)]))
        async for msg in session.receive():
            if msg.text:
                print(msg.text, end="", flush=True)
            if msg.server_content and msg.server_content.turn_complete:
                break
```

### Adapter extensions

#### `adapters/media/image_gen.py` (extended)
```python
def get_parser():
    p = ...
    p.add_argument("--aspect-ratio", choices=["1:1","2:3","3:2","3:4","4:3","4:5","5:4","9:16","16:9","21:9"])
    p.add_argument("--image-size", choices=["1K","2K","4K"])
    return p

def run(..., aspect_ratio=None, image_size=None, ...):
    body = {"contents": [...], "generationConfig": {"responseModalities": ["IMAGE"]}}
    if aspect_ratio or image_size:
        body["generationConfig"]["imageConfig"] = {
            **({"aspectRatio": aspect_ratio} if aspect_ratio else {}),
            **({"imageSize": image_size} if image_size else {}),
        }
    response = api_call(..., body=body)
    ...
```

#### `adapters/data/files.py` (extended — add `download` subcommand)
```python
def _run_download(name: str, out_path: str) -> None:
    """GET <files/{name}>?alt=media on raw HTTP, or client.files.download on SDK."""
    body: Mapping[str, object] = {"_sdk_method": "files.download", "name": name}
    response = api_call(f"{name}", method="GET", body=body)  # transport routes appropriately
    Path(out_path).write_bytes(response["data"])
    emit_json({"path": out_path, "name": name, "size_bytes": len(response["data"])})
```

#### `adapters/tools/search.py` (extended)
```python
def run(..., show_grounding: bool = False, ...):
    response = api_call(...)
    text = extract_text(response)
    if show_grounding:
        meta = response.get("candidates", [{}])[0].get("groundingMetadata")
        emit_json({"text": text, "grounding": meta})
    else:
        emit_output(text, ...)
```

### Tests (one example per category — full list in the file-by-file table above)

#### `tests/transport/test_policy.py`
```python
"""Exhaustive table-driven tests for is_fallback_eligible.

Every exception class in the rules must have at least one assertion row.
"""
@pytest.mark.parametrize("exc, expected", [
    (AuthError("bad key"), False),
    (APIError("rate limit", status_code=429), True),
    (APIError("not found", status_code=404), False),
    (APIError("server error", status_code=500), True),
    (URLError("dns"), True),
    (socket.timeout(), True),
    (ImportError("google.genai"), True),
    (AttributeError("module 'google.genai' has no attribute 'foo'"), True),
    (TypeError("Tool() got an unexpected keyword argument 'google_maps'"), True),
    (TypeError("can't multiply sequence"), False),  # not SDK-related → no fallback
    (AssertionError(), False),
    (ValueError("bad json"), False),
    (CostLimitError("over limit", current=10, limit=5), False),
    (BackendUnavailableError("sdk missing"), True),
])
def test_is_fallback_eligible(exc, expected):
    assert is_fallback_eligible(exc) is expected
```

#### `tests/transport/test_coordinator.py`
```python
def test_primary_success_does_not_invoke_fallback(): ...
def test_primary_eligible_failure_falls_back_and_succeeds(): ...
def test_primary_eligible_failure_then_fallback_failure_raises_combined_error():
    primary = Mock(spec=Transport); primary.api_call.side_effect = URLError("p")
    fallback = Mock(spec=Transport); fallback.api_call.side_effect = URLError("f")
    coord = TransportCoordinator(primary, fallback)
    with pytest.raises(APIError) as exc_info:
        coord.execute_api_call(...)
    assert "Primary" in str(exc_info.value) and "Fallback" in str(exc_info.value)
def test_primary_non_eligible_failure_propagates_immediately(): ...
def test_fallback_disabled_never_invokes_fallback(): ...
def test_missing_surface_cache_skips_primary_on_second_call(): ...
def test_async_path_does_not_fall_back_to_raw_http(): ...
```

### Modified files (brief notes — full pseudocode would balloon the plan, but each file's contract is described above)

- [SKILL.md](SKILL.md): replace invocation with `${CLAUDE_SKILL_DIR}/.venv/bin/python`.
- [README.md](README.md): rewrite Quick Start per doc-sweep table.
- All `docs/*.md` and `reference/*.md`: per doc-sweep table.
- `core/cli/dispatch.py`: small addition — detect `IS_ASYNC` adapter attribute, run via `asyncio.run`.
- `tests/core/infra/test_client.py`: update import paths only; assertions unchanged.
- All extended adapter test files: add tests for the new flags/subcommands.
- All new live integration tests: `tests/integration/test_imagen_live.py`, `test_live_live.py`.



**All implementation must be test-driven. Target: 100% line + branch coverage on every new module under `core/transport/` and on the modified install flow.**

Per file, the loop is:
1. Write the failing test first (red).
2. Implement minimum code to pass (green).
3. Refactor with tests green.
4. Run `pytest --cov=core/transport --cov=core/cli/install_main --cov-branch --cov-report=term-missing --cov-fail-under=100` after each module lands. CI gate must enforce `--cov-fail-under=100` on the new surface.

Implementation order (each step is red→green→refactor before moving on):

1. `core/transport/policy.py` + `tests/transport/test_policy.py` — pure decision table, easiest to drive 100%. Every error class in the eligibility rules gets an explicit test row (eligible + not-eligible).
2. `core/transport/base.py` + `tests/transport/test_base.py` — `Transport` protocol shape, dataclass equality, `name` attribute.
3. `core/transport/normalize.py` + `tests/transport/test_normalize.py` — fixtures for every adapter response category (text, multipart, inline image, tool calls, streaming chunk, file upload, usageMetadata, promptFeedback, safety block). Use captured real SDK `model_dump()` outputs as fixtures so the tests pin the contract.
4. `core/transport/raw_http/client.py` (move) + update `tests/core/infra/test_client.py` import path — must stay green with zero behavior change. Verify coverage on the moved module is unchanged from baseline.
5. `core/transport/raw_http/transport.py` + `tests/transport/test_raw_http_transport.py` — every method delegates; mock the underlying `client.py` functions; assert call-through and exception passthrough.
6. `core/transport/sdk/client_factory.py` + tests — covers: lazy import success, `ImportError` → `BackendUnavailableError`, key resolution path, singleton caching, cache invalidation on auth change.
7. `core/transport/sdk/transport.py` + tests — mock `genai.Client`; cover every endpoint mapping (`generateContent`, `streamGenerateContent`, `countTokens`, `embedContent`, `files.upload`, `files.list`, `files.get`, `files.delete`, `cachedContents.*`, `batches.*`, `operations.*`). Each mapping needs: happy path, SDK exception → `APIError` translation, normalize call verification.
8. `core/transport/coordinator.py` + `tests/transport/test_coordinator.py` — matrix:
   - primary success (fallback never invoked)
   - primary fail (eligible) → fallback success
   - primary fail (eligible) → fallback fail → combined `APIError` with both messages
   - primary fail (not eligible) → propagates immediately, fallback never invoked
   - both priority flags true → SDK is primary, raw HTTP is fallback (valid; SDK always wins when both enabled)
    - both priority flags false → ConfigError at coordinator build
    - only one true → that backend is primary with no fallback target
   - primary == fallback (config validation rejects)
   - coordinator caching: same instance across calls; cache invalidates on config change
9. `core/transport/__init__.py` (facade) + `tests/transport/test_facade.py` — facade reads config, builds coordinator, delegates each of the three public functions. Cover the lazy/cached path.
10. `core/infra/config.py` field additions + `tests/core/infra/test_config.py` extensions — defaults, env overrides via the two GEMINI_IS_*_PRIORITY flags, validation errors (both flags false), case-insensitive bool parsing, computed primary_backend/fallback_backend property tests, backward compat with old config files missing the fields.
11. `core/infra/errors.py` extensions + tests — `BackendUnavailableError` hierarchy, `APIError` carrying `primary_backend`/`fallback_backend`/`primary_error`/`fallback_error`, `format_user_error` rendering.
12. `core/infra/client.py` shim + verify existing adapter tests still green and shim itself has full coverage.
13. `core/cli/install_main.py` venv steps + `tests/core/cli/test_install_main.py` — mock `venv.EnvBuilder` and `subprocess.run`; cover: fresh install creates venv, second install is idempotent, SDK install failure path falls back config to `raw_http` primary, Windows interpreter path, permissions on the venv directory.
14. `scripts/gemini_run.py` re-exec logic + tests — already-in-venv path, not-in-venv-but-venv-exists path (re-execs), not-in-venv-no-venv path (runs anyway), Windows path resolution.
15. `core/cli/health_main.py` reporting + tests — every reported field has an assertion (is_sdk_priority, is_rawhttp_priority, computed primary/fallback, SDK importable, venv path, google-genai version).

Test infrastructure rules:
- **No live network in unit tests.** Everything mocks `urlopen`, `genai.Client`, and `subprocess.run`.
- **No coverage exclusions** (`# pragma: no cover`) on new code. If a branch is genuinely unreachable, prove it with a test that asserts the precondition.
- **Mutation-resistant**: tests must assert observable behavior (return values, recorded mock calls, raised exception type + message), not just "function ran without error".
- Existing live tests in `tests/integration/` stay gated behind `GEMINI_LIVE_TESTS=1` and serve as end-to-end verification only — they don't count toward the 100% target.

## Architect-review revisions (consolidated cross-cutting fixes)

The two architect/planning agent reviews surfaced ~30 issues. The structural ones (config flag phase ordering, install_main split, capability registry, normalize hardening, layering fix, GOOGLE_API_KEY moved to Phase 0) are applied inline above. The remaining cross-cutting fixes are listed here:

### CR-1: Mermaid output is **SVG with a forced white background** (determinism + dark-mode legibility)

Two requirements that previously appeared to be in tension:
1. **Determinism** — the CI gate `git diff --exit-code docs/diagrams/*.<ext>` only works if the output is byte-stable across machines. PNG goes through Chromium and is NOT byte-stable across Chromium versions. SVG IS deterministic for a pinned Mermaid CLI version.
2. **Dark-mode legibility** — transparent SVGs render with white text on dark backgrounds in dark-mode environments and are unreadable.

**Solution: SVG with a forced white background.** `mmdc` accepts `-b <color>` to set the background. Use `-b white` (NOT `-b transparent`):
```bash
npx @mermaid-js/mermaid-cli@<pinned> \
  -i docs/diagrams/<name>.mmd \
  -o docs/diagrams/<name>.svg \
  -t default \
  -b white \
  -w 1600
```
The resulting SVG has an explicit white `<rect>` background element, renders identically in light AND dark mode (always white background, always dark text/lines on it), AND remains byte-deterministic.

**Replace PNG with SVG everywhere in the Mermaid section**: every `.png` filename becomes `.svg`, the `mmdc -o` flag uses `.svg`, the embed in markdown is `![alt](diagrams/<name>.svg)`. The `-b white` flag is mandatory in `scripts/render_diagrams.sh`.

**Fallback**: if a future Mermaid CLI version proves non-deterministic in SVG mode (regressions happen), fall back to PNG with `-b white -w 1600` and accept the determinism trade-off — make the `git diff --exit-code` gate advisory (warning, not failure) for the PNG case. SVG is the preferred path because it satisfies both requirements simultaneously.

### CR-2: Deadline tracking across fallback

When the primary backend exhausts a 30s timeout, the fallback should not start with a fresh 30s budget. `TransportCoordinator._execute` tracks an absolute deadline (`time.monotonic() + timeout`) when first called and passes the **remaining budget** to the fallback. If remaining < 1s, raise `APIError("budget exhausted before fallback")` instead of attempting. Tests: `test_coordinator_passes_remaining_budget_to_fallback`, `test_coordinator_skips_fallback_when_budget_exhausted`.

### CR-3: Structured fallback log

Every fallback invocation emits one log line via Python `logging` at WARNING level with structured fields (already shown in the revised `_execute` pseudocode in the architectural revision section). CI test captures `caplog` and asserts the expected log line on every fallback path.

### CR-4: Coverage gate scoped to changed modules only

Running `--cov-fail-under=100` on the FULL repo will fail because untouched modules (e.g. `core/state/`, `core/routing/`) aren't at 100% today. Scope the gate to only the modules this refactor touches:
```bash
pytest \
  --cov=core/transport --cov=core/auth --cov=core/infra/config \
  --cov=core/infra/errors --cov=core/infra/checksums \
  --cov=core/cli/installer --cov=core/cli/install_main --cov=core/cli/update_main \
  --cov=core/cli/health_main --cov=core/cli/dispatch \
  --cov=scripts \
  --cov=adapters/generation/imagen --cov=adapters/generation/live \
  --cov=adapters/media/image_gen --cov=adapters/data/files --cov=adapters/tools/search \
  --cov-branch --cov-fail-under=100
```
This is the canonical Phase 10 exit gate command.

### CR-5: `pytest-asyncio` added to dev requirements

The Live API adapter tests are async and require `pytest-asyncio==0.23.7`. Add it to `setup/requirements-dev.txt` in Phase 5.

### CR-6: CI installs google-genai BEFORE Phase 2

Phases 2-4 use `Mock(spec=genai.Client)` which requires `import google.genai` to succeed. Add a `pip install google-genai==1.33.0` step to `.github/workflows/ci.yml` immediately after Python setup. The `setup/requirements.txt` file lands in Phase 5; for Phases 1-4 use a temporary inline pip install in CI; remove the inline step in the Phase 5 commit.

### CR-7: `deepdiff` added to dev requirements (parity tests)

`pytest tests/transport/test_parity.py` uses `DeepDiff`. Add `deepdiff==7.0.1` to `setup/requirements-dev.txt`.

### CR-8: `getpass.getpass` warning on echo fallback

`getpass.getpass()` silently falls back to echoing input on unusual terminals. The `_prompt_gemini_api_key` helper detects this fallback (catches `getpass.GetPassWarning`) and refuses to proceed without explicit `--accept-echo` flag. Test: `test_prompt_api_key_refuses_when_getpass_falls_back_to_echo`.

### CR-9: `git mv` for the client.py move (already applied to Phase 1 checklist)

### CR-10: Time estimates revised (~28 hrs → ~60 hrs)

- Phase 0 — 30 min
- Phase 1 — 6 hrs (was 3) — now also lands config flags
- Phase 2 — 12 hrs (was 4) — 33-row endpoint matrix is the bulk
- Phase 3 — 6 hrs (was 2) — capability registry + 11 coordinator tests
- Phase 4 — 3 hrs (was 2) — checksums only; config moved to Phase 1
- Phase 5 — 8 hrs (was 3) — split into 4 installer submodules
- Phase 6 — 4 hrs (was 3)
- Phase 7 — 7 hrs (was 4)
- Phase 8 — 3 hrs (was 2)
- Phase 9 — 10 hrs (was 3) — includes Phase 9c
- Phase 10 — 2 hrs (was 1)
- **Total: ~60 hours** (was ~28)

### CR-11: ADRs

Add two ADRs in Phase 9b:
- `docs/adr/0001-google-genai-version-pinning.md` — upgrade procedure
- `docs/adr/0002-explicit-sdk-capability-registry.md` — why no try/except heuristics

### CR-13: Backup `~/.claude/settings.json` once at first touch

`core/cli/installer/settings_merge.py` writes `~/.claude/settings.json.pre-gemini-skill.bak` exactly once (on first install detection) before any merge. Documented recovery: `cp ~/.claude/settings.json.pre-gemini-skill.bak ~/.claude/settings.json`. Tests: `test_first_install_creates_backup`, `test_subsequent_installs_do_not_overwrite_backup`.

### CR-14: Empty-string-on-both-sides silent overwrite for GEMINI_API_KEY

If existing `GEMINI_API_KEY` is `""` AND the installer's default is `""`, the prompt is suppressed and the existing `""` stays untouched (not flagged as a conflict). Rationale: nobody intentionally stores `""`. Test: `test_merge_settings_no_prompt_when_both_sides_empty_string`.

### CR-15: Adapters-zero-edits CI check

Phase 7's marquee promise is "zero adapter edits" except for the explicitly-extended ones. Add CI gate that fails the PR if any unexpected adapter file changed.

### CR-16: Cost tracking wired in this refactor

`core/infra/cost.py` exists today but is unused. Wire `record_actual_cost(response)` into the coordinator so both backends feed `usageMetadata` into the cost tracker. Tests in `tests/transport/test_coordinator.py` extensions.

## Mermaid diagrams → SVG embeds in documentation

User decision: every documentation file that has an architectural concept worth diagramming gets a Mermaid source committed to the repo, rendered to PNG at build time, and the PNG embedded in the markdown (NOT the raw Mermaid block). Mermaid blocks alone are rejected because GitHub renders them, but VSCode preview and many static doc viewers do not — PNG ensures the diagram is visible everywhere.

### Diagram inventory (one row per diagram to produce)

| Source `.mmd` file | Renders to | Embedded in | What the diagram shows |
|---|---|---|---|
| `docs/diagrams/architecture-dual-backend.mmd` | `docs/diagrams/architecture-dual-backend.png` | [docs/architecture.md](docs/architecture.md), [README.md](README.md) | High-level dual-backend transport: adapters → facade → coordinator → SDK \| raw HTTP → Gemini API. |
| `docs/diagrams/coordinator-decision-flow.mmd` | `.../coordinator-decision-flow.png` | [docs/architecture.md](docs/architecture.md) | Sequence/flow diagram of `TransportCoordinator._execute`: try primary → eligible? → fallback → combined error. |
| `docs/diagrams/auto-fallback-cache.mmd` | `.../auto-fallback-cache.png` | [docs/architecture.md](docs/architecture.md) | The missing-surface cache lifecycle: first call probes SDK → AttributeError → cache marks → second call skips probe. |
| `docs/diagrams/install-flow.mmd` | `.../install-flow.png` | [docs/install.md](docs/install.md) | Install pipeline: copy files → checksums → venv → pip install requirements → verify SDK → merge settings.json → done. |
| `docs/diagrams/settings-merge-decision.mmd` | `.../settings-merge-decision.png` | [docs/install.md](docs/install.md) | Decision tree for `_merge_settings_env`: missing file / malformed / no env block / duplicate keys / clean merge. |
| `docs/diagrams/auth-resolution.mmd` | `.../auth-resolution.png` | [docs/security.md](docs/security.md), [docs/install.md](docs/install.md) | Auth precedence: `GEMINI_API_KEY` env (from settings.json) → repo-root `.env` (local-dev only) → `AuthError`. |
| `docs/diagrams/backend-priority-matrix.mmd` | `.../backend-priority-matrix.png` | [docs/architecture.md](docs/architecture.md), [README.md](README.md) | The 4-cell priority truth table: (sdk,raw) flag combinations → primary/fallback or error. |
| `docs/diagrams/request-lifecycle.mmd` | `.../request-lifecycle.png` | [docs/how-it-works.md](docs/how-it-works.md) | End-to-end sequence for a `gemini text` call: SKILL.md → venv → gemini_run.py → dispatch → adapter → coordinator → backend → Gemini → normalize → adapter → emit. |
| `docs/diagrams/streaming-flow.mmd` | `.../streaming-flow.png` | [docs/how-it-works.md](docs/how-it-works.md), [reference/streaming.md](reference/streaming.md) | Streaming chunks flowing through SDK or raw HTTP into the adapter loop. |
| `docs/diagrams/async-live-flow.mmd` | `.../async-live-flow.png` | [reference/live.md](reference/live.md) | Async dispatch + Live API session lifecycle: connect → send_client_content → receive loop → turn_complete. |
| `docs/diagrams/test-coverage-matrix.mmd` | `.../test-coverage-matrix.png` | [docs/testing.md](docs/testing.md) | Unit / parity / live-test-matrix layers and which gate each one passes through. |
| `docs/diagrams/phase-execution-timeline.mmd` | `.../phase-execution-timeline.png` | [docs/contributing.md](docs/contributing.md), [docs/planning/refactor-dual-backend-sdk-and-raw-http.md](docs/planning/refactor-dual-backend-sdk-and-raw-http.md) | Phase 0 → Phase 10 swimlane / gantt of the refactor with model + effort labels. |

### Rendering pipeline

1. **Tooling**: use the official Mermaid CLI (`@mermaid-js/mermaid-cli`, command `mmdc`). Pin the version in a new `setup/diagram-tools.json` (or hand off to `npx @mermaid-js/mermaid-cli@<pinned>`). The Mermaid CLI requires Node + Chromium; document this in `docs/contributing.md` under "How to regenerate diagrams".
2. **Source files**: every `.mmd` file lives under `docs/diagrams/` next to its rendered PNG. Source files are **canonical** — never edit the PNG. Reviewers read the `.mmd` diff in PRs.
3. **Render command**: `npx @mermaid-js/mermaid-cli@<pinned> -i docs/diagrams/<name>.mmd -o docs/diagrams/<name>.png -t default -b transparent -w 1600`. The `-w 1600` width gives readable PNGs on retina displays. Use `-t dark` only if a doc explicitly wants a dark theme.
4. **Helper script**: add `scripts/render_diagrams.sh` that loops over every `*.mmd` file and renders the matching `.png`. Idempotent — re-running produces byte-identical output (Mermaid CLI is deterministic when given the same input + version).
5. **CI gate**: a GitHub Action job runs `scripts/render_diagrams.sh` and then `git diff --exit-code docs/diagrams/*.png` — if a `.mmd` was edited but the PNG wasn't regenerated, CI fails with "diagram out of date; run scripts/render_diagrams.sh". Same pattern as common doc-as-code workflows.
6. **Markdown embedding**: docs reference the PNG via standard markdown image syntax with an alt-text fallback for screen readers and a link to the source for editors:
   ```markdown
   ![Dual-backend transport architecture](diagrams/architecture-dual-backend.png)
   <sub>Source: [`docs/diagrams/architecture-dual-backend.mmd`](diagrams/architecture-dual-backend.mmd) — regenerate with `scripts/render_diagrams.sh`</sub>
   ```
   Every embed includes the source-link footer so future editors find the `.mmd` immediately.
7. **No raw `mermaid` blocks in markdown.** PRs that add one get rejected — the rule is "PNG + source-link footer". Add a CI grep that fails if a markdown file under `docs/` or `reference/` contains ` ```mermaid ` outside the `docs/diagrams/` directory.

### Per-file changes added to the doc-sweep table

Each diagram inventory row implies a corresponding docs change in Phase 9:
- The doc gets a new section (or an existing section is extended) with the PNG embed.
- The PNG file and `.mmd` source are both committed.
- The doc text adjacent to the embed walks the reader through the diagram in 2-4 sentences (don't rely on the diagram alone — explain the key arrows and labels).
- Cross-diagram consistency: shared actors (e.g. "TransportCoordinator", "SdkTransport") use the same shape and color across every diagram so readers build a mental model that holds across docs.

### New TDD step (added to the implementation order)

After Phase 9 doc sweep, add **Phase 9c — diagram pass**:
- **Goal**: produce all `.mmd` source files, render PNGs, embed them, commit.
- **Model**: `sonnet-4-6` / **medium** effort. Mermaid is well-specified, sonnet-friendly.
- **Token efficiency**: load each doc + its diagram targets one at a time. ~25k tokens per batch.
- **Exit gate**:
  - `scripts/render_diagrams.sh` succeeds locally and in CI.
  - `git diff --exit-code docs/diagrams/*.png` clean after re-render.
  - Every doc in the inventory table contains a working `![alt](diagrams/<name>.png)` reference.
  - The "no raw mermaid block" CI grep passes.
  - Manual eyeball check of each PNG in a fresh GitHub preview of the PR: legible, no truncation, arrows visible.

### Folder structure addition

```
docs/
└── diagrams/                                         ** NEW directory **
    ├── architecture-dual-backend.mmd                 ** NEW source
    ├── architecture-dual-backend.png                 ** NEW rendered
    ├── coordinator-decision-flow.mmd                 **
    ├── coordinator-decision-flow.png                 **
    ├── auto-fallback-cache.mmd                       **
    ├── auto-fallback-cache.png                       **
    ├── install-flow.mmd                              **
    ├── install-flow.png                              **
    ├── settings-merge-decision.mmd                   **
    ├── settings-merge-decision.png                   **
    ├── auth-resolution.mmd                           **
    ├── auth-resolution.png                           **
    ├── backend-priority-matrix.mmd                   **
    ├── backend-priority-matrix.png                   **
    ├── request-lifecycle.mmd                         **
    ├── request-lifecycle.png                         **
    ├── streaming-flow.mmd                            **
    ├── streaming-flow.png                            **
    ├── async-live-flow.mmd                           **
    ├── async-live-flow.png                           **
    ├── test-coverage-matrix.mmd                      **
    ├── test-coverage-matrix.png                      **
    ├── phase-execution-timeline.mmd                  **
    └── phase-execution-timeline.png                  **
scripts/
└── render_diagrams.sh                                ** NEW helper (loops over *.mmd)
```

## Documentation update sweep (final phase, before PR)

After implementation + tests are green and the install flow is verified, do a full documentation pass. Every doc that references the old transport, install, or runtime model must be updated. This is **not** optional — the PR is not ready for review until docs match reality.

| Doc | What to update |
|---|---|
| **[README.md](README.md) (mandatory full pass)** | Quick Start: venv-based install model with `setup/install.py` creating `~/.claude/skills/gemini/.venv` and installing pinned `google-genai` from `setup/requirements.txt`. Update the "Where does my .env file go" section to point users at `~/.claude/settings.json` env block instead. Add a "Backends" section: by default `GEMINI_IS_SDK_PRIORITY=true` so SDK runs first and raw HTTP is the auto-fallback; flip the two priority flags to invert. Update the architecture diagram (or add one) to show adapters → coordinator → SDK/raw-HTTP. Update Python requirement to "Python 3.9+, plus `google-genai` installed automatically into the skill-local `.venv`". Remove every "zero runtime dependencies" / "stdlib only" claim. Update Quick Test command to use the venv interpreter. |
| **[SKILL.md](SKILL.md) (mandatory full pass — backend-agnostic instructions)** | (1) Invocation line MUST become `"${CLAUDE_SKILL_DIR}/.venv/bin/python" "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" <command> [args]`. (2) Frontmatter stays minimal — only `name`, `description`, `disable-model-invocation`. Do NOT add `allowed-tools` or `argument-hint`. (3) **Critical: every command and feature documented in SKILL.md must be backend-agnostic.** The instructions Claude Code reads must work identically whether the call routes through the SDK or raw HTTP. Concrete rules: never reference `google.genai`, `genai.Client`, `urllib`, `api_call`, or any backend-internal symbol in user-facing instructions. Always describe operations by capability name (`text`, `multimodal`, `embed`, `image_gen`, etc.) and the CLI flags they accept. (4) Add a one-paragraph "How transport works" section that explicitly tells Claude Code: "All commands route through `scripts/gemini_run.py` which dispatches to the right adapter. The adapter calls a single `api_call`/`stream_generate_content`/`upload_file` facade that picks the right backend automatically based on `GEMINI_IS_SDK_PRIORITY` / `GEMINI_IS_RAWHTTP_PRIORITY`. **You do not need to know which backend is active** — every command has identical behavior, identical output shape, and identical error format regardless." This is the load-bearing sentence that makes Claude Code stop trying to second-guess the transport. (5) Confirm the rules section still lists mutating-op `--execute` and privacy `--i-understand-privacy` gates (unchanged — those are dispatch-layer concerns, backend-independent). (6) The "Quick commands" list stays the same, and every example uses the canonical CLI form (no SDK or REST snippets ever). |
| **All 19 `reference/*.md` files (backend-agnostic pass — additive to the earlier reference table row)** | Beyond the venv-interpreter and "stdlib-only language removal" tasks already listed: every reference file must describe its capability **purely in terms of CLI flags, input shape, and output shape**, with **zero mention of which backend handles the call**. Specifically: (a) remove any "this calls `models/X:generateContent`" REST endpoint references — replace with capability-level descriptions ("Generates text from a prompt using the configured Gemini model"). (b) remove any `client.models.X` or `genai.Client(...)` SDK snippets — they don't belong in user docs. (c) remove any `urllib.request.urlopen` / "raw HTTP" mentions that leak the implementation. (d) For the four capabilities currently auto-fallback-routed (`maps`, `music_gen`, `computer_use`, `file_search`), the one-line "Routed via raw HTTP backend" note IS allowed because users may want to know about the limitation, but it must be in a "Notes" or "Implementation detail" subsection at the bottom — never in the main usage section. (e) The output shape examples must be the **normalized** envelope shape (the GeminiResponse TypedDict), since that's what users see whether SDK or raw HTTP ran. (f) Add a footer to every reference file: "Backend-agnostic: this command produces identical output via either the SDK or raw HTTP backend." This footer is the user-facing version of the SKILL.md load-bearing sentence — it tells Claude Code reading the reference file that there's nothing to disambiguate. |
| [docs/install.md](docs/install.md) | Full rewrite of the install steps: venv creation, `pip install -r setup/requirements.txt`, manual activation example (`source .venv/bin/activate`), troubleshooting for venv failures, "where does my .env file go", upgrade workflow (edit pin → re-run install). Replace any "stdlib only" claims. |
| [docs/architecture.md](docs/architecture.md) | New section: dual-backend transport. Diagram showing adapters → facade → coordinator → (SDK \| raw HTTP). Document the fallback eligibility rules. Document the runtime auto-fallback behavior for missing SDK surfaces (no registry field needed). |
| [docs/how-it-works.md](docs/how-it-works.md) | Update the request lifecycle walkthrough to show coordinator selection. |
| [docs/contributing.md](docs/contributing.md) | TDD requirement, 100% coverage gate on `core/transport/`, how to add a new capability (adapter + endpoint mapping in `SdkTransport`), how to bump the pinned `google-genai` version. |
| [docs/security.md](docs/security.md) | SDK trust boundary section: we trust `google-genai` to handle the wire format but we still validate inputs (mime type CRLF guard) and sanitize errors. Pinned-dependency rationale (supply chain). Note that the SDK is installed into an isolated venv, never system Python. |
| [docs/testing.md](docs/testing.md) | Document the 100% coverage gate, the parity test harness (`tests/transport/test_parity.py`), how to record new SDK fixtures, how to run live integration tests against each backend independently by flipping `GEMINI_IS_SDK_PRIORITY` / `GEMINI_IS_RAWHTTP_PRIORITY` env overrides, and how the live test fixture verifies which backend actually ran via the per-call marker file. |
| [docs/update-sync.md](docs/update-sync.md) | Pinned-version upgrade workflow: edit `setup/requirements.txt`, run `setup/install.py`, run live integration suite, open PR. |
| [docs/python-guide.md](docs/python-guide.md) | Python 3.9+ requirement reaffirmed; note that the skill no longer attempts Python 2.7 compat. Mention the venv interpreter. |
| [docs/usage.md](docs/usage.md) | Add a "Choosing a backend" subsection — most users never touch this; advanced users can set `primary_backend` in their config. |
| [docs/capabilities.md](docs/capabilities.md) | Note which capabilities are routed via raw HTTP at runtime due to missing SDK surfaces (currently `maps`, `music_gen`, `computer_use`, `file_search` per the parity audit; subject to change as the SDK ships new tool classes). |
| [docs/commands.md](docs/commands.md) | No content change unless command flags change; verify and update if dispatch.py adds anything. |
| [docs/model-routing.md](docs/model-routing.md) | Note that routing is unchanged but the resolved model now flows through the coordinator. |
| **All 19 `reference/*.md` files (mandatory venv + transport-mention sweep)** | Open every one of: [reference/text.md](reference/text.md), [reference/structured.md](reference/structured.md), [reference/multimodal.md](reference/multimodal.md), [reference/streaming.md](reference/streaming.md), [reference/embed.md](reference/embed.md), [reference/token_count.md](reference/token_count.md), [reference/function_calling.md](reference/function_calling.md), [reference/code_exec.md](reference/code_exec.md), [reference/search.md](reference/search.md), [reference/maps.md](reference/maps.md), [reference/image_gen.md](reference/image_gen.md), [reference/video_gen.md](reference/video_gen.md), [reference/music_gen.md](reference/music_gen.md), [reference/files.md](reference/files.md), [reference/cache.md](reference/cache.md), [reference/batch.md](reference/batch.md), [reference/file_search.md](reference/file_search.md), [reference/computer_use.md](reference/computer_use.md), [reference/deep_research.md](reference/deep_research.md), [reference/index.md](reference/index.md). For each: (1) update any invocation example to use the venv interpreter `${CLAUDE_SKILL_DIR}/.venv/bin/python`, (2) remove any "stdlib only / urllib" language, (3) verify the example commands still match the actual parser surfaces, (4) `index.md` adds a brief paragraph about the dual-backend transport with a link to `docs/architecture.md`. The detailed backend-agnostic content rules are in the row below. This is a mandatory file-by-file pass — every file gets opened, even if no change is needed. |
| `docs/planning/refactor-dual-backend-sdk-and-raw-http.md` | This plan, copied in pre-implementation step 6. Add a short closing paragraph after merge: "Implemented in PR #N, merged YYYY-MM-DD". |
| [.env.example](.env.example) | Rewrite per the dev-only template snippet earlier in the plan. Includes `GEMINI_IS_SDK_PRIORITY` and `GEMINI_IS_RAWHTTP_PRIORITY` as commented-out lines, plus all other env vars. Header explicitly says "local dev only — installed skill uses ~/.claude/settings.json instead". |

Verification of the doc sweep:
- `grep -rn "stdlib-only\|zero dependencies\|urllib" docs/ README.md SKILL.md` returns no stale claims.
- `grep -rn "python3 .*gemini_run.py" docs/ README.md SKILL.md` shows the venv interpreter path everywhere it appears in user-facing instructions.
- A reader who only reads `README.md` + `docs/install.md` can install the skill, configure their key, run a command, and understand which backend handled it — without reading the source.

## Outstanding TODOs converted to features

A scan of the repo (`grep -rn "TODO\|FIXME\|XXX\|HACK"`) finds two related TODOs in the docs that should be turned into actual features in this refactor. Both touch install/update integrity, which is doubly important now that the installer fetches `google-genai` from PyPI into a venv.

1. **Install-time file checksums** ([docs/security.md:303](docs/security.md#L303), [docs/update-sync.md:271](docs/update-sync.md#L271)).

   Implementation:
   - Add `core/infra/checksums.py` with `generate_checksums(root: Path) -> dict[str, str]` and `verify_checksums(root: Path, expected: dict[str, str]) -> list[str]` (returns list of mismatched files; empty list = success).
   - Release flow ([.github/workflows/release.yml](.github/workflows/release.yml)) generates `.checksums.json` covering every file copied by the installer (source code + `setup/requirements.txt`, but NOT user data like `.env` or the `.venv/`).
   - `core/cli/install_main.py` verifies checksums after copying files but before creating the venv. Mismatch → abort install with a clear error message and the list of mismatched paths. New install flag `--skip-checksum` for dev installs from a working tree.
   - `core/cli/update_main.py` verifies before applying updates; mismatch → refuses to update (the user's installed copy was tampered with or hand-edited).
   - `core/cli/health_main.py` reports checksum status: "ok" or "drift detected (N files)".
   - Tests: `tests/core/infra/test_checksums.py` (generate/verify happy and mismatch paths, missing file, extra file, byte-for-byte equality), and assertions in `test_install_main.py` / `test_update_main.py` for the integration.
   - Docs: update [docs/security.md](docs/security.md) — flip the TODO to "Implemented in PR #N". Update [docs/update-sync.md](docs/update-sync.md) — same.

2. **Pinned-dependency drift detection** (new TODO this refactor introduces, addressed up front).

   Implementation:
   - `core/cli/health_main.py` reads `setup/requirements.txt` and `~/.claude/skills/gemini/.venv/bin/python -m pip show google-genai`, asserts the installed version matches the pin, and reports drift.
   - `core/cli/update_main.py` refuses to run if the installed version drifts unexpectedly (someone manually `pip install --upgrade`d) — surfaces a clear message and asks the user to re-run `setup/install.py` to reset the pin.
   - Tests: `tests/core/cli/test_health_main.py` covers the drift detection path.

The "GPG Signatures (Future)" section in `docs/update-sync.md` stays as a future item — out of scope for this refactor, but the checksum work above is the prerequisite.

## Backfill `tests/scripts/` (currently empty)

[tests/scripts/](tests/scripts/) currently contains only `__init__.py` — no tests for the two scripts in [scripts/](scripts/): [scripts/gemini_run.py](scripts/gemini_run.py) and [scripts/health_check.py](scripts/health_check.py). This is a coverage gap that this refactor must close, because both scripts are about to gain new behavior:

- `gemini_run.py` gains the **venv re-exec logic** (detect not-in-venv → re-exec under `~/.claude/skills/gemini/.venv/bin/python` if it exists). This is exactly the kind of code that needs a unit test before it ships.
- `health_check.py` will be extended (or replaced by the upgraded `core/cli/health_main.py`) to report backend selection, venv path, pinned vs installed `google-genai` version, and the per-process list of capabilities the auto-fallback cache has marked as SDK-unavailable.

Add the following test files inside [tests/scripts/](tests/scripts/), all in the TDD loop alongside the rest of the implementation:

| New test file | What it covers |
|---|---|
| `tests/scripts/test_gemini_run.py` | (1) Python version guard rejects < 3.9; (2) `sys.path` includes the repo root before importing dispatch; (3) venv re-exec: when `sys.executable` is NOT the skill `.venv/bin/python` AND that venv path exists, the script `os.execv`s the venv interpreter; (4) when already running under the venv, no re-exec; (5) when the venv does not exist (e.g. dev mode in repo), runs as-is without re-exec; (6) Windows path resolution (`Scripts/python.exe`); (7) argv pass-through is exact (no quoting changes); (8) exits with the dispatch return code. Mock `os.execv`, `sys.executable`, `Path.exists`. |
| `tests/scripts/test_health_check.py` | The thin script launcher delegates to `core.cli.health_main.main()`; assert it imports correctly, calls `main()`, and propagates the exit code. Mock the import target. |

Both files target **100% line + branch coverage** on the script files themselves (they're tiny — ~30 lines each — so this is achievable). Coverage is enforced via the same `--cov-fail-under=100` gate as `core/transport/`.

These test files become part of the TDD workflow: write them at step 14 (the `scripts/gemini_run.py` re-exec implementation step) instead of after-the-fact.

## Verification

1. **Unit tests** (no network):
   - `pytest tests/transport/ -v` — all coordinator/policy/normalize/sdk/facade tests green.
   - `pytest tests/core/infra/test_client.py -v` — regression suite for raw HTTP passes after the move.
   - `pytest tests/adapters/ -v` — every adapter's existing tests still pass unchanged, proving the shim works.

2. **Install flow**:
   - `python3 setup/install.py` on a clean home → installer prints the venv python path and the installed `google-genai` version. Verify `~/.claude/skills/gemini/.venv/bin/python` exists, `~/.claude/skills/gemini/.venv/bin/pip show google-genai` returns a version, and `~/.claude/skills/gemini/.venv/bin/python -c "import google.genai"` exits 0.
   - `python3 setup/install.py` run twice → second run is idempotent, venv preserved, SDK upgraded in place (no recreation).
   - Sanity-activate manually: `source ~/.claude/skills/gemini/.venv/bin/activate && python -c "import google.genai" && deactivate` — must succeed, proving the venv is a valid activation target as well as a direct-invoke target.
   - Failure injection: pre-create a broken `.venv` directory and re-run install → installer detects the breakage, surfaces a clear error, and the config falls back to `primary_backend="raw_http"`.

3. **End-to-end live** (gated on `GEMINI_LIVE_TESTS=1`):
   - `~/.claude/skills/gemini/.venv/bin/python ~/.claude/skills/gemini/scripts/gemini_run.py text "hello"` with default config → succeeds via SDK backend.
   - Force SDK failure: set `primary_backend=sdk` in config, `pip uninstall google-genai` from the venv, re-run → falls back to raw HTTP, succeeds, health check reports SDK unavailable.
   - Force raw HTTP only end-to-end: flip both priority flags so raw HTTP is primary, then `pip uninstall google-genai` from the venv → SDK is unreachable as a fallback target, command runs entirely over raw HTTP, marker file confirms.
   - Set `primary_backend=raw_http` → runs via raw HTTP, SDK never imported.
   - `pytest tests/integration/ -v` — all 20 live smoke tests pass under the new primary (SDK) backend.

4. **SKILL.md invocation**: fully restart VSCode, run `/gemini text "hello"` → invocation goes through `.venv/bin/python`, confirmed via `ps` or by temporarily logging `sys.executable` in `gemini_run.py`.

## Critical files to open during implementation

- [core/infra/client.py](core/infra/client.py) — source of the raw HTTP code being moved
- [core/adapter/helpers.py](core/adapter/helpers.py) — response shape contract the normalize layer must match
- [core/infra/config.py](core/infra/config.py) — where backend config fields land
- [core/infra/errors.py](core/infra/errors.py) — error hierarchy extension
- [core/cli/install_main.py](core/cli/install_main.py) — venv + SDK install steps
- [SKILL.md](SKILL.md) — interpreter path
- [tests/core/infra/test_client.py](tests/core/infra/test_client.py) — regression anchor
- [adapters/generation/text.py](adapters/generation/text.py) — representative adapter; smoke-test that adapter-level tests still pass unchanged
