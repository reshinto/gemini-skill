# Testing — Unit Tests

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Unit tests cover `core/`, `adapters/`, `scripts/`, `setup/`, and `gemini_skill_install/` with a 100% line + branch coverage gate.

## Quick Start

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r setup/requirements.txt
pip install -r setup/requirements-dev.txt
```

### Run all tests

```bash
bash setup/run_tests.sh
```

Or directly:

```bash
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" tests/ -v \
  --cov=core --cov=adapters --cov-report=term-missing
```

### Run a specific test

```bash
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" tests/core/test_router.py -v
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" tests/gemini_skill_install/test_cli.py -v
```

### Check coverage

```bash
coverage report
coverage html  # Generate HTML report
open htmlcov/index.html
```

---

## Test Structure

```
tests/
├── core/
│   ├── test_auth.py           # Authentication (API key resolution)
│   ├── test_client.py         # HTTP client (requests, retries, streaming)
│   ├── test_dispatch.py       # CLI dispatch (whitelist, routing)
│   ├── test_router.py         # Model selection
│   ├── test_config.py         # Configuration loading
│   ├── test_state.py          # File locking, atomic writes
│   ├── test_cost.py           # Cost tracking
│   ├── test_mime.py           # MIME type detection
│   └── test_errors.py         # Error handling
├── adapters/
│   ├── generation/
│   │   ├── test_text.py       # Text generation (single & multi-turn)
│   │   ├── test_multimodal.py # File input
│   │   ├── test_structured.py # JSON schema output
│   │   └── test_streaming.py  # SSE streaming
│   ├── data/
│   │   ├── test_embeddings.py
│   │   ├── test_token_count.py
│   │   ├── test_files.py      # Files API (upload/list/get/delete)
│   │   ├── test_cache.py      # Context caching
│   │   ├── test_batch.py      # Batch processing
│   │   └── test_file_search.py# Hosted RAG
│   ├── tools/
│   │   ├── test_function_calling.py
│   │   ├── test_code_exec.py
│   │   ├── test_search.py
│   │   └── test_maps.py
│   ├── media/
│   │   ├── test_image_gen.py  # Mutating, requires --execute
│   │   ├── test_video_gen.py
│   │   └── test_music_gen.py
│   └── experimental/
│       ├── test_computer_use.py
│       └── test_deep_research.py
└── integration/              # Live smoke tests — opt-in, real API
    └── ...                   # See testing-integration.md
```

**Total:** 1,300+ tests, 100% coverage target on covered modules.

---

## Test Coverage Requirements

All code must have 100% test coverage:

```bash
.venv/bin/pytest -c setup/pytest.ini --rootdir="$(pwd)" tests/ \
  --cov=core --cov=adapters --cov-report=term-missing
```

Missing lines show as `MISSING` in the report.

**Policy:**
- No new code without tests
- Coverage gates on CI (blocks merge if < 100%)
- Uncovered lines must be marked `# pragma: no cover` with justification

---

## Writing Tests

### Test template

```python
"""Tests for core/infra/example.py."""
import pytest
from core.infra.example import function_to_test


class TestFunction:
    """Test suite for function_to_test."""

    def test_basic_case(self):
        """Test function with basic input."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test function with edge case."""
        with pytest.raises(ValueError):
            function_to_test("")

    def test_large_input(self):
        """Test function with large input."""
        result = function_to_test("x" * 10000)
        assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Mocking API calls

For adapters that call the API, mock `core.infra.client.api_call`:

```python
"""Tests for adapters/generation/text.py."""
from unittest.mock import patch, MagicMock
from adapters.generation import text


class TestTextAdapter:
    @patch("core.infra.client.api_call")
    def test_simple_text(self, mock_api_call):
        mock_api_call.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello!"}]}}]
        }
        parser = text.get_parser()
        args = parser.parse_args(["Hello"])
        with patch("core.infra.config.load_config") as mock_config:
            with patch("core.routing.router.Router") as mock_router:
                mock_config.return_value = MagicMock(
                    prefer_preview_models=False, output_dir="/tmp"
                )
                mock_router.return_value.select_model.return_value = "gemini-2.5-flash"
                text.run(**vars(args))
        mock_api_call.assert_called_once()
```

### Testing mutating operations

For mutating commands that require `--execute`:

```python
"""Tests for adapters/data/files.py."""
from unittest.mock import patch
from adapters.data import files


class TestFilesAdapter:
    def test_upload_dry_run(self):
        """Test that upload without --execute is a dry-run."""
        parser = files.get_parser()
        args = parser.parse_args(["upload", "file.txt"])
        with patch("core.infra.client.api_call") as mock_api:
            files.run(**vars(args))
            mock_api.assert_not_called()

    @patch("core.infra.client.api_call")
    def test_upload_with_execute(self, mock_api_call):
        """Test that upload with --execute actually runs."""
        mock_api_call.return_value = {"file": {"name": "files/xyz"}}
        parser = files.get_parser()
        args = parser.parse_args(["upload", "file.txt", "--execute"])
        files.run(**vars(args))
        mock_api_call.assert_called_once()
```

### Testing sessions

For multi-turn conversation tests, use a temporary directory and mock `SessionState`:

```python
"""Tests for adapters/generation/text.py (sessions)."""
from unittest.mock import patch
from pathlib import Path
import tempfile
from adapters.generation import text


class TestTextSessions:
    @patch("core.infra.client.api_call")
    def test_session_creation(self, mock_api_call):
        mock_api_call.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Response"}]}}]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            # mock SessionState to write into tmpdir
            parser = text.get_parser()
            args = parser.parse_args(["Hello", "--session", "test-chat"])
            # verify session file created via mocked SessionState
```

---

## Test Fixtures

Common fixtures (in `conftest.py`):

```python
import pytest, tempfile
from pathlib import Path
from unittest.mock import MagicMock

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.prefer_preview_models = False
    config.output_dir = tempfile.gettempdir()
    return config

@pytest.fixture
def mock_router():
    router = MagicMock()
    router.select_model.return_value = "gemini-2.5-flash"
    return router

@pytest.fixture
def mock_api_response():
    return {"candidates": [{"content": {"parts": [{"text": "Mocked response"}]}}]}

@pytest.fixture
def temp_session_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

---

## CI/CD Integration

The project uses GitHub Actions for CI (see `.github/workflows/ci.yml`). The pipeline runs `pytest` with `--cov` flags across `core/` and `adapters/`, uploads coverage to Codecov, then fails the build if coverage drops below 100%:

```yaml
- name: Fail if coverage < 100%
  run: coverage report --fail-under=100
```

Coverage gates on CI block merges if tests drop below 100%.

---

## Common Test Patterns

### Testing error handling

```python
def test_api_error_handling(self):
    """Test that API errors are handled gracefully."""
    with patch("core.infra.client.api_call") as mock_api:
        mock_api.side_effect = APIError(400, "Bad request")
        
        with pytest.raises(APIError) as exc_info:
            text.run(prompt="test")
        
        assert exc_info.value.status_code == 400
```

### Testing file operations

```python
def test_file_upload(self):
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write("test data"); f.flush()
        with patch("core.infra.client.api_call") as mock_api:
            mock_api.return_value = {"file": {"name": "files/xyz"}}
            args = files.get_parser().parse_args(["upload", f.name, "--execute"])
            files.run(**vars(args))
            mock_api.assert_called_once()
```

### Testing argument parsing

```python
def test_argument_validation(self):
    """Test that invalid arguments are rejected."""
    parser = text.get_parser()
    
    with pytest.raises(SystemExit):
        parser.parse_args(["--invalid-flag"])
```

---

## Performance Testing

For expensive operations, gate on elapsed wall time with a mocked API to avoid flakiness:

```python
def test_embedding_performance(self):
    import time
    with patch("core.infra.client.api_call") as mock_api:
        mock_api.return_value = {"embedding": {"values": [0.1] * 768}}
        start = time.time()
        for _ in range(10):
            embeddings.run(text="test")
        assert time.time() - start < 5.0  # < 5s for 10 iterations
```

---

## See also

- [testing.md](testing.md) — overview and quick commands
- [testing-integration.md](testing-integration.md) — live API matrix, `GEMINI_LIVE_TESTS`, backend parity, skip rules
- [testing-smoke.md](testing-smoke.md) — clean-install smoke, packaged install, upgrade path
- [contributing.md](contributing.md) — PR workflow
