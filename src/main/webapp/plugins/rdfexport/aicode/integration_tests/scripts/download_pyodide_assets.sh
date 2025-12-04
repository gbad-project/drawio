#!/usr/bin/env bash
set -euo pipefail

VERSION="0.28.3"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET_DIR="${ROOT_DIR}/.pyodide"
ARCHIVE="pyodide-${VERSION}.tar.bz2"
ARCHIVE_URL="https://github.com/pyodide/pyodide/releases/download/${VERSION}/${ARCHIVE}"
WHEEL_FILE="rdflib-7.4.0-py3-none-any.whl"
WHEEL_URL="https://files.pythonhosted.org/packages/a7/52/9d03e93f2e00d2a07749ee90f358d08c07822819d084f08c387b7ade8b56/${WHEEL_FILE}"

PYYAML_WHEEL_FILE="PyYAML-6.0.3-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
PYYAML_WHEEL_URL="https://files.pythonhosted.org/packages/11/d2/6ad1c5e8ffc00b44ea7ab6c48e23f39e62fc30afe37ab89abad1c0cfa95c/${PYYAML_WHEEL_FILE}"

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

# Check if PyYAML wheel is already downloaded
if [[ -f "${TARGET_DIR}/wheels/${PYYAML_WHEEL_FILE}.base64" ]]; then
  echo "[rdfexport] PyYAML wheel already exists, skipping download..."
else
  echo "[rdfexport] Downloading PyYAML wheel..."
  mkdir -p "${TARGET_DIR}/wheels"
  curl -L "${PYYAML_WHEEL_URL}" -o "${TMP_DIR}/${PYYAML_WHEEL_FILE}"

  echo "[rdfexport] Converting wheel to base64..."
  base64 < "${TMP_DIR}/${PYYAML_WHEEL_FILE}" > "${TARGET_DIR}/wheels/${PYYAML_WHEEL_FILE}.base64"
fi

echo "[rdfexport] Pyodide assets available at ${TARGET_DIR}"
