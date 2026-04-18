# file_search

Manage File Search stores (Gemini's hosted RAG). Create stores, import files by Gemini file URI, query them, list, and delete.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" file_search <subcommand> [args]
```

## Subcommands

- `create <name>` — Create a new store. The positional `<name>` is the display name for the store. **Mutating, requires `--execute`.**
- `upload <store> <file_uri>` — Import a file into a store. **The `<file_uri>` is a Gemini `files/...` resource URI**, not a local file path — you must first upload the local file via `files upload ... --execute` and use the returned URI here. **Mutating, requires `--execute`.**
- `query <prompt> --store <store>` — Search a store with a natural-language query. The query is the positional argument; `--store <name>` identifies the store to search.
- `list` — List all stores.
- `delete <name>` — Delete a store by its resource name. **Mutating, requires `--execute`.**

## Flags

Only the shared base flags are supported:

- `--model MODEL` — Override the default model used for the `query` subcommand.
- `--execute` — Confirm and execute the operation (required for `create`, `upload`, `delete`).
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `file_search` adapter does **not** support `--poll-interval` or `--max-wait`; those flags exist on `video_gen` and `deep_research` but not here.

## Examples

```bash
# 1. Create a store
gemini_run.py file_search create "research-library" --execute

# 2. Upload a local file via the files API first, capture the file URI
gemini_run.py files upload ./research.pdf --execute
# → returns something like {"name": "files/abc123xyz", ...}

# 3. Import that file URI into the store
gemini_run.py file_search upload "fileSearchStores/<store-id>" "files/abc123xyz" --execute

# 4. Query the store
gemini_run.py file_search query "What are the key findings?" --store "fileSearchStores/<store-id>"

# 5. List / delete
gemini_run.py file_search list
gemini_run.py file_search delete "fileSearchStores/<store-id>" --execute
```

Default model: `gemini-2.5-flash-lite`. Currently served via the raw HTTP backend (SDK 1.33.0 does not expose this surface).

## Default behavior

Without `--execute`, mutating subcommands (`create`, `upload`, `delete`) print a dry-run message and exit 0 — no API call is made. Read-only subcommands (`query`, `list`) do not accept `--execute`.

## Use case

File Search is Gemini's hosted RAG. Upload documents once, then run grounded queries against them without sending file content on every request.

[← Back](index.md)
