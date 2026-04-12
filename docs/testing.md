# Testing

**Last Updated:** 2026-04-13

Running tests, writing new tests, and maintaining 100% coverage.

## Quick Start

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Run all tests

```bash
./run_tests.sh
```

Or directly:

```bash
pytest tests/ -v --cov=core --cov=adapters --cov-report=term-missing
```

### Run a specific test

```bash
pytest tests/core/test_router.py -v
pytest tests/adapters/generation/test_text.py::test_text_simple -v
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
└── integration/
    ├── test_e2e_text.py       # End-to-end text generation
    └── test_e2e_files.py      # End-to-end file operations
```

**Total:** 574 tests, 100% coverage.

---

## Test Coverage Requirements

All code must have 100% test coverage:

```bash
pytest tests/ --cov=core --cov=adapters --cov-report=term-missing
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
import pytest
from unittest.mock import patch, MagicMock
from adapters.generation import text


class TestTextAdapter:
    """Test suite for text generation adapter."""

    @patch("core.infra.client.api_call")
    def test_simple_text(self, mock_api_call):
        """Test basic text generation."""
        mock_api_call.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello!"}]
                }
            }]
        }

        # Create parser and run
        parser = text.get_parser()
        args = parser.parse_args(["Hello"])
        
        # Mock config and router
        with patch("core.infra.config.load_config") as mock_config:
            with patch("core.routing.router.Router") as mock_router:
                mock_config.return_value = MagicMock(
                    prefer_preview_models=False,
                    output_dir="/tmp"
                )
                mock_router_instance = MagicMock()
                mock_router_instance.select_model.return_value = "gemini-2.5-flash"
                mock_router.return_value = mock_router_instance
                
                # Run adapter
                text.run(**vars(args))

        # Verify API was called
        mock_api_call.assert_called_once()

    @patch("core.infra.client.api_call")
    def test_text_with_system_instruction(self, mock_api_call):
        """Test text generation with system instruction."""
        mock_api_call.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Concise response"}]
                }
            }]
        }

        parser = text.get_parser()
        args = parser.parse_args(["Prompt", "--system", "Be concise"])
        
        # ... similar setup ...
        
        # Verify system instruction was included in request
        call_args = mock_api_call.call_args
        assert call_args is not None
```

### Testing mutating operations

For mutating commands that require `--execute`:

```python
"""Tests for adapters/data/files.py."""
from unittest.mock import patch
from adapters.data import files


class TestFilesAdapter:
    """Test suite for Files API adapter."""

    def test_upload_dry_run(self):
        """Test that upload without --execute is a dry-run."""
        parser = files.get_parser()
        args = parser.parse_args(["upload", "file.txt"])
        
        # Should not call API
        with patch("core.infra.client.api_call") as mock_api:
            files.run(**vars(args))
            mock_api.assert_not_called()

    @patch("core.infra.client.api_call")
    def test_upload_with_execute(self, mock_api_call):
        """Test that upload with --execute actually runs."""
        mock_api_call.return_value = {"file": {"name": "files/xyz"}}
        
        parser = files.get_parser()
        args = parser.parse_args(["upload", "file.txt", "--execute"])
        
        # Should call API
        files.run(**vars(args))
        mock_api_call.assert_called_once()
```

### Testing sessions

For multi-turn conversation tests:

```python
"""Tests for adapters/generation/text.py (sessions)."""
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
from adapters.generation import text


class TestTextSessions:
    """Test suite for multi-turn conversations."""

    @patch("core.infra.client.api_call")
    def test_session_creation(self, mock_api_call):
        """Test that --session creates a new session."""
        mock_api_call.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Response"}]}
            }]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir)
            
            # ... mock SessionState to use tmpdir ...
            
            parser = text.get_parser()
            args = parser.parse_args(["Hello", "--session", "test-chat"])
            
            # Session file should be created
            # (verify via mocked SessionState)

    @patch("core.infra.client.api_call")
    def test_session_continuation(self, mock_api_call):
        """Test that --continue loads existing session."""
        # ... similar setup ...
        
        # Verify history is loaded and new message appended
```

---

## Test Fixtures

Common fixtures (in `conftest.py`):

```python
"""Pytest fixtures for all tests."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.prefer_preview_models = False
    config.output_dir = tempfile.gettempdir()
    return config


@pytest.fixture
def mock_router():
    """Mock model router."""
    router = MagicMock()
    router.select_model.return_value = "gemini-2.5-flash"
    return router


@pytest.fixture
def mock_api_response():
    """Mock Gemini API response."""
    return {
        "candidates": [{
            "content": {
                "parts": [{"text": "Mocked response"}]
            }
        }]
    }


@pytest.fixture
def temp_session_dir():
    """Temporary directory for session files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

---

## CI/CD Integration

The project uses GitHub Actions for CI (example `.github/workflows/test.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          python -m pip install -r requirements-dev.txt
      
      - name: Run tests
        run: |
          pytest tests/ -v --cov=core --cov=adapters --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
      
      - name: Fail if coverage < 100%
        run: |
          coverage report --fail-under=100
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
    """Test file upload adapter."""
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write("test data")
        f.flush()
        
        with patch("core.infra.client.api_call") as mock_api:
            mock_api.return_value = {"file": {"name": "files/xyz"}}
            
            parser = files.get_parser()
            args = parser.parse_args(["upload", f.name, "--execute"])
            files.run(**vars(args))
            
            # Verify file was read
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

For expensive operations:

```python
def test_embedding_performance(self):
    """Test embedding generation performance."""
    import time
    
    with patch("core.infra.client.api_call") as mock_api:
        mock_api.return_value = {
            "embedding": {"values": [0.1] * 768}
        }
        
        start = time.time()
        for _ in range(10):
            embeddings.run(text="test")
        elapsed = time.time() - start
        
        assert elapsed < 5.0  # Should complete in < 5s
```

---

## Running Tests in Production

Before deploying:

```bash
# Run all tests with coverage
./run_tests.sh

# Check coverage
coverage report --fail-under=100

# Lint and format check
ruff check core adapters scripts
black --check core adapters scripts

# Type check (if applicable)
mypy core adapters --strict
```

---

## Next Steps

- **Architecture:** [System design](architecture.md)
- **Contributing:** [Contributing guide](contributing.md)
- **Installation:** [Install guide](install.md)
