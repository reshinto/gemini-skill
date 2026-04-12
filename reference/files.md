# files

Manage Gemini Files API — upload, list, retrieve, and delete files. Supports documents, media, and code.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" files <subcommand> [args] [--execute]
```

## Subcommands

- `upload <file_path>` — Upload a file. **Mutating, requires `--execute`.**
- `list` — List all uploaded files.
- `get <file_id>` — Retrieve metadata for a file.
- `delete <file_id>` — Delete a file. **Mutating, requires `--execute`.**

## Flags

- `--execute` — Confirm and execute the operation (mutating commands only).
- `--mime TYPE` — Override MIME type for upload.

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

# Delete a file
gemini_run.py files delete "fileId-12345" --execute
```

## Limits

- **File size:** 2GB per file, 20GB total.
- **Retention:** 48 hours after last use. Unused files are auto-deleted.
- **Formats:** PDFs, images, audio, video, text, code.

## Default behavior

Without `--execute`, mutating commands (`upload`, `delete`) print a dry-run message and exit. Use `--execute` to confirm.

## Output

List and get return JSON metadata. Upload returns the file ID and name.
