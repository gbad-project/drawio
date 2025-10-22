#!/usr/bin/env bash
#set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
cd ../../../../.. && bash src/main/webapp/plugins/rdfexport/legacy/scripts/run_regeneration.sh
# Test draw io parser patches applied for rdfexport plugin integration
cd src/main/webapp/plugins/rdfexport && pytest legacy/tests/ meta_builder/tests/
