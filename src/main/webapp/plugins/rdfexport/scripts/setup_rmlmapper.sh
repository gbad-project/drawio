#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/tools/rmlmapper"
DOWNLOADS_DIR="${TOOLS_DIR}/downloads"
JAVA_DIR="${TOOLS_DIR}/java"
JAR_DIR="${TOOLS_DIR}/lib"
MANIFEST_PATH="${TOOLS_DIR}/manifest.json"

JDK_VERSION="17.0.13+11"
JDK_ARCHIVE="OpenJDK17U-jdk_x64_linux_hotspot_17.0.13_11.tar.gz"
JDK_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13+11/${JDK_ARCHIVE}"
JDK_SHA256="8682892fc02965930b9022c066fa164dd6f458ef4a5dc262016aa28333b30f49"

RMLMAPPER_VERSION="7.0.0-r374"
RMLMAPPER_JAR="rmlmapper-${RMLMAPPER_VERSION}-all.jar"
RMLMAPPER_URL="https://github.com/RMLio/rmlmapper-java/releases/download/v7.0.0/${RMLMAPPER_JAR}"
RMLMAPPER_SHA256="925f83c4d029f56b18b81427484163f634edede6e0d620d572e04a9014de922f"

mkdir -p "${DOWNLOADS_DIR}" "${JAVA_DIR}" "${JAR_DIR}"

jdk_archive_path="${DOWNLOADS_DIR}/${JDK_ARCHIVE}"
if [[ ! -f "${jdk_archive_path}" ]]; then
  echo "[setup-rmlmapper] Downloading Temurin JDK ${JDK_VERSION}..."
  curl -fL "${JDK_URL}" -o "${jdk_archive_path}"
fi

jdk_actual_sha="$(sha256sum "${jdk_archive_path}" | awk '{print $1}')"
if [[ "${jdk_actual_sha}" != "${JDK_SHA256}" ]]; then
  echo "[setup-rmlmapper] Checksum mismatch for ${JDK_ARCHIVE}:" >&2
  echo "  expected ${JDK_SHA256}" >&2
  echo "  actual   ${jdk_actual_sha}" >&2
  exit 1
fi

jdk_extract_dir="${JAVA_DIR}/temurin-${JDK_VERSION}"
if [[ ! -d "${jdk_extract_dir}" ]]; then
  echo "[setup-rmlmapper] Extracting JDK to ${jdk_extract_dir}..."
  mkdir -p "${jdk_extract_dir}"
  tar -xzf "${jdk_archive_path}" -C "${jdk_extract_dir}" --strip-components=1
fi

rmlmapper_path="${JAR_DIR}/${RMLMAPPER_JAR}"
if [[ ! -f "${rmlmapper_path}" ]]; then
  echo "[setup-rmlmapper] Downloading RMLMapper ${RMLMAPPER_VERSION}..."
  curl -fL "${RMLMAPPER_URL}" -o "${rmlmapper_path}"
fi

rmlmapper_actual_sha="$(sha256sum "${rmlmapper_path}" | awk '{print $1}')"
if [[ "${rmlmapper_actual_sha}" != "${RMLMAPPER_SHA256}" ]]; then
  echo "[setup-rmlmapper] Checksum mismatch for ${RMLMAPPER_JAR}:" >&2
  echo "  expected ${RMLMAPPER_SHA256}" >&2
  echo "  actual   ${rmlmapper_actual_sha}" >&2
  exit 1
fi

java_bin="${jdk_extract_dir}/bin/java"
if [[ ! -x "${java_bin}" ]]; then
  echo "[setup-rmlmapper] java binary not found at ${java_bin}" >&2
  exit 1
fi

cat > "${MANIFEST_PATH}" <<MANIFEST
{
  "java_version": "${JDK_VERSION}",
  "java_home": "${jdk_extract_dir}",
  "java_bin": "${java_bin}",
  "rmlmapper_version": "${RMLMAPPER_VERSION}",
  "rmlmapper_jar": "${rmlmapper_path}"
}
MANIFEST

echo "[setup-rmlmapper] Environment ready. Manifest written to ${MANIFEST_PATH}."
