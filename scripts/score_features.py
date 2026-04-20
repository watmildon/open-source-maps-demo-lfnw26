#!/usr/bin/env python3
"""
Score OSM features for survey completeness.

Loads POIs/museums from osmium GeoJSON exports (SliceOSM pipeline) and
roads/buildings/parks from DuckDB TSV exports (Layercake pipeline).

Buffers parks + museums by 200m, spatially joins nearby features,
scores tag completeness, and outputs scored GeoJSON for tippecanoe.

Each park/museum gets a survey_score = total missing tags within its buffer.
"""

import sys
import math
import json
import csv
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


# Tag completeness definitions per category
EXPECTED_TAGS = {
    "roads": ["name", "surface"],
    "pois": ["opening_hours", "phone", "website"],
    "buildings": ["building:levels"],
}

# cuisine only applies to these amenity types
CUISINE_AMENITIES = {"restaurant", "fast_food"}

# name is only expected on these highway types
NAMED_HIGHWAY_TYPES = {"primary", "secondary", "tertiary", "residential"}

BUFFER_METERS = 200


def detect_utm_epsg(lon, lat):
    """Auto-detect UTM zone EPSG code from a lon/lat coordinate."""
    zone = int(math.floor((lon + 180) / 6)) + 1
    if lat >= 0:
        return 32600 + zone  # Northern hemisphere
    else:
        return 32700 + zone  # Southern hemisphere


def load_layercake_tsv(filepath):
    """Load a Layercake TSV export (with WKT geometry) into a GeoDataFrame."""
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    df["geometry"] = df["wkt_geometry"].apply(wkt.loads)
    # Strip brackets from name column (Layercake encodes some values as [value])
    if "name" in df.columns:
        df["name"] = df["name"].str.strip("[]")
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.drop(columns=["wkt_geometry"])
    return gdf


def load_osmium_geojson(filepath):
    """Load an osmium-exported GeoJSON into a GeoDataFrame."""
    gdf = gpd.read_file(filepath)
    return gdf


def parse_osm_id(row, source):
    """
    Extract a normalized osm_id like 'way/123456' from the feature.
    - osmium exports use '@id' property (e.g. 'way/123456')
    - Layercake exports have 'id' (int) and 'type' (e.g. 'way') columns
    """
    if source == "osmium":
        raw = row.get("@id", "")
        if raw:
            return str(raw)
        return ""
    else:  # layercake
        osm_type = row.get("type", "")
        osm_id = row.get("id", "")
        if osm_type and osm_id:
            return f"{osm_type}/{osm_id}"
        return ""


def is_missing(val):
    """Check if a tag value is effectively missing."""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def score_features(gdf, category, source, survey_area_utm, utm_epsg):
    """
    Score a GeoDataFrame for tag completeness.
    Returns a new GeoDataFrame with only features that:
    1. Intersect the survey area (within buffer of a park or museum)
    2. Have at least one missing expected tag
    """
    if gdf.empty:
        return gpd.GeoDataFrame()

    expected = EXPECTED_TAGS[category]

    # Reproject to UTM for spatial join
    gdf_utm = gdf.to_crs(epsg=utm_epsg)

    # Spatial filter: keep only features intersecting the survey area
    mask = gdf_utm.intersects(survey_area_utm)
    nearby = gdf.loc[mask].copy()

    if nearby.empty:
        return gpd.GeoDataFrame()

    # Score tag completeness
    missing_tags_list = []
    missing_counts = []
    osm_ids = []
    names = []

    for _, row in nearby.iterrows():
        missing = []
        check_tags = list(expected)
        # For POIs, check cuisine only for restaurants and fast food
        if category == "pois":
            amenity = row.get("amenity", "")
            if isinstance(amenity, str) and amenity in CUISINE_AMENITIES:
                check_tags.append("cuisine")
        # For roads, only check name on primary/secondary/tertiary/residential
        if category == "roads":
            highway = row.get("highway", "")
            if not (isinstance(highway, str) and highway in NAMED_HIGHWAY_TYPES):
                check_tags = [t for t in check_tags if t != "name"]
        for tag in check_tags:
            if is_missing(row.get(tag)):
                missing.append(tag)
        missing_tags_list.append(",".join(missing))
        missing_counts.append(len(missing))
        osm_ids.append(parse_osm_id(row, source))
        names.append(row.get("name", ""))

    nearby = nearby.copy()
    nearby["missing_tags"] = missing_tags_list
    nearby["missing_count"] = missing_counts
    nearby["osm_id"] = osm_ids
    nearby["name"] = names
    nearby["category"] = category

    # Filter out fully-tagged features
    nearby = nearby[nearby["missing_count"] > 0]

    if nearby.empty:
        return gpd.GeoDataFrame()

    # For POIs: convert all non-point geometries to centroids
    if category == "pois":
        is_not_point = ~nearby.geometry.geom_type.isin(["Point"])
        if is_not_point.any():
            nearby_utm = nearby.to_crs(epsg=utm_epsg)
            centroids_utm = nearby_utm.loc[is_not_point].geometry.representative_point()
            centroids_4326 = gpd.GeoSeries(centroids_utm, crs=f"EPSG:{utm_epsg}").to_crs("EPSG:4326")
            nearby.loc[is_not_point, "geometry"] = centroids_4326.values

    # Keep only the columns we need for the output
    keep_cols = ["geometry", "name", "category", "missing_tags", "missing_count", "osm_id"]
    return nearby[keep_cols]


def score_anchors(anchor_gdf, anchor_utm, scored_layers, utm_epsg):
    """
    For each anchor (park or museum), count the total missing tags
    from all scored features within its individual buffer.
    Returns the anchor GeoDataFrame with a 'survey_score' column added.
    """
    if anchor_gdf.empty:
        return anchor_gdf.copy()

    scores = []
    for idx in anchor_utm.index:
        anchor_buffer = anchor_utm.loc[idx, "geometry"].buffer(BUFFER_METERS)
        total_missing = 0
        for scored in scored_layers:
            if scored.empty:
                continue
            scored_utm = scored.to_crs(epsg=utm_epsg)
            hits = scored_utm.intersects(anchor_buffer)
            total_missing += scored_utm.loc[hits, "missing_count"].sum()
        scores.append(int(total_missing))

    result = anchor_gdf.copy()
    result["survey_score"] = scores
    return result


def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")

    print("=== Scoring features for survey needs ===")

    # --- Load anchor features ---
    # Parks from Layercake
    parks_file = data_dir / "layercake_parks.tsv"
    if parks_file.exists():
        parks = load_layercake_tsv(parks_file)
        print(f"Loaded {len(parks)} parks from Layercake")
    else:
        print(f"Warning: {parks_file} not found, using empty parks")
        parks = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # Museums from SliceOSM
    museums_file = data_dir / "museums.geojson"
    if museums_file.exists():
        museums = load_osmium_geojson(museums_file)
        print(f"Loaded {len(museums)} museums from SliceOSM")
    else:
        print(f"Warning: {museums_file} not found, using empty museums")
        museums = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # --- Detect UTM zone from data ---
    all_anchors = pd.concat([parks, museums], ignore_index=True)
    if all_anchors.empty:
        print("Error: No parks or museums found. Cannot create survey area.")
        sys.exit(1)

    centroid = all_anchors.union_all().centroid
    utm_epsg = detect_utm_epsg(centroid.x, centroid.y)
    print(f"Auto-detected UTM zone: EPSG:{utm_epsg}")

    # --- Buffer anchors by 200m ---
    parks_utm = parks.to_crs(epsg=utm_epsg) if not parks.empty else parks
    museums_utm = museums.to_crs(epsg=utm_epsg) if not museums.empty else museums

    buffers = []
    if not parks_utm.empty:
        buffers.append(unary_union(parks_utm.buffer(BUFFER_METERS)))
    if not museums_utm.empty:
        buffers.append(unary_union(museums_utm.buffer(BUFFER_METERS)))

    survey_area_utm = unary_union(buffers)
    print(f"Survey area created ({BUFFER_METERS}m buffer around parks + museums)")

    # --- Load and score feature categories ---

    # POIs from SliceOSM (osmium GeoJSON)
    pois_file = data_dir / "pois.geojson"
    if pois_file.exists():
        pois = load_osmium_geojson(pois_file)
        print(f"Loaded {len(pois)} POIs from SliceOSM")
        scored_pois = score_features(pois, "pois", "osmium", survey_area_utm, utm_epsg)
        print(f"  {len(scored_pois)} POIs need surveying")
    else:
        scored_pois = gpd.GeoDataFrame()

    # Roads from Layercake
    roads_file = data_dir / "layercake_roads.tsv"
    if roads_file.exists():
        roads = load_layercake_tsv(roads_file)
        print(f"Loaded {len(roads)} roads from Layercake")
        scored_roads = score_features(roads, "roads", "layercake", survey_area_utm, utm_epsg)
        print(f"  {len(scored_roads)} roads need surveying")
    else:
        scored_roads = gpd.GeoDataFrame()

    # Buildings from Layercake
    buildings_file = data_dir / "layercake_buildings.tsv"
    if buildings_file.exists():
        buildings = load_layercake_tsv(buildings_file)
        print(f"Loaded {len(buildings)} buildings from Layercake")
        scored_buildings = score_features(buildings, "buildings", "layercake", survey_area_utm, utm_epsg)
        print(f"  {len(scored_buildings)} buildings need surveying")
    else:
        scored_buildings = gpd.GeoDataFrame()

    # --- Score each park and museum ---
    scored_layers = [scored_pois, scored_roads, scored_buildings]

    print("\nScoring parks and museums by nearby survey needs...")

    if not parks.empty:
        parks_display = parks[["geometry", "name"]].copy()
        parks_scored = score_anchors(parks_display, parks_utm, scored_layers, utm_epsg)
        print(f"  Parks: score range {parks_scored['survey_score'].min()} – {parks_scored['survey_score'].max()}")
    else:
        parks_scored = gpd.GeoDataFrame()

    if not museums.empty:
        museums_display = museums[["geometry"]].copy()
        museums_display["name"] = museums.get("name", "")
        # Convert non-point museums to centroids
        is_not_point = ~museums_display.geometry.geom_type.isin(["Point"])
        if is_not_point.any():
            mus_utm = museums_display.to_crs(epsg=utm_epsg)
            centroids_utm = mus_utm.loc[is_not_point].geometry.representative_point()
            centroids_4326 = gpd.GeoSeries(centroids_utm, crs=f"EPSG:{utm_epsg}").to_crs("EPSG:4326")
            museums_display.loc[is_not_point, "geometry"] = centroids_4326.values
        museums_scored = score_anchors(museums_display, museums_utm, scored_layers, utm_epsg)
        print(f"  Museums: score range {museums_scored['survey_score'].min()} – {museums_scored['survey_score'].max()}")
    else:
        museums_scored = gpd.GeoDataFrame()

    # --- Write scored GeoJSON outputs ---
    def save_geojson(gdf, path):
        if gdf.empty:
            with open(path, "w") as f:
                json.dump({"type": "FeatureCollection", "features": []}, f)
        else:
            gdf.to_file(path, driver="GeoJSON")
        print(f"  Wrote {path}")

    save_geojson(scored_pois, data_dir / "scored_pois.geojson")
    save_geojson(scored_roads, data_dir / "scored_roads.geojson")
    save_geojson(scored_buildings, data_dir / "scored_buildings.geojson")
    save_geojson(parks_scored, data_dir / "parks_display.geojson")
    save_geojson(museums_scored, data_dir / "museums_display.geojson")

    # Create centroid-based label layers (one point per feature, avoids
    # duplicate labels when tippecanoe splits polygons across tiles)
    if not parks_scored.empty:
        parks_labels = parks_scored.copy()
        parks_labels_utm = parks_labels.to_crs(epsg=utm_epsg)
        parks_labels["geometry"] = parks_labels_utm.geometry.representative_point().to_crs("EPSG:4326").values
        save_geojson(parks_labels, data_dir / "parks_labels.geojson")
    else:
        save_geojson(gpd.GeoDataFrame(), data_dir / "parks_labels.geojson")

    print("\nScoring complete!")


if __name__ == "__main__":
    main()
