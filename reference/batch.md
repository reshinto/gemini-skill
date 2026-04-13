# batch

Submit and manage batch jobs — create, list, retrieve, and cancel. Process multiple requests efficiently.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" batch <subcommand> [args]
```

## Subcommands

- `create --src INPUT --dest OUTPUT` — Create a batch job. **Mutating, requires `--execute`.**
- `list` — List all batch jobs.
- `get <batch_id>` — Retrieve batch metadata and status.
- `cancel <batch_id>` — Cancel a running batch. **Mutating, requires `--execute`.**

## Flags

- `--src FILE` — Input JSONL file (batch requests).
- `--dest FILE` — Output file path for results.
- `--execute` — Confirm and execute `create` or `cancel`.

## Examples

```bash
# Create a batch job
gemini_run.py batch create --src requests.jsonl --dest results.jsonl --execute

# List all batch jobs
gemini_run.py batch list

# Check batch status
gemini_run.py batch get "batch-xyz789"

# Cancel a batch
gemini_run.py batch cancel "batch-xyz789" --execute
```

## Input format (JSONL)

Each line is a JSON request:

```json
{"custom_id": "req-1", "params": {"contents": [{"role": "user", "parts": [{"text": "Prompt 1"}]}]}}
{"custom_id": "req-2", "params": {"contents": [{"role": "user", "parts": [{"text": "Prompt 2"}]}]}}
```

## Output format (JSONL)

Results are written as JSONL with same custom_ids:

```json
{"custom_id": "req-1", "result": {"content": [...]}}
```

## Default behavior

Without `--execute`, mutating subcommands (`create`, `cancel`) print dry-run messages. Read-only subcommands (`list`, `get`) do not accept `--execute`.

## Note

Batch jobs are long-running and asynchronous. Check status regularly with `get`.
