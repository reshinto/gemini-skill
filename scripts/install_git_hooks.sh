#!/usr/bin/env bash
#
# Install local git hooks for the gemini-skill repo.
#
# Run this once after cloning:
#     bash scripts/install_git_hooks.sh
#
# The hooks live under .git/hooks/ and are NOT version-controlled. This
# bootstrap script is the canonical installer; running it twice is idempotent.
#
# Hooks installed:
#   pre-push:
#     Auto-formats every tracked Python file with black before allowing a
#     push. If black changes anything, the hook stages the changes, creates
#     a "style(format): auto-format with black via pre-push hook" commit,
#     and BLOCKS the push (exit 1) so the user re-runs `git push` and the
#     formatting commit gets included. The hook is per-machine and reads
#     the pinned black version from the repo-root .venv.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
  echo "ERROR: $HOOKS_DIR does not exist. Are you running this from a git checkout?" >&2
  exit 1
fi

PRE_PUSH="$HOOKS_DIR/pre-push"

cat > "$PRE_PUSH" <<'HOOK_EOF'
#!/usr/bin/env bash
# Pre-push hook: auto-format Python with black; if anything changed, stage,
# commit, and block the push so the user re-pushes with the formatting commit
# included. Installed by scripts/install_git_hooks.sh.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Activate the dev venv so we use the pinned black version from
# setup/requirements-dev.txt. If the venv is missing, warn and skip
# (don't block pushes for contributors who haven't run pre-impl step 6 yet).
if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
else
  echo "[pre-push] WARNING: dev .venv not found at $REPO_ROOT/.venv — skipping black format pass"
  exit 0
fi

if ! command -v black >/dev/null 2>&1; then
  echo "[pre-push] ERROR: black not installed in dev venv. Run: pip install -r setup/requirements-dev.txt" >&2
  exit 1
fi

echo "[pre-push] Running black on tracked Python files..."

# Collect tracked Python files. We format the whole tree (not just the diff)
# so we never push a half-formatted commit.
mapfile -t PY_FILES < <(git ls-files '*.py')
if [ ${#PY_FILES[@]} -eq 0 ]; then
  echo "[pre-push] No Python files tracked — skipping."
  exit 0
fi

if ! black --line-length 100 --target-version py313 "${PY_FILES[@]}"; then
  echo "[pre-push] ERROR: black failed (syntax error?)" >&2
  exit 1
fi

# If black modified anything, create a formatting commit and block the push.
if ! git diff --quiet; then
  echo "[pre-push] black reformatted some files — staging and committing..."
  git add -u
  git commit -m "style(format): auto-format with black via pre-push hook"
  echo ""
  echo "[pre-push] A formatting commit was created. Re-run 'git push' to push it."
  echo "[pre-push] (The push you just attempted has been blocked so the new commit is included.)"
  exit 1
fi

echo "[pre-push] black: no changes needed."
exit 0
HOOK_EOF

chmod +x "$PRE_PUSH"
echo "Installed pre-push hook at $PRE_PUSH"
