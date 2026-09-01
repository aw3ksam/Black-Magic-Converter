#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> Building BRAW Native Decoder (braw_decode)..."

SDK_DIR="${ROOT_DIR}/Documents/Blackmagic RAW SDK/Mac"
INCLUDE_DIR="${SDK_DIR}/Include"
LIB_DIR="${SDK_DIR}/Libraries"
SRC_FILE="${ROOT_DIR}/src/native/braw_decode.mm"
DISPATCH_FILE="${INCLUDE_DIR}/BlackmagicRawAPIDispatch.cpp"
OUT_BIN="${ROOT_DIR}/bin/braw_decode"

mkdir -p "${ROOT_DIR}/bin"

clang++ -std=c++17 -O3 -fobjc-arc \
    -I"${INCLUDE_DIR}" \
    -F"${LIB_DIR}" \
    -framework CoreFoundation \
    -framework CoreServices \
    -framework Foundation \
    -framework Metal \
    -framework AVFoundation \
    -framework VideoToolbox \
    -framework CoreMedia \
    -framework CoreVideo \
    -framework AudioToolbox \
    -framework Accelerate \
    "${DISPATCH_FILE}" \
    "${SRC_FILE}" \
    -o "${OUT_BIN}"

chmod +x "${OUT_BIN}"
echo "==> Successfully built ${OUT_BIN}"
