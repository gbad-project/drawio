#!/usr/bin/env bash
set -euo pipefail

VERSION="0.26.4"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${ROOT_DIR}/pyodide"
ARCHIVE="pyodide-${VERSION}.tar.bz2"
ARCHIVE_URL="https://github.com/pyodide/pyodide/releases/download/${VERSION}/${ARCHIVE}"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

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

echo "[rdfexport] Pyodide assets available at ${TARGET_DIR}"
