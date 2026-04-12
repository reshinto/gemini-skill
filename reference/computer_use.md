# computer_use

Enable computer use (preview). Model can capture screenshots, analyze UI, and simulate keyboard/mouse input. Privacy-sensitive, opt-in only.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" computer_use "task" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Simple UI navigation
gemini_run.py computer_use "Open a web browser and navigate to example.com"

# Automated task
gemini_run.py computer_use "Take a screenshot, identify the login form, and describe it"

# Screen analysis
gemini_run.py computer_use "What is the current state of my desktop?"
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

Gemini's specialized computer-use model.

## Limitations

- Desktop/GUI access only (no direct file system access in most cases)
- Input simulation is best-effort (some applications may not respond correctly)
- Screenshot capture depends on running display server
