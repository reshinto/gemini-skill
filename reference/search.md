# search

Ground text generation in real-time Google Search results. Privacy-sensitive, with dispatcher-managed opt-in.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" search "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `search` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`.
The dispatcher auto-applies the internal privacy opt-in flag for this command, so callers do not need to pass `--i-understand-privacy`.

## Examples

```bash
# Current events query
gemini_run.py search "What are the latest developments in quantum computing?"

# Up-to-date information
gemini_run.py search "Current Bitcoin price" --model gemini-2.5-pro

# News search
gemini_run.py search "Breaking news in space exploration"
```

## Privacy note

Search queries are sent to Google Search. Results are grounded in live search data. Consider user privacy before using.

## Latency

Search-grounded queries are slower (typically 2–5s extra) due to live search integration. Cache responses when possible.

## Cost

Search adds per-request cost on top of the base model call. Check pricing.

## Default model

`gemini-2.5-flash`.

## Flags (additional)

- `--show-grounding` — Emit JSON with grounding metadata instead of human-readable "Sources:" footer. Useful for downstream processing.

## Output

Response includes search results and the model's synthesis. Search sources may be cited in the output.

Without `--show-grounding`, output includes a human-readable "Sources from Google Search:" footer.
With `--show-grounding`, output is JSON with structured grounding metadata.

---

Currently served via the raw HTTP backend (SDK 1.33.0 does not expose this surface). Identical CLI and output.

---

[← Back](index.md) · [Previous: music_gen](music_gen.md) · [Next: streaming](streaming.md)
