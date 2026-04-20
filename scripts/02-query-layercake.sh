#!/usr/bin/env bash
# Query Layercake GeoParquet files remotely via DuckDB.
# Exports TSV files with WKT geometry for the Python scoring script to consume.
#
# Usage: 02-query-layercake.sh <data_dir> <xmin> <ymin> <xmax> <ymax>
set -euo pipefail

DATA_DIR="${1:-data}"
XMIN="${2:--111.1}"
YMIN="${3:-32.1}"
XMAX="${4:--110.8}"
YMAX="${5:-32.35}"

mkdir -p "$DATA_DIR"

# Use duckdb from PATH, or fall back to known install location
DUCKDB="$(which duckdb 2>/dev/null || echo "$HOME/.duckdb/cli/latest/duckdb")"

LAYERCAKE_BASE="https://data.openstreetmap.us/layercake"

echo "=== Querying Layercake GeoParquet via DuckDB ==="
echo "Bounding box: $XMIN,$YMIN,$XMAX,$YMAX"

"$DUCKDB" <<SQL
INSTALL spatial; LOAD spatial;
INSTALL httpfs;  LOAD httpfs;

-- Parks from Layercake
COPY (
    SELECT
        id, type,
        ST_AsText(geometry) as wkt_geometry,
        name
    FROM read_parquet('${LAYERCAKE_BASE}/parks.parquet')
    WHERE bbox.xmin > ${XMIN} AND bbox.xmax < ${XMAX}
      AND bbox.ymin > ${YMIN} AND bbox.ymax < ${YMAX}
) TO '${DATA_DIR}/layercake_parks.tsv' (HEADER, DELIMITER '	');

-- Highways from Layercake
COPY (
    SELECT
        id, type,
        ST_AsText(geometry) as wkt_geometry,
        name, highway, surface, lanes, maxspeed
    FROM read_parquet('${LAYERCAKE_BASE}/highways.parquet')
    WHERE bbox.xmin > ${XMIN} AND bbox.xmax < ${XMAX}
      AND bbox.ymin > ${YMIN} AND bbox.ymax < ${YMAX}
) TO '${DATA_DIR}/layercake_roads.tsv' (HEADER, DELIMITER '	');

-- Buildings from Layercake
COPY (
    SELECT
        id, type,
        ST_AsText(geometry) as wkt_geometry,
        name, building, "building:levels", height
    FROM read_parquet('${LAYERCAKE_BASE}/buildings.parquet')
    WHERE bbox.xmin > ${XMIN} AND bbox.xmax < ${XMAX}
      AND bbox.ymin > ${YMIN} AND bbox.ymax < ${YMAX}
) TO '${DATA_DIR}/layercake_buildings.tsv' (HEADER, DELIMITER '	');
SQL

echo "Layercake queries complete:"
echo "  $(wc -l < "$DATA_DIR/layercake_parks.tsv") parks (incl header)"
echo "  $(wc -l < "$DATA_DIR/layercake_roads.tsv") roads (incl header)"
echo "  $(wc -l < "$DATA_DIR/layercake_buildings.tsv") buildings (incl header)"
