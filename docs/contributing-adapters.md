# Contributing — Adapters & Commands

[← Back to Contributing](contributing.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

How to add a new command or adapter, wire it into the registry, document it, and test it.

## Architecture Overview

Before contributing, understand the architecture:

- **SKILL.md** — Skill manifest: `name`, `description`, `disable-model-invocation: true`, and the markdown body shown to the model when the user invokes `/gemini`. Note: `allowed-tools`, `argument-hint`, and `model` are slash-command-only frontmatter fields and must **not** appear in `SKILL.md` — the Claude Code skill loader silently rejects the file if they do (see [install.md](install.md) troubleshooting).
- **dispatch.py** — Policy boundary (whitelist, IS_ASYNC detection, argument parsing, dry-run enforcement)
- **Adapters** — Modular command implementations (one file per command, backend-agnostic via facade)
- **Transport** — Dual-backend coordinator (SDK primary + raw HTTP fallback, capability gate, fallback policy)
- **Router** — Model selection logic
- **Facade** (`core/transport/__init__.py`) — Unified API (api_call, stream_generate_content, upload_file)
- **Installer payload manifest** (`core/cli/installer/payload.py`) — Single source of truth for what the bootstrap package, clone installer, and release artifacts ship
- **Bootstrap installer package** (`gemini_skill_install/`) — `uvx` / `pipx` entry point that materializes the packaged payload and delegates to `install_main`

See [architecture.md](architecture.md) for details.

---

## Adding a New Command

### Step 1: Create the adapter

Create a new file in `adapters/<category>/<command>.py`. Adapters are **backend-agnostic** — they call `core.infra.client.api_call()` (a shim) or the new canonical import `from core.transport import api_call`. Both backends return identical `GeminiResponse` dict shapes.

Required structure:

```python
"""New command adapter.

Brief description. Dependencies: core/transport (facade), core/adapter/helpers.py
"""
from __future__ import annotations
from typing import Any
from core.adapter.helpers import build_base_parser, emit_output
from core.transport import api_call
from core.infra.config import load_config


def get_parser():
    parser = build_base_parser("Brief description")
    parser.add_argument("prompt", help="Main input")
    parser.add_argument("--custom-flag", default=None, help="Optional flag")
    return parser


def run(
    prompt: str,
    model: str | None = None,
    execute: bool = False,  # include only for mutating commands
    **kwargs: Any,
) -> None:
    if check_dry_run(execute, "description of operation"):
        return
    config = load_config()
    # select model, build body, call api_call(), emit_output()
```

See the full hello_world walkthrough below for a complete implementation.

### Step 2: Register the command

Edit `core/cli/dispatch.py`:

```python
ALLOWED_COMMANDS: dict[str, str] = {
    # ... existing commands ...
    "my_command": "adapters.category.my_command",
}
```

### Step 3: Write tests

Create `tests/adapters/category/test_my_command.py`. At minimum test: argument parsing, successful execution (mock `api_call`), and dry-run (mock not called without `--execute`). See the hello_world walkthrough below for a full example.

Ensure 100% coverage:

```bash
pytest tests/adapters/category/test_my_command.py -v --cov=adapters.category.my_command --cov-report=term-missing
```

### Step 4: Write reference documentation

Create `reference/my_command.md`:

```markdown
# my_command

Brief description.

## Usage

Command line syntax.

## Flags

- `--flag` — Description

## Examples

2–3 practical examples.

## Notes

Any special behavior or limitations.
```

Keep under 60 lines.

### Step 5: Update SKILL.md (if public-facing)

If the command is user-facing, add a brief note to `SKILL.md`:

```markdown
## Quick commands

- ...
- `my_command "input"` — do something
```

---

## Code Style & Standards

### 500-line limit

Each adapter should be under 500 lines. If longer, extract `_build_request()`, `_process_response()`, and other helpers — keep `run()` as a thin coordinator.

### SOLID Principles

- **S**ingle Responsibility: Adapters do one thing (one command)
- **O**pen/Closed: Easy to add new adapters without modifying existing ones
- **L**iskov: All adapters follow same interface (get_parser, run)
- **I**nterface Segregation: Adapters only use what they need
- **D**ependency Inversion: Adapters depend on abstractions (facade, config) not implementations

### TDD + 100% Coverage (MANDATORY)

1. Write test first (red)
2. Write adapter (green)
3. Refactor (refactor)
4. Verify 100% coverage: `pytest --cov=<module> --cov-branch --cov-fail-under=100`

**Policy:** Every new module under `core/transport/`, every new adapter, every new `core/infra/` file, every modified install/update/health module must hit 100% line + branch coverage. No `# pragma: no cover` on new code.

### Strict Typing (MANDATORY)

New code uses **mypy --strict** and NO `Any`:
```python
from __future__ import annotations
from typing import TypedDict, Protocol, Union, TypeVar
from dataclasses import dataclass
```

Use `TypedDict`, `Protocol`, `dataclass`, `Union`, `TypeVar` instead of `Any`.

### Code organization

Module layout: docstring → `from __future__ import annotations` → stdlib imports → local imports → UPPER_CASE constants → `get_parser()` → `run()` → private helpers (`_name`).

### Type Hints

Use Python 3.9+ syntax: `dict[str, Any]`, `str | None`. Avoid legacy `Dict`, `Optional` from `typing`.

## Error Handling

### Fail Closed

Always raise on ambiguity or missing data — never proceed silently (no `print("Warning: ...")`).

### Custom Errors

Define adapter-specific errors in `core/infra/errors.py`. Use domain-specific subclasses, not bare `Exception`.

### Error Messages

Include actionable remediation — report which value was bad and what the valid options are.

---

## Mutating Operations

Commands that modify server state require `--execute` flag:

- Upload, delete, create
- Generate (images, videos, music)
- Batch submit, cache create
- File Search mutations

```python
def run(..., execute: bool = False, ...):
    # Check dry-run
    if check_dry_run(execute, "description of operation"):
        return  # Dry-run: print message and exit
    
    # Now safe to proceed with mutation
    api_call(...)
```

Test both paths: `execute=False` → `api_call` not called; `execute=True` → called once.

---

## Registry Updates

If adding a new model or capability, update `registry/models.json`:

```json
{
  "models": [
    {
      "id": "new-model",
      "display_name": "New Model",
      "capabilities": ["text", "multimodal"],
      "preview": false,
      "deprecated": false,
      "default_for": []
    }
  ]
}
```

Update model defaults for specialty tasks:

```json
{
  "capabilities": {
    "my_task": {
      "default_model": "new-model"
    }
  }
}
```

---

## Adding a New Capability

1. Write failing test in `tests/adapters/<category>/test_<cmd>.py`
2. Implement adapter in `adapters/<category>/<cmd>.py` (backend-agnostic)
3. Register in `registry/capabilities.json`
4. If SDK supports it, add to `_SUPPORTED_CAPABILITIES` in `core/transport/sdk/transport.py`
5. Add endpoint mapping to `SdkTransport.api_call()` if SDK-specific
6. Create reference doc at `reference/<cmd>.md` (< 60 lines)
7. Test: `pytest tests/adapters/<category>/test_<cmd>.py --cov=adapters.<category>.<cmd> --cov-fail-under=100`

---

## Documentation

Every new command must include:

1. **Adapter docstring** (what it does, dependencies)
2. **Argument help** (in get_parser())
3. **Reference file** (reference/<command>.md, < 60 lines)
4. **Example usage** (in reference file)

Example docstring:

```python
"""Image generation adapter — Nano Banana family.

Generates images from text prompts using the Nano Banana model.
Output is always saved to file (never stdout).

Mutating — requires --execute.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
```

---

## Testing Requirements

All code must have **100% test coverage**:

```bash
pytest tests/ --cov=core --cov=adapters --cov-report=term-missing
coverage report --fail-under=100
```

Uncovered lines (rare exceptions) must be marked:

```python
# pragma: no cover
raise SystemExit("Should never reach here")
```

---

## Performance Considerations

### Timeouts

All network calls have explicit timeouts:

```python
response = api_call(..., timeout=30)
```

Default: 30 seconds. Streaming may need longer.

### File Size Limits

Enforce reasonable limits:

```python
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

if file_size > MAX_FILE_SIZE:
    raise ValueError(f"File exceeds 2GB limit")
```

### Large Response Guard

Auto-save responses > 50KB to file:

```python
if len(response) > 50_000:
    output_path = _save_to_file(response)
    emit_json({"path": str(output_path)})
else:
    emit_output(response)
```

---

## Security Checklist

- [ ] No shell injection (avoid subprocess with shell=True; never pass user input unsanitised to a shell)
- [ ] No hardcoded secrets
- [ ] No plaintext password prompts (use env vars)
- [ ] Input validation (file exists, path safe)
- [ ] Error messages don't leak sensitive data
- [ ] API key not logged anywhere
- [ ] File permissions for state files (mode 600)
- [ ] Atomic writes for state
- [ ] File locking for concurrent access

---

## Example: Adding a "hello_world" command

### 1. Create adapter

File: `adapters/generation/hello_world.py`

```python
"""Hello world adapter — simple greeting command."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser():
    """Return the argument parser."""
    parser = build_base_parser("Say hello")
    parser.add_argument("name", help="Name to greet")
    return parser


def run(
    name: str,
    model: str | None = None,
    **kwargs: Any,
) -> None:
    """Greet someone using Gemini."""
    from core.routing.router import Router

    config = load_config()
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("text")

    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": f"Say a brief friendly greeting to {name}"}]
        }]
    }

    response = api_call(f"models/{resolved_model}:generateContent", body=body)
    text = response["candidates"][0]["content"]["parts"][0]["text"]
    emit_output(text, output_dir=config.output_dir)
```

### 2. Register command

Edit `core/cli/dispatch.py`:

```python
ALLOWED_COMMANDS: dict[str, str] = {
    # ... existing ...
    "hello_world": "adapters.generation.hello_world",
}
```

### 3. Write tests

File: `tests/adapters/generation/test_hello_world.py`

```python
"""Tests for hello_world adapter."""
from unittest.mock import patch, MagicMock
from adapters.generation import hello_world


class TestHelloWorld:
    def test_parser(self):
        parser = hello_world.get_parser()
        args = parser.parse_args(["Alice"])
        assert args.name == "Alice"

    @patch("core.infra.client.api_call")
    def test_greeting(self, mock_api_call):
        mock_api_call.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello Alice!"}]}}]
        }
        with patch("core.infra.config.load_config") as mock_config:
            with patch("core.routing.router.Router") as mock_router:
                mock_config.return_value = MagicMock(
                    prefer_preview_models=False, output_dir="/tmp"
                )
                mock_router.return_value.select_model.return_value = "gemini-2.5-flash"
                hello_world.run(**vars(hello_world.get_parser().parse_args(["Alice"])))
        mock_api_call.assert_called_once()
```

Run tests: `pytest tests/adapters/generation/test_hello_world.py -v`

### 4. Create reference doc

File: `reference/hello_world.md`

```markdown
# hello_world

Greet someone using Gemini.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" hello_world "name" [--model model]
```

## Flags

- `--model MODEL` — Override the default model.

## Examples

```bash
gemini_run.py hello_world "Alice"
gemini_run.py hello_world "Bob" --model gemini-2.5-pro
```

## Default model

`gemini-2.5-flash`.
```

### 5. Test & submit

```bash
pytest tests/ -v --cov
coverage report --fail-under=100
black core adapters scripts
/gemini hello_world "Test"
```

---

## See also

- [contributing.md](contributing.md) — overview and principles
- [contributing-workflow.md](contributing-workflow.md) — PR workflow, commit style, pre-push hook, release tagging
- [architecture.md](architecture.md) — module map
- [testing-unit.md](testing-unit.md) — unit test patterns
- [reference/index.md](../reference/index.md) — reference pages index
