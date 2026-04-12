# search

Ground text generation in real-time Google Search results. Opt-in (privacy-sensitive, adds latency and cost).

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" search "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

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

## Output

Response includes search results and the model's synthesis. Search sources may be cited in the output.
