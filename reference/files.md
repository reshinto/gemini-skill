# files

Manage Gemini Files API — upload, list, retrieve, download, and delete files. Supports documents, media, and code.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" files <subcommand> [args]
```

## Subcommands

- `upload <file_path>` — Upload a file. **Mutating, requires `--execute`.**
- `list` — List all uploaded files.
- `get <file_id>` — Retrieve metadata for a file.
- `download <file_id> <out_path>` — Download a file's bytes to a local path. **Mutating, requires `--execute`.**
- `delete <file_id>` — Delete a file. **Mutating, requires `--execute`.**

## Flags

- `--execute` — Confirm and execute `upload`, `download`, or `delete`.
- `--mime TYPE` — Override MIME type for upload.
- `--display-name NAME` — Display name for the uploaded file (upload subcommand only).

## Examples

```bash
# Upload a file (dry-run without --execute)
gemini_run.py files upload dataset.csv

# Actually upload
gemini_run.py files upload dataset.csv --execute

# List uploaded files
gemini_run.py files list

# Get file details
gemini_run.py files get "fileId-12345"

# Download file contents
gemini_run.py files download "fileId-12345" ./dataset.csv --execute

# Delete a file
gemini_run.py files delete "fileId-12345" --execute
```

## Limits

- **File size:** 2GB per file, 20GB total.
- **Retention:** 48 hours after last use. Unused files are auto-deleted.
- **Formats:** PDFs, images, audio, video, text, code.

## Default behavior

Without `--execute`, mutating subcommands (`upload`, `download`, `delete`) print a dry-run message and exit. Read-only subcommands (`list`, `get`) do not accept `--execute`.

## Output

List and get return JSON metadata. Upload returns the file ID and name. Download returns a JSON summary with the output path and size.

[← Back](index.md)
