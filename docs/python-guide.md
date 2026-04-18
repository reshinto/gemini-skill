# Python Design Decisions

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-14

Python requirements and architectural decisions for gemini-skill.

## Python 3.9+ Requirement

The skill requires **Python 3.9 or higher**. This is enforced at launch in `scripts/gemini_run.py` with a readable error message.

### Why 3.9?

- Type hints with `dict[str, Any]` (PEP 585, lowercase generics) require 3.9+
- `from __future__ import annotations` allows modern type syntax in earlier syntax parsing (available 3.7+, but full modern syntax support is 3.9+)
- macOS ships Python 3.9+ by default (as of ~2021)
- Most Linux distros have 3.9 in standard repos
- Python 3.8 reached EOL in October 2024

### Mandatory Annotations Import

All new Python modules in the codebase **must** include this import at the top:

```python
from __future__ import annotations
```

This enables:
- `dict[str, Any]` instead of `Dict[str, Any]`
- `str | None` instead of `Optional[str]`
- Cleaner type hints aligned with Python 3.10+ syntax (but running on 3.9+)

### Runtime vs Development Venvs

**Runtime venv (end-users):**
```
~/.claude/skills/gemini/.venv/bin/python
```
- Managed by installer
- Pinned `google-genai==1.33.0` for SDK backend
- Small footprint (runtime deps only)
- Controlled by `setup/requirements.txt`

**Development venv (contributors):**
```
<repo>/.venv/bin/python
```
- Local to repository clone
- Full dev deps: `setup/requirements-dev.txt` (pytest, black, ruff, etc.)
- Used for local testing and CI
- Initialize with: `python3 -m venv .venv && source .venv/bin/activate && pip install -r setup/requirements-dev.txt`

---

## Python 3.9+ Floor

### Why 3.9?

```python
# Python 3.9 introduced:
# - dict | Union syntax (PEP 604) — NO, uses |
# - List[int] -> list[int] (PEP 585) — YES, lowercase generics
# - Decorator @ @ syntax (PEP 614) — NO

# We actually use 3.9 for:
# - Type hints (from __future__ import annotations) — works since 3.7
# - Union type (Optional[T], or T | None) — | syntax is 3.10+, so we use Optional
# - dict unpacking in type hints — 3.9+
```

The 3.9 floor is somewhat arbitrary but reflects:
- macOS ships Python 3.9+ by default (as of ~2021)
- Most Linux distros have 3.9 in standard repos
- Python 3.8 is EOL (Oct 2024)

To support older Python:
- Remove `from __future__ import annotations`
- Use `Optional[str]` instead of `str | None`
- Use `Dict` and `List` from `typing` instead of `dict` and `list`

### Version Check at Launch

```python
# scripts/gemini_run.py (2.7-compatible syntax)
if sys.version_info < (3, 9):
    sys.exit("gemini-skill requires Python 3.9+. Found: {}.{}".format(...))
```

This ensures even Python 2 gets a readable error message (not a SyntaxError on the next line).

---

## Python 3.13 Compatibility

### Current Issues

Python 3.13 removes `cgi.guess_type()` (deprecated in 3.11):

```python
# OLD (broken in 3.13)
from cgi import guess_type
mime_type = guess_type(filename)[0]

# NEW (Python 3.13+)
from mimetypes import guess_type
mime_type = guess_type(filename)[0]
```

Current code uses `mimetypes.guess_type()` (available since 3.3), so it's already compatible.

### Future Removals

Python 3.14+ may remove:
- `distutils` (already gone in 3.12)
- `pipes` module (use `shlex` instead)
- `asyncore` (we don't use)
- `smtpd` (we don't use)

The skill should remain compatible as long as we:
1. Use `urllib` instead of `http.client` (future-proof)
2. Use `mimetypes` instead of `cgi` (already done)
3. Avoid deprecated modules

### Testing on 3.13

```bash
python3.13 -m pytest tests/ --cov=core --cov=adapters
```

CI should test against multiple Python versions:
- 3.9 (floor)
- 3.10, 3.11, 3.12 (recent stable)
- 3.13 (current)

---

## stdlib Modules Used

### Network (urllib)

```python
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
```

The skill uses `urllib` (stdlib) for HTTP calls in the raw HTTP transport (`RawHttpTransport` in `core/transport/raw_http.py`). This provides full control over headers, timeouts, and multipart encoding without external dependencies.

**Advantages:**
- Stdlib, zero deps
- Full control over headers
- Timeout support

**Disadvantages:**
- More verbose (no `.json()` helper)
- No auto-retry (we implement)
- Manual multipart encoding

### JSON

```python
import json

config = json.loads(file_contents)
# Instead of: import yaml
```

All config and state files are JSON (no YAML) to avoid regex parsing.

### File I/O

```python
from pathlib import Path
import os

# Atomic write
temp_path = Path(temp_file)
temp_path.write_text(json.dumps(data))
os.replace(temp_file, dest_file)  # Atomic on POSIX and Windows
```

### Concurrency / Locking

```python
import fcntl  # POSIX
import msvcrt  # Windows

# Mutex for state files
with open(state_file, 'r+') as f:
    if hasattr(fcntl, 'flock'):
        fcntl.flock(f, fcntl.LOCK_EX)
    elif hasattr(msvcrt, 'locking'):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
```

Platform-specific imports handle file locking on POSIX and Windows.

### Crypto / Hashing

```python
import hashlib

checksum = hashlib.sha256(data).hexdigest()
```

Only used for integrity checking (not authentication). For auth, we use HTTP header.

### Regular Expressions

```python
import re

safe_mime = re.match(r'^[a-z]+/[a-z]+$', mime_type)
```

Minimal regex usage (only for MIME validation and ANSI stripping).

### Time

```python
import time
import datetime

timestamp = time.time()  # POSIX epoch, timezone-independent
today = datetime.date.today().isoformat()  # UTC date
```

All timestamps are POSIX epoch (seconds since 1970-01-01 UTC). Never use `datetime.now()` (affected by timezone).

### Temp Files

```python
import tempfile

temp_dir = tempfile.gettempdir()
temp_file = tempfile.NamedTemporaryFile(delete=False)
```

For media generation and large responses.

### Base64

```python
import base64

encoded = base64.b64encode(data).decode('utf-8')
decoded = base64.b64decode(encoded)
```

For multimodal input (inline files as base64) and media output.

### Command-line Parsing

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("prompt")
args = parser.parse_args()
```

Each adapter defines its own parser via `get_parser()`.

---

## Module Layout

### Entry Scripts

```
scripts/gemini_run.py       # 2.7-safe launcher, version check
setup/install.py            # Install handler
setup/update.py             # Update/sync handler
```

These scripts are **2.7-compatible syntax** so they can run on old Python and give a readable error.

### Core Modules

```
core/
├── cli/
│   ├── dispatch.py         # Subcommand routing (3.9+)
│   ├── install_main.py     # Setup logic
│   ├── update_main.py      # Sync logic
│   └── health_main.py      # Diagnostics
├── auth/
│   └── auth.py             # API key resolution
├── infra/
│   ├── client.py           # HTTP client
│   ├── config.py           # Config loading
│   ├── cost.py             # Cost tracking (file locking)
│   ├── errors.py           # Exception types
│   ├── mime.py             # MIME detection
│   ├── sanitize.py         # Safe print
│   ├── timeouts.py         # Timeout constants
│   ├── filelock.py         # Cross-platform locking
│   └── atomic_write.py     # Atomic file writes
├── routing/
│   ├── router.py           # Model selection
│   └── registry.py         # Model registry
├── state/
│   ├── session_state.py    # Multi-turn history
│   ├── file_state.py       # Files API tracking
│   └── store_state.py      # File Search state
└── adapter/
    ├── helpers.py          # Shared adapter utilities
    └── contract.py         # Adapter interface
```

All modules are 3.9+ (use modern syntax, type hints).

### Adapters

```
adapters/
├── generation/
├── data/
├── tools/
├── media/
└── experimental/
```

Each adapter is a simple module with `get_parser()` and `run(**kwargs)`.

---

## Type Hints

The codebase uses Python 3.9+ type hints with the mandatory `from __future__ import annotations` import:

```python
from __future__ import annotations
from typing import Any

def api_call(
    endpoint: str,
    body: dict[str, Any] | None = None,
    api_version: str = "v1beta",
) -> dict[str, Any]:
    """Make an API call."""
```

**All new code must use:**
- `dict[str, Any]` (lowercase generics, 3.9+ syntax)
- `str | None` (union syntax, available under `from __future__ import annotations`)
- The mandatory `from __future__ import annotations` at the module top

This ensures consistency across the codebase and leverages Python 3.9+ capabilities.

---

## Atomic Writes

State files (sessions, file tracking, cost) use atomic writes:

```python
# Read
with open(state_file, 'r') as f:
    data = json.load(f)

# Modify
data['cost'] += amount

# Atomic write (no partial writes on crash)
temp_file = state_file + '.tmp'
with open(temp_file, 'w') as f:
    json.dump(data, f)
os.replace(temp_file, state_file)  # Atomic swap
```

`os.replace()` is atomic on POSIX and Windows (though Windows may fail if antivirus holds a handle; we retry).

---

## File Locking

For concurrent access (Claude Code can parallelize tool calls):

```python
import fcntl

with open(state_file, 'r+') as f:
    fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
    data = json.load(f)
    data['cost'] += amount
    f.seek(0)
    json.dump(data, f)
    f.truncate()
    fcntl.flock(f, fcntl.LOCK_UN)  # Unlock
```

On Windows:

```python
import msvcrt

with open(state_file, 'r+') as f:
    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    # ... read/modify/write ...
    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
```

This prevents data corruption from concurrent reads/writes.

---

## String Handling

### Encoding

All text is Unicode (str in Python 3):

```python
# Read file as text
content = Path(filename).read_text(encoding='utf-8')

# Write file as text
Path(filename).write_text(content, encoding='utf-8')

# Binary operations
data = base64.b64encode(binary).decode('utf-8')
binary = base64.b64decode(base64_string.encode('utf-8'))
```

### ANSI Stripping

Safe print removes ANSI escape codes (no injection):

```python
def safe_print(text: str) -> None:
    """Remove ANSI sequences before printing."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    print(text)
```

---

## Performance Considerations

### asyncio (async adapters only)

19 of 23 adapters use synchronous I/O. The `live` adapter is the exception: it declares `IS_ASYNC = True` and implements `async def run_async()`. Dispatch detects this flag and calls `asyncio.run(adapter_module.run_async(**vars(args)))`.

**Rationale:**
- The Live API requires a persistent async bidirectional stream; synchronous urllib cannot model it
- All other adapters remain synchronous for simplicity
- No event-loop complexity for the common case

### Caching

Sessions and file state are cached in memory for the duration of a command:

```python
# Load once per command
session_state = SessionState(...)
history = session_state.get_history(session_id)

# Modify in memory
history.append(new_message)

# Write once at end
session_state.save(session_id, history)
```

No background caching layer needed.

---

## Testing on Multiple Python Versions

```bash
# Install multiple Python versions (macOS)
brew install python@3.9 python@3.10 python@3.11 python@3.12 python@3.13

# Run tests on each
python3.9 -m pytest tests/ -v
python3.10 -m pytest tests/ -v
python3.11 -m pytest tests/ -v
python3.12 -m pytest tests/ -v
python3.13 -m pytest tests/ -v
```

Or use `tox` (requires `pip`):

```toml
# tox.ini
[tox]
envlist = py39,py310,py311,py312,py313

[testenv]
commands = pytest tests/ -v --cov
```

---

## Code Style

### Formatting

```bash
# Black (code formatter)
black core adapters scripts

# Ruff (linter)
ruff check core adapters scripts
ruff check --fix core adapters scripts
```

### Type Checking

```bash
# Mypy (optional)
mypy core adapters --strict
```

Not required (no strict type checking), but recommended for new code.

---

## Future-Proofing

1. **Stay on stdlib:** Don't add external dependencies
2. **Test on 3.13:** Ensure compatibility with latest Python
3. **Avoid deprecated APIs:** Use `mimetypes` not `cgi`, `urllib` not `http.client`
4. **Pin minimum version:** `python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"`
5. **Document Python version requirements:** In README and INSTALL.md

---

## Next Steps

- **Architecture:** [System design](architecture.md)
- **Testing:** [Testing guide](testing.md)
- **Contributing:** [Contributing guide](contributing.md)
