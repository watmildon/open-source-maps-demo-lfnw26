# Developer Setup

## Prerequisites

- [osmium-tool](https://osmium.org/): OSM data extraction
- [DuckDB](https://duckdb.org/): Layercake GeoParquet queries
- [tippecanoe](https://github.com/felt/tippecanoe): Vector tile generation
- Python 3 with `geopandas`, `shapely`, `pandas`

```bash
pip install -r scripts/requirements.txt
```

## Running the Data Pipeline

Download a PBF extract from [SliceOSM](https://slice.openstreetmap.us/) and run:

```bash
bash scripts/process-all.sh <file.osm.pbf> <xmin> <ymin> <xmax> <ymax>
```

Example for Bellingham:

```bash
bash scripts/process-all.sh US-WA-Bellingham.osm.pbf -122.55 48.7 -122.35 48.85
```

This extracts POIs via osmium, queries Layercake via DuckDB, scores features for missing tags, and generates PMTiles in `docs/tiles/`.

## Local Dev Server

```bash
bash scripts/serve-local.sh
```

Opens at `http://localhost:3721/`. The server supports HTTP range requests required by PMTiles.
