# file_search

Manage File Search stores (hosted RAG). Create, upload documents, query, list, and delete stores. Long-running operations require polling.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" file_search <subcommand> [args] [--execute]
```

## Subcommands

- `create` — Create a new file search store. **Mutating, requires `--execute`.**
- `upload <store_id> <file>` — Add a file to a store. **Mutating, requires `--execute`.**
- `query <store_id> "query"` — Search documents in a store.
- `list` — List all stores.
- `delete <store_id>` — Delete a store. **Mutating, requires `--execute`.**

## Flags

- `--execute` — Confirm and execute the operation (mutating commands only).
- `--poll-interval SECONDS` — Polling interval for long-running ops (default: 2).
- `--max-wait SECONDS` — Maximum wait time (default: 300).

## Examples

```bash
# Create a store
gemini_run.py file_search create --execute

# Upload a document to the store
gemini_run.py file_search upload "store-id-123" research.pdf --execute

# Query the store
gemini_run.py file_search query "store-id-123" "What are the key findings?"

# List all stores
gemini_run.py file_search list

# Delete a store
gemini_run.py file_search delete "store-id-123" --execute
```

## Long-running operations

File uploads and store operations are asynchronous. The command polls for completion (default: 2s interval, 300s max wait).

## Default behavior

Without `--execute`, mutating commands print dry-run messages. Use `--execute` to confirm.

## Use case

File Search is Gemini's hosted RAG. Upload documents once, then query them repeatedly without sending file content in every request.

## Output

Create returns store ID. Query returns matching documents. List returns all stores with metadata.
