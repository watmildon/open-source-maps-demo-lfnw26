#!/usr/bin/env bash
# Extract POIs and museums from a SliceOSM PBF extract using osmium
set -euo pipefail

PBF="${1:-US-AZ-Tuscon.osm.pbf}"
DATA_DIR="${2:-data}"

if [ ! -f "$PBF" ]; then
    echo "Error: PBF file not found: $PBF"
    exit 1
fi

mkdir -p "$DATA_DIR"

echo "=== Extracting POIs from SliceOSM PBF ==="

echo "Extracting restaurants, cafes, bars, pubs, fast food, shops..."
osmium tags-filter "$PBF" \
    nwr/amenity=restaurant,cafe,fast_food,bar,pub \
    nwr/shop \
    -o "$DATA_DIR/pois.osm.pbf" --overwrite

echo "Extracting museums..."
osmium tags-filter "$PBF" \
    nwr/tourism=museum nwr/amenity=museum \
    -o "$DATA_DIR/museums.osm.pbf" --overwrite

echo "Converting to GeoJSON..."
osmium export "$DATA_DIR/pois.osm.pbf" -o "$DATA_DIR/pois.geojson" --overwrite
osmium export "$DATA_DIR/museums.osm.pbf" -o "$DATA_DIR/museums.geojson" --overwrite

echo "POI extraction complete:"
echo "  $(grep -c '"type": "Feature"' "$DATA_DIR/pois.geojson" || echo 0) POIs"
echo "  $(grep -c '"type": "Feature"' "$DATA_DIR/museums.geojson" || echo 0) museums"
