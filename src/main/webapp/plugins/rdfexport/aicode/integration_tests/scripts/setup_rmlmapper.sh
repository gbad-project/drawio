#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/.rmlmapper"
JAR_DIR="${TOOLS_DIR}/lib"
MANIFEST_PATH="${TOOLS_DIR}/manifest.json"

RMLMAPPER_VERSION="7.0.0-r374"
RMLMAPPER_JAR="rmlmapper-${RMLMAPPER_VERSION}-all.jar"
RMLMAPPER_URL="https://github.com/RMLio/rmlmapper-java/releases/download/v7.0.0/${RMLMAPPER_JAR}"
RMLMAPPER_SHA256="925f83c4d029f56b18b81427484163f634edede6e0d620d572e04a9014de922f"

# SDKMAN configuration
SDKMAN_DIR="${TOOLS_DIR}/sdkman"
JDK_VERSION="17.0.13-tem"

mkdir -p "${JAR_DIR}"

# Install SDKMAN! if not present
if [[ ! -d "${SDKMAN_DIR}" ]]; then
  echo "[setup-rmlmapper] Installing SDKMAN!..."
  # Temporarily disable strict mode for SDKMAN install
  set +u
  export SDKMAN_DIR
  curl -s "https://get.sdkman.io?rcupdate=false" | bash
  set -u
fi

# Source SDKMAN with proper error handling
set +u  # Temporarily disable unbound variable check
source "${SDKMAN_DIR}/bin/sdkman-init.sh"
set -u  # Re-enable strict mode

# Install Java via SDKMAN (automatically handles OS detection)
echo "[setup-rmlmapper] Checking for Java ${JDK_VERSION}..."
set +u
if ! sdk list java 2>/dev/null | grep -q "installed.*${JDK_VERSION}"; then
  echo "[setup-rmlmapper] Installing Temurin JDK 17 via SDKMAN!..."
  sdk install java "${JDK_VERSION}" < /dev/null
else
  echo "[setup-rmlmapper] Java ${JDK_VERSION} already installed."
fi

# Use the installed Java
sdk use java "${JDK_VERSION}"
set -u

# Download RMLMapper
if [[ ! -f "${JAR_DIR}/${RMLMAPPER_JAR}" ]]; then
  echo "[setup-rmlmapper] Downloading RMLMapper ${RMLMAPPER_VERSION}..."
  curl -fL "${RMLMAPPER_URL}" -o "${JAR_DIR}/${RMLMAPPER_JAR}"
fi

# Verify checksum
rmlmapper_actual_sha="$(sha256sum "${JAR_DIR}/${RMLMAPPER_JAR}" | awk '{print $1}')"
if [[ "${rmlmapper_actual_sha}" != "${RMLMAPPER_SHA256}" ]]; then
  echo "[setup-rmlmapper] Checksum mismatch for ${RMLMAPPER_JAR}:" >&2
  echo "  expected ${RMLMAPPER_SHA256}" >&2
  echo "  actual   ${rmlmapper_actual_sha}" >&2
  exit 1
fi

# Get Java paths from SDKMAN
JAVA_HOME_PATH="${SDKMAN_DIR}/candidates/java/${JDK_VERSION}"
JAVA_BIN="${JAVA_HOME_PATH}/bin/java"

# Write manifest
cat > "${MANIFEST_PATH}" <<MANIFEST
{
  "java_version": "${JDK_VERSION}",
  "java_home": "${JAVA_HOME_PATH}",
  "java_bin": "${JAVA_BIN}",
  "rmlmapper_version": "${RMLMAPPER_VERSION}",
  "rmlmapper_jar": "${JAR_DIR}/${RMLMAPPER_JAR}",
  "sdkman_dir": "${SDKMAN_DIR}"
}
MANIFEST

echo "[setup-rmlmapper] ✓ Environment ready. Manifest written to ${MANIFEST_PATH}."
echo "[setup-rmlmapper] Java location: ${JAVA_BIN}"
