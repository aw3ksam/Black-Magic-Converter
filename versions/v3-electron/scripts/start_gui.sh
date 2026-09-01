#!/usr/bin/env bash
# Launcher script for BRAW Converter macOS GUI (v2.0)

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GUI_BIN="$ROOT_DIR/versions/v2-gui/.build/release/BRAWConverterGUI"

if [ ! -f "$GUI_BIN" ]; then
    echo "Building GUI application..."
    (cd "$ROOT_DIR/versions/v2-gui" && swift build -c release)
fi

echo "=================================================="
echo "Launching BRAW Converter Native macOS GUI (v2.0)..."
echo "Binary: $GUI_BIN"
echo "=================================================="

"$GUI_BIN"
