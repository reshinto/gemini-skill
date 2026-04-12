# maps

Ground text generation in Google Maps data. Opt-in (privacy-sensitive, mandatory output schema enforced).

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" maps "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Location search
gemini_run.py maps "Find restaurants in San Francisco with good reviews"

# Navigation
gemini_run.py maps "Best route from downtown to the airport"

# Local information
gemini_run.py maps "Coffee shops near me"
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
