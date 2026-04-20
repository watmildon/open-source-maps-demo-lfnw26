#!/usr/bin/env bash
# Orchestrator: run the full data pipeline from PBF to PMTiles.
# Usage: bash scripts/process-all.sh [path-to.osm.pbf]
set -euo pipefail

PBF="${1:-US-AZ-Tuscon.osm.pbf}"
DATA_DIR="data"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  Tucson Survey Needs — Data Pipeline"
echo "============================================"
echo "PBF: $PBF"
echo ""

# Step 1: Extract POIs from SliceOSM PBF
echo "--- Step 1/4: Extract POIs (SliceOSM) ---"
bash "$SCRIPT_DIR/01-extract-pois.sh" "$PBF" "$DATA_DIR"
echo ""

# Step 2: Query Layercake GeoParquet via DuckDB
echo "--- Step 2/4: Query Layercake (DuckDB) ---"
bash "$SCRIPT_DIR/02-query-layercake.sh" "$DATA_DIR"
echo ""

# Step 3: Score features for survey needs
echo "--- Step 3/4: Score features (Python) ---"
python3 "$SCRIPT_DIR/score_features.py" "$DATA_DIR"
echo ""

# Step 4: Generate PMTiles with tippecanoe
echo "--- Step 4/4: Generate tiles (tippecanoe) ---"
bash "$SCRIPT_DIR/03-generate-tiles.sh" "$DATA_DIR"
echo ""

echo "============================================"
echo "  Pipeline complete!"
echo "============================================"
