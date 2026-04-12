# computer_use

Enable computer use (preview). Model can capture screenshots, analyze UI, and simulate keyboard/mouse input. Privacy-sensitive, opt-in only.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" computer_use "task" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--i-understand-privacy` — Required. Computer use is privacy-sensitive and gated by the dispatcher.
- `--session ID` — Start or continue a named session.
- `--continue` — Continue the most recent session.

The `computer_use` adapter accepts only the base flags above plus the `prompt` positional. It does **not** support `--system`, `--max-tokens`, or `--temperature`.

## Examples

```bash
# Simple UI navigation
gemini_run.py computer_use "Open a web browser and navigate to example.com" --i-understand-privacy

# Automated task
gemini_run.py computer_use "Take a screenshot, identify the login form, and describe it" --i-understand-privacy

# Screen analysis
gemini_run.py computer_use "What is the current state of my desktop?" --i-understand-privacy
```

## Privacy and security

Computer use requires explicit opt-in. The model can:
- Capture screenshots (see everything on screen)
- Simulate keyboard and mouse input
- Interact with running applications

**Caution:** Do not use with sensitive data visible on screen (passwords, personal info, financial data).

## Preview status

Computer use is a preview feature and may change. Model behavior and API surface are subject to revision.

## Default model

`gemini-3-flash-preview` (set as `default_model` for the `computer_use` capability in [registry/capabilities.json](../registry/capabilities.json)). The dedicated computer-use preview model `gemini-2.5-computer-use-preview-10-2025` is also registered and can be pinned with `--model`.

## Limitations

- Desktop/GUI access only (no direct file system access in most cases)
- Input simulation is best-effort (some applications may not respond correctly)
- Screenshot capture depends on running display server
