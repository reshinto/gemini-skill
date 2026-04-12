# code_exec

Execute Python code in Gemini's sandboxed code execution environment. Useful for calculations, data processing, and verification.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" code_exec "prompt with code request" [flags]
```

## Flags

- `--model MODEL` — Override the default model.
- `--system TEXT` — System instruction.
- `--max-tokens N` — Maximum output tokens.
- `--temperature F` — Sampling temperature 0.0–2.0 (default: 1.0).

## Examples

```bash
# Ask the model to write and execute code
gemini_run.py code_exec "Generate 100 random numbers and compute their mean"

# Complex data analysis
gemini_run.py code_exec "Load this CSV data and perform a statistical analysis"

# Verify a calculation
gemini_run.py code_exec "Compute the 100th Fibonacci number"
```

## Output

The model writes Python code (visible in response) and Gemini executes it, returning stdout/stderr and any computed values.

## Sandbox

Code runs in Google's sandboxed Python environment. No internet access, no file system persistence beyond the execution session, but standard library available.

## Default model

`gemini-2.5-flash`.

## Note

Code execution is non-mutating — it does not require `--execute`. The sandbox is isolated and safe.
