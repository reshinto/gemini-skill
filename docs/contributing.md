# Contributing

**Last Updated:** 2026-04-13

Guidelines for extending gemini-skill with new adapters and features.

## Architecture Overview

Before contributing, understand the architecture:

- **SKILL.md** — Skill manifest: `name`, `description`, `disable-model-invocation: true`, and the markdown body shown to the model when the user invokes `/gemini`. Note: `allowed-tools`, `argument-hint`, and `model` are slash-command-only frontmatter fields and must **not** appear in `SKILL.md` — the Claude Code skill loader silently rejects the file if they do (see [install.md](install.md) troubleshooting).
- **dispatch.py** — Policy boundary (whitelist, argument parsing, dry-run enforcement)
- **Adapters** — Modular command implementations (one file per command)
- **Router** — Model selection logic
- **Client** — HTTP wrapper (urllib, retries, SSE streaming)

See [architecture.md](architecture.md) for details.

---

## Adding a New Command

### Step 1: Create the adapter

Create a new file in `adapters/<category>/<command>.py`:

```python
"""New command adapter.

Brief description of what this command does.

Dependencies: core/infra/client.py, core/adapter/helpers.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser, emit_output
from core.infra.client import api_call
from core.infra.config import load_config


def get_parser():
    """Return the argument parser for this adapter."""
    parser = build_base_parser("Brief description of the command")
    parser.add_argument("prompt", help="Main input for the command")
    parser.add_argument(
        "--custom-flag", default=None,
        help="Optional custom flag"
    )
    return parser


def run(
    prompt: str,
    model: str | None = None,
    custom_flag: str | None = None,
    execute: bool = False,
    **kwargs: Any,
) -> None:
    """Execute the command.
    
    Args:
        prompt: Main input from user.
        model: Optional model override.
        custom_flag: Optional custom flag.
        execute: Include only for mutating commands or mutating subcommands.
        **kwargs: Additional arguments (session, continue, etc.).
    """
    # Check dry-run for mutating commands
    if check_dry_run(execute, "description of operation"):
        return
    
    # Load config
    config = load_config()
    
    # Select model
    router = Router(
        root_dir=Path(__file__).parent.parent.parent,
        prefer_preview=config.prefer_preview_models,
    )
    resolved_model = model or router.select_model("command_name")
    
    # Build request
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # ... other fields ...
    }
    
    # Call API
    response = api_call("endpoint", body=body)
    
    # Extract and emit response
    result = response["field"]["nested"]["value"]
    emit_output(result, output_dir=config.output_dir)
```

### Step 2: Register the command

Edit `core/cli/dispatch.py`:

```python
ALLOWED_COMMANDS: dict[str, str] = {
    # ... existing commands ...
    "my_command": "adapters.category.my_command",
}
```

### Step 3: Write tests

Create `tests/adapters/category/test_my_command.py`:

```python
"""Tests for adapters/category/my_command.py."""
import pytest
from unittest.mock import patch, MagicMock
from adapters.category import my_command


class TestMyCommand:
    """Test suite for my_command adapter."""

    def test_parser(self):
        """Test argument parsing."""
        parser = my_command.get_parser()
        args = parser.parse_args(["input", "--custom-flag", "value"])
        assert args.prompt == "input"
        assert args.custom_flag == "value"

    @patch("core.infra.client.api_call")
    def test_basic_execution(self, mock_api_call):
        """Test basic command execution."""
        mock_api_call.return_value = {
            "field": {"nested": {"value": "expected_output"}}
        }

        with patch("core.infra.config.load_config") as mock_config:
            with patch("core.routing.router.Router") as mock_router:
                mock_config.return_value = MagicMock(
                    prefer_preview_models=False,
                    output_dir="/tmp"
                )
                mock_router_instance = MagicMock()
                mock_router_instance.select_model.return_value = "gemini-2.5-flash"
                mock_router.return_value = mock_router_instance

                parser = my_command.get_parser()
                args = parser.parse_args(["test_input"])
                my_command.run(**vars(args))

        mock_api_call.assert_called_once()

    def test_dry_run(self):
        """Test that mutating commands are dry-run by default."""
        parser = my_command.get_parser()
        args = parser.parse_args(["test_input"])

        with patch("core.infra.client.api_call") as mock_api:
            my_command.run(**vars(args))
            mock_api.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

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

Each adapter should be under 500 lines. If longer, refactor:

```python
# DON'T: 800-line adapter with complex logic
def run(...):
    # 800 lines of code

# DO: Extract helper functions
def _build_request(...) -> dict:
    """Build API request."""

def _process_response(response) -> str:
    """Process API response."""

def run(...):
    body = _build_request(...)
    response = api_call(...)
    result = _process_response(response)
```

### SOLID Principles

- **S**ingle Responsibility: Adapters do one thing (one command)
- **O**pen/Closed: Easy to add new adapters without modifying existing ones
- **L**iskov: All adapters follow same interface (get_parser, run)
- **I**nterface Segregation: Adapters only use what they need
- **D**ependency Inversion: Adapters depend on abstractions (client, config) not implementations

### TDD (Test-Driven Development)

1. Write test first (red)
2. Write adapter (green)
3. Refactor (refactor)

All code must have tests before merge.

### Code organization

```python
"""Module docstring (brief description + dependencies)."""
from __future__ import annotations

# Imports (stdlib first, then local)
import argparse
import json
from pathlib import Path
from typing import Any

from core.adapter.helpers import build_base_parser
from core.infra.client import api_call

# Constants (uppercase)
DEFAULT_TIMEOUT = 30
SUPPORTED_FORMATS = frozenset({"json", "csv"})

# Functions (public first, then private)
def get_parser():
    """Return argument parser."""

def run(...):
    """Main entry point."""

def _helper_function():
    """Private helper (leading underscore)."""
```

### Type Hints

Use modern type hints (Python 3.9+):

```python
# Good
def api_call(
    endpoint: str,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Make an API call."""
```

Avoid:

```python
# Don't use old typing syntax
from typing import Dict, Optional
def api_call(endpoint: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```

---

## Error Handling

### Fail Closed

Always fail on ambiguity or missing data. Never proceed silently.

```python
# Good
if not config.api_key:
    raise AuthError("API key not found")

# Don't
if not config.api_key:
    print("Warning: API key not found, proceeding without auth")
```

### Custom Errors

Define errors in `core/infra/errors.py`:

```python
class MyAdapterError(Exception):
    """Raised when adapter encounters an error."""
```

Use domain-specific errors, not generic `Exception`.

### Error Messages

Include actionable remediation:

```python
# Good
raise CapabilityUnavailableError(
    f"Model '{model_id}' not found in registry. "
    f"Available models: {', '.join(available_models)}"
)

# Don't
raise CapabilityUnavailableError("Model not found")
```

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

Test both dry-run and execute paths:

```python
def test_dry_run(self):
    """Verify dry-run without --execute."""
    with patch("core.infra.client.api_call") as mock_api:
        my_command.run(..., execute=False)
        mock_api.assert_not_called()

def test_execute(self, mock_api_call):
    """Verify execution with --execute."""
    my_command.run(..., execute=True)
    mock_api_call.assert_called_once()
```

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

- [ ] No shell injection (no os.system, no shell=True)
- [ ] No hardcoded secrets
- [ ] No plaintext password prompts (use env vars)
- [ ] Input validation (file exists, path safe)
- [ ] Error messages don't leak sensitive data
- [ ] API key not logged anywhere
- [ ] File permissions for state files (mode 600)
- [ ] Atomic writes for state
- [ ] File locking for concurrent access

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
import pytest
from unittest.mock import patch, MagicMock
from adapters.generation import hello_world


class TestHelloWorld:
    """Test suite for hello_world adapter."""

    def test_parser(self):
        """Test argument parsing."""
        parser = hello_world.get_parser()
        args = parser.parse_args(["Alice"])
        assert args.name == "Alice"

    @patch("core.infra.client.api_call")
    def test_greeting(self, mock_api_call):
        """Test greeting generation."""
        mock_api_call.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Hello Alice!"}]}
            }]
        }

        with patch("core.infra.config.load_config") as mock_config:
            with patch("core.routing.router.Router") as mock_router:
                mock_config.return_value = MagicMock(
                    prefer_preview_models=False,
                    output_dir="/tmp"
                )
                mock_router_instance = MagicMock()
                mock_router_instance.select_model.return_value = "gemini-2.5-flash"
                mock_router.return_value = mock_router_instance

                parser = hello_world.get_parser()
                args = parser.parse_args(["Alice"])
                hello_world.run(**vars(args))

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

## Next Steps

- **Architecture:** [System design](architecture.md)
- **Testing:** [Testing guide](testing.md)
- **Code style:** [Python design](python-guide.md)
