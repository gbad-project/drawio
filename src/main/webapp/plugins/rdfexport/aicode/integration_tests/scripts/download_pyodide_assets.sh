#!/usr/bin/env bash
set -euo pipefail

VERSION="0.28.3"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET_DIR="${ROOT_DIR}/.pyodide"
ARCHIVE="pyodide-${VERSION}.tar.bz2"
ARCHIVE_URL="https://github.com/pyodide/pyodide/releases/download/${VERSION}/${ARCHIVE}"
WHEEL_FILE="rdflib-7.4.0-py3-none-any.whl"
WHEEL_URL="https://files.pythonhosted.org/packages/18/ea/30bd9eb0d4a25dd0ab929153ed23698c907c6124389aa72eea5b7b703ab8/${WHEEL_FILE}"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

# Check if Pyodide is already downloaded
if [[ -f "${TARGET_DIR}/pyodide.js" && -f "${TARGET_DIR}/pyodide.asm.js" ]]; then
  echo "[rdfexport] Pyodide ${VERSION} already exists, skipping download..."
else
  mkdir -p "${TARGET_DIR}"

  echo "[rdfexport] Downloading Pyodide ${VERSION} archive..."
  curl -L "${ARCHIVE_URL}" -o "${TMP_DIR}/${ARCHIVE}"

  echo "[rdfexport] Extracting archive..."
  tar -xjf "${TMP_DIR}/${ARCHIVE}" -C "${TMP_DIR}"

  # Updated: pyodide archive now extracts into "pyodide" or "pyodide-${VERSION}"
  SOURCE_DIR="$(find "${TMP_DIR}" -maxdepth 2 -type d -name 'pyodide' | head -n1)"
  if [[ -z "${SOURCE_DIR}" ]]; then
    echo "[rdfexport] Pyodide directory not found" >&2
    exit 1
  fi

  echo "[rdfexport] Syncing assets into ${TARGET_DIR}"
  rm -rf "${TARGET_DIR}"
  mkdir -p "${TARGET_DIR}"
  cp -a "${SOURCE_DIR}/." "${TARGET_DIR}/"
fi

# Check if rdflib wheel is already downloaded
if [[ -f "${TARGET_DIR}/wheels/${WHEEL_FILE}.base64" ]]; then
  echo "[rdfexport] rdflib wheel already exists, skipping download..."
else
  echo "[rdfexport] Downloading rdflib wheel..."
  mkdir -p "${TARGET_DIR}/wheels"
  curl -L "${WHEEL_URL}" -o "${TMP_DIR}/${WHEEL_FILE}"

  echo "[rdfexport] Converting wheel to base64..."
  base64 < "${TMP_DIR}/${WHEEL_FILE}" > "${TARGET_DIR}/wheels/${WHEEL_FILE}.base64"
fi

echo "[rdfexport] Pyodide assets available at ${TARGET_DIR}"
