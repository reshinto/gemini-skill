# deep_research

Conduct deep research using Gemini's Interactions API (not generateContent). Asynchronous, privacy-sensitive, server-stored, with resumption support.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" deep_research "research query" [--resume id] [--max-wait seconds] --execute
```

## Flags

- `--resume ID` — Resume a previous research session by ID.
- `--max-wait SECONDS` — Maximum wait time for polling (default: 300).
- `--execute` — Confirm and start. **Mutating, required.**
- `--model MODEL` — Override the default model.

The dispatcher auto-applies the internal privacy opt-in flag for this command, but `--execute` is still required because starting or resuming research is mutating.

## Examples

```bash
# Start a new research task
gemini_run.py deep_research "Analyze the impact of renewable energy on global markets" --execute

# Resume research in progress
gemini_run.py deep_research --resume "research-abc123" --execute

# Custom wait time
gemini_run.py deep_research "Comprehensive review of AI safety literature" --max-wait 900 --execute
```

## How it works

Deep Research uses Gemini's Interactions API (background=true) for long-running, stateful research. Results are stored server-side, not in local sessions.

## Storage and retention

- **Paid accounts:** Results stored for 55 days.
- **Free accounts:** Results stored for 1 day.

After retention expires, the research cannot be resumed.

## Output

Returns JSON with research ID, status, and findings:

```json
{
  "id": "research-xyz789",
  "status": "completed",
  "summary": "Research findings...",
  "duration_seconds": 45
}
```

## Default behavior

Without `--execute`, prints dry-run. Use `--execute` to start.

## Typical duration

Deep research takes 30–120 seconds depending on query complexity.

## Note

Deep Research is designed for thorough, multi-step investigation. Simpler queries may be faster with regular `text` command.
