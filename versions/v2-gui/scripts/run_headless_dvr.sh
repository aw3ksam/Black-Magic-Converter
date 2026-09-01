#!/usr/bin/env bash
# Helper script to launch DaVinci Resolve Studio in Headless (-nogui) Mode on macOS

RESOLVE_APP="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"

if [ ! -f "$RESOLVE_APP" ]; then
    echo "Error: DaVinci Resolve not found at: $RESOLVE_APP"
    exit 1
fi

echo "=================================================="
echo "Starting DaVinci Resolve Studio Headless Engine..."
echo "Binary: $RESOLVE_APP"
echo "=================================================="

"$RESOLVE_APP" -nogui &
DVR_PID=$!

echo "DaVinci Resolve launched with PID: $DVR_PID"
echo "To stop: kill $DVR_PID"
