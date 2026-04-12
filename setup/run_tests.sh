#!/usr/bin/env bash
# Auto-setup venv + run tests. macOS/Linux only.
# Usage: ./setup/run_tests.sh [pytest args...]
# Example: ./setup/run_tests.sh -v -k test_auth

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
REQ_FILE="${REPO_ROOT}/setup/requirements-dev.txt"
PYTEST_INI="${REPO_ROOT}/setup/pytest.ini"

# Create venv if it doesn't exist
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    echo "Installing dev dependencies..."
    "${VENV_DIR}/bin/pip" install --quiet -r "${REQ_FILE}"
fi

# Run pytest with the project's config
exec "${VENV_DIR}/bin/pytest" -c "${PYTEST_INI}" --rootdir="${REPO_ROOT}" "$@"
