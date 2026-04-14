# cache

Manage Gemini context caching — create, list, retrieve, and delete cached content blocks.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" cache <subcommand> [args]
```

## Subcommands

- `create <content> [--ttl SECONDS]` — Create a new cache. **Mutating, requires `--execute`.**
- `list` — List all cached blocks.
- `get <cache_id>` — Retrieve cache metadata.
- `delete <cache_id>` — Delete a cache. **Mutating, requires `--execute`.**

## Flags

- `--ttl SECONDS` — Time-to-live for the cache (e.g., 3600 for 1 hour). Default: 3600.
- `--execute` — Confirm and execute `create` or `delete`.

## Examples

```bash
# Create a cache with content
gemini_run.py cache create "System prompt text" --ttl 7200 --execute

# List caches
gemini_run.py cache list

# Get cache details
gemini_run.py cache get "cache-abc123"

# Delete a cache
gemini_run.py cache delete "cache-abc123" --execute
```

## TTL (Time-to-Live)

Caches expire after the specified TTL in seconds. After expiry, the cache is deleted and cannot be reused.

## Use case

Use caching to reuse large context blocks (system prompts, documents, code) across multiple API calls and save tokens and latency.

## Default behavior

Without `--execute`, mutating subcommands (`create`, `delete`) print a dry-run message. Read-only subcommands (`list`, `get`) do not accept `--execute`.

## Output

List and get return JSON metadata. Create returns the cache ID and expiry time.

---

Backend-agnostic: this command produces identical output whether the SDK or raw HTTP backend handled the call.
