# maps

Ground text generation in Google Maps data. Opt-in (privacy-sensitive, mandatory output schema enforced).

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" maps "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--i-understand-privacy` — Required. Maps grounding sends queries to Google Maps and is gated by the dispatcher as privacy-sensitive.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `maps` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`.

## Examples

```bash
# Location search
gemini_run.py maps "Find restaurants in San Francisco with good reviews" --i-understand-privacy

# Navigation
gemini_run.py maps "Best route from downtown to the airport" --i-understand-privacy

# Local information
gemini_run.py maps "Coffee shops near me" --i-understand-privacy
```

## Output schema (mandatory)

Maps-grounded responses enforce an output schema:

```json
{
  "answer": "Natural language response",
  "sources": [
    {
      "title": "Business Name",
      "uri": "https://maps.google.com/maps?..."
    }
  ]
}
```

All sources must be formatted as `[title](uri)` markdown links. Requires trailing attribution: "Sources from Google Maps."

## Privacy note

Location queries are sent to Google Maps. User location may be inferred. Explicit opt-in required.

## Cost

Maps grounding adds per-request cost. Check pricing.

## Default model

`gemini-2.5-flash`.
