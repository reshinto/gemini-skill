#!/usr/bin/env bash
# Render every Mermaid source in docs/diagrams/ to a white-background SVG.
#
# Requirements: Node.js + @mermaid-js/mermaid-cli (installed via npx on demand).
# Output: deterministic SVG with forced white background so it renders legibly
# in both light and dark markdown viewers.
#
# Usage:
#   bash scripts/render_diagrams.sh            # render everything
#   bash scripts/render_diagrams.sh <name>     # render one (e.g. architecture-dual-backend)

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIAGRAMS_DIR="${REPO_ROOT}/docs/diagrams"

if ! command -v mmdc >/dev/null 2>&1; then
  # Fall back to npx so contributors without a global install still work.
  MMDC=(npx --yes @mermaid-js/mermaid-cli@10.9.1 mmdc)
else
  MMDC=(mmdc)
fi

render_one() {
  local mmd_path="$1"
  local svg_path="${mmd_path%.mmd}.svg"
  echo "[render] $(basename "$mmd_path") -> $(basename "$svg_path")"
  "${MMDC[@]}" \
    -i "$mmd_path" \
    -o "$svg_path" \
    -t default \
    -b white \
    -w 1600
}

if [ $# -gt 0 ]; then
  render_one "${DIAGRAMS_DIR}/$1.mmd"
else
  shopt -s nullglob
  for mmd in "${DIAGRAMS_DIR}"/*.mmd; do
    render_one "$mmd"
  done
fi

echo "[render] done"
