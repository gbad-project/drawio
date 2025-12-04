#!/usr/bin/env bash
#set -euo pipefail

# ────────────────────────────────────────────────
# 🚀 Entry Point for Master Test/Debug Pipeline
# This script runs first under `bun run:test:all`
# ────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_ACTIVATE="${ROOT_DIR}/.venv/bin/activate"

if [[ -f "${VENV_ACTIVATE}" ]]; then
  # Ensure Python commands (meta builder, pytest, etc.) resolve against the
  # project virtual environment provisioned by `bun run setup:uv`.
  # This keeps rdflib and the rest of the synced dependencies available when
  # the test harness shells out through Bun.
  # shellcheck source=/dev/null
  source "${VENV_ACTIVATE}"
fi

cd "${ROOT_DIR}"

# Rebuild legacy draw io parser from meta builder
bun run build:py
# Produce reliable, original draw io parser output artifacts
bash python_core/scripts/run_regeneration.sh
# Test draw io parser patches applied for rdfexport plugin integration
pytest -rA aicode/python_core/tests/ python_core/tests/
