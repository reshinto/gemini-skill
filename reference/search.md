# search

Ground text generation in real-time Google Search results. Opt-in (privacy-sensitive, adds latency and cost).

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" search "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--i-understand-privacy` — Required. Search grounding sends queries to Google and is gated by the dispatcher as privacy-sensitive.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `search` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`.

## Examples

```bash
# Current events query
gemini_run.py search "What are the latest developments in quantum computing?" --i-understand-privacy

# Up-to-date information
gemini_run.py search "Current Bitcoin price" --model gemini-2.5-pro --i-understand-privacy

# News search
gemini_run.py search "Breaking news in space exploration" --i-understand-privacy
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
