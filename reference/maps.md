
# maps

Ground text generation in Google Maps data. Privacy-sensitive, with dispatcher-managed opt-in and a mandatory output schema.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" maps "prompt" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `maps` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`.
The dispatcher auto-applies the internal privacy opt-in flag for this command, so callers do not need to pass `--i-understand-privacy`.

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

Location queries are sent to Google Maps. User location may be inferred. Use only when the user intentionally asked for maps-grounded results.

## Cost

Maps grounding adds per-request cost. Check pricing.

## Default model

`gemini-2.5-flash`.

---

## Notes

Currently served via the raw HTTP backend (SDK 1.33.0 does not expose this surface). Identical CLI and output.

---

[← Back](index.md) · [Previous: live](live.md) · [Next: multimodal](multimodal.md)
