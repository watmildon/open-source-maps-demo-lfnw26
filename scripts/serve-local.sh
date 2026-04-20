#!/usr/bin/env bash
# Serve the map locally for development.
# Uses a custom server that supports HTTP Range requests (required by PMTiles).
# Access the map at: http://localhost:8080/docs/
set -euo pipefail

PORT="${1:-3721}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check that PMTiles exist
if [ ! -f "$ROOT/docs/tiles/poi-survey.pmtiles" ] || [ ! -f "$ROOT/docs/tiles/infra-survey.pmtiles" ]; then
    echo "Warning: PMTiles files not found in docs/tiles/"
    echo "Run the pipeline first, then copy tiles:"
    echo "  bash scripts/process-all.sh"
    echo "  cp data/*.pmtiles docs/tiles/"
    echo ""
fi

python3 "$SCRIPT_DIR/serve-local.py" "$PORT"
