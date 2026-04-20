#!/usr/bin/env bash
# Generate PMTiles from scored GeoJSON using tippecanoe.
# Creates two separate PMTiles files to showcase both data pipelines.
set -euo pipefail

DATA_DIR="${1:-data}"

echo "=== Generating PMTiles with tippecanoe ==="

echo "Building POI survey tiles (SliceOSM pipeline)..."
tippecanoe -o "$DATA_DIR/poi-survey.pmtiles" -f \
    -n "POI Survey Needs" \
    -N "Restaurants, cafes, and shops near parks/museums needing OSM survey" \
    -Z 10 -z 16 \
    -L pois:"$DATA_DIR/scored_pois.geojson" \
    -L museums:"$DATA_DIR/museums_display.geojson" \
    --drop-densest-as-needed \
    --extend-zooms-if-still-dropping

echo "Building infrastructure survey tiles (Layercake pipeline)..."
tippecanoe -o "$DATA_DIR/infra-survey.pmtiles" -f \
    -n "Infrastructure Survey Needs" \
    -N "Roads and buildings near parks/museums needing OSM survey" \
    -Z 10 -z 16 \
    -L roads:"$DATA_DIR/scored_roads.geojson" \
    -L buildings:"$DATA_DIR/scored_buildings.geojson" \
    -L parks:"$DATA_DIR/parks_display.geojson" \
    -L parks_labels:"$DATA_DIR/parks_labels.geojson" \
    --drop-densest-as-needed \
    --extend-zooms-if-still-dropping

echo "Tile generation complete:"
ls -lh "$DATA_DIR"/*.pmtiles

# Copy to web/tiles/ for serving
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_TILES="$SCRIPT_DIR/../web/tiles"
mkdir -p "$WEB_TILES"
cp "$DATA_DIR/poi-survey.pmtiles" "$DATA_DIR/infra-survey.pmtiles" "$WEB_TILES/"
echo "Copied to web/tiles/ for serving"
