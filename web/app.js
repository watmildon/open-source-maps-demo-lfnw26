// Tucson Survey Needs Map
// MapLibre GL JS + PMTiles overlay from two data pipelines

// --- Configuration ---
// PMTiles are served from tiles/ relative to the page (works on GitHub Pages and locally)
const TILES_BASE = new URL("tiles/", window.location.href).href;
const POI_PMTILES_URL = `pmtiles://${TILES_BASE}poi-survey.pmtiles`;
const INFRA_PMTILES_URL = `pmtiles://${TILES_BASE}infra-survey.pmtiles`;

const TUCSON_CENTER = [-110.9747, 32.2226];
const INITIAL_ZOOM = 13;
const BUFFER_METERS = 200;

// Color scale for missing tag counts
const COLOR_GREEN = "#2ecc71";
const COLOR_YELLOW = "#f39c12";
const COLOR_RED = "#e74c3c";

// --- PMTiles protocol ---
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// --- Basemap style (OpenMapTiles schema from OpenTileService) ---
const basemapStyle = {
    version: 8,
    sources: {
        openmaptiles: {
            type: "vector",
            url: "https://tiles.openstreetmap.us/vector/openmaptiles.json",
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | <a href="https://openmaptiles.org/">OpenMapTiles</a> | <a href="https://tiles.openstreetmap.us/">OSM US TileService</a>'
        }
    },
    glyphs: "https://tiles.openstreetmap.us/fonts/{fontstack}/{range}.pbf",
    layers: [
        // Background
        {
            id: "background",
            type: "background",
            paint: { "background-color": "#f0ede9" }
        },
        // Water
        {
            id: "water",
            type: "fill",
            source: "openmaptiles",
            "source-layer": "water",
            paint: { "fill-color": "#a4c4d1", "fill-opacity": 0.7 }
        },
        // Landuse - green areas
        {
            id: "landuse-green",
            type: "fill",
            source: "openmaptiles",
            "source-layer": "landuse",
            filter: ["in", "class", "grass", "park", "cemetery", "wood", "scrub"],
            paint: { "fill-color": "#d4e6c3", "fill-opacity": 0.5 }
        },
        // Buildings (basemap)
        {
            id: "building-base",
            type: "fill",
            source: "openmaptiles",
            "source-layer": "building",
            minzoom: 14,
            paint: { "fill-color": "#ddd", "fill-opacity": 0.5 }
        },
        // Roads - casing
        {
            id: "road-casing",
            type: "line",
            source: "openmaptiles",
            "source-layer": "transportation",
            filter: ["in", "class", "motorway", "trunk", "primary", "secondary", "tertiary"],
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
                "line-color": "#ccc",
                "line-width": ["interpolate", ["linear"], ["zoom"],
                    10, 1,
                    14, 6,
                    18, 16
                ]
            }
        },
        // Roads - fill
        {
            id: "road-fill",
            type: "line",
            source: "openmaptiles",
            "source-layer": "transportation",
            filter: ["in", "class", "motorway", "trunk", "primary", "secondary", "tertiary"],
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
                "line-color": "#fff",
                "line-width": ["interpolate", ["linear"], ["zoom"],
                    10, 0.5,
                    14, 4,
                    18, 12
                ]
            }
        },
        // Minor roads
        {
            id: "road-minor",
            type: "line",
            source: "openmaptiles",
            "source-layer": "transportation",
            filter: ["in", "class", "minor", "service"],
            minzoom: 13,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
                "line-color": "#fff",
                "line-width": ["interpolate", ["linear"], ["zoom"],
                    13, 0.5,
                    18, 6
                ]
            }
        },
        // Road labels
        {
            id: "road-label",
            type: "symbol",
            source: "openmaptiles",
            "source-layer": "transportation_name",
            minzoom: 13,
            layout: {
                "symbol-placement": "line",
                "text-field": "{name}",
                "text-font": ["Open Sans Regular"],
                "text-size": 11,
                "text-max-angle": 30
            },
            paint: {
                "text-color": "#555",
                "text-halo-color": "#fff",
                "text-halo-width": 1.5
            }
        },
        // Place labels
        {
            id: "place-label",
            type: "symbol",
            source: "openmaptiles",
            "source-layer": "place",
            layout: {
                "text-field": "{name}",
                "text-font": ["Open Sans Bold"],
                "text-size": ["interpolate", ["linear"], ["zoom"],
                    8, 12,
                    14, 18
                ]
            },
            paint: {
                "text-color": "#333",
                "text-halo-color": "#fff",
                "text-halo-width": 2
            }
        }
    ]
};

// --- Map initialization ---
const map = new maplibregl.Map({
    container: "map",
    style: basemapStyle,
    center: TUCSON_CENTER,
    zoom: INITIAL_ZOOM,
    hash: true
});

map.addControl(new maplibregl.NavigationControl(), "bottom-right");
map.addControl(new maplibregl.ScaleControl(), "bottom-left");

// --- Add overlay layers on map load ---
map.on("load", () => {
    // PMTiles sources
    map.addSource("poi-survey", {
        type: "vector",
        url: POI_PMTILES_URL
    });

    map.addSource("infra-survey", {
        type: "vector",
        url: INFRA_PMTILES_URL
    });

    // --- Parks (green fill, opacity scales with survey_score) ---
    map.addLayer({
        id: "parks",
        source: "infra-survey",
        "source-layer": "parks",
        type: "fill",
        paint: {
            "fill-color": "#27ae60",
            "fill-opacity": [
                "interpolate", ["linear"], ["coalesce", ["get", "survey_score"], 0],
                0, 0.05,
                50, 0.2,
                200, 0.45
            ],
            "fill-outline-color": "#27ae60"
        }
    });

    // --- Buildings needing survey (fill) ---
    map.addLayer({
        id: "buildings",
        source: "infra-survey",
        "source-layer": "buildings",
        type: "fill",
        paint: {
            "fill-color": [
                "case",
                [">=", ["get", "missing_count"], 2], COLOR_RED,
                COLOR_YELLOW
            ],
            "fill-opacity": 0.5,
            "fill-outline-color": "#555"
        }
    });

    // --- Roads needing survey (line) ---
    map.addLayer({
        id: "roads",
        source: "infra-survey",
        "source-layer": "roads",
        type: "line",
        paint: {
            "line-color": [
                "case",
                [">=", ["get", "missing_count"], 2], COLOR_RED,
                COLOR_YELLOW
            ],
            "line-width": 3,
            "line-opacity": 0.85
        }
    });

    // --- Museums (purple circles, size scales with survey_score) ---
    map.addLayer({
        id: "museums",
        source: "poi-survey",
        "source-layer": "museums",
        type: "circle",
        paint: {
            "circle-radius": [
                "interpolate", ["linear"], ["coalesce", ["get", "survey_score"], 0],
                0, 6,
                50, 10,
                200, 18
            ],
            "circle-color": "#8e44ad",
            "circle-opacity": [
                "interpolate", ["linear"], ["coalesce", ["get", "survey_score"], 0],
                0, 0.4,
                50, 0.7,
                200, 1.0
            ],
            "circle-stroke-color": "#fff",
            "circle-stroke-width": 2
        }
    });
    map.addLayer({
        id: "museums-label",
        source: "poi-survey",
        "source-layer": "museums",
        type: "symbol",
        minzoom: 12,
        filter: [">", ["coalesce", ["get", "survey_score"], 0], 0],
        layout: {
            "text-field": ["concat",
                ["coalesce", ["get", "name"], "Needs Name Survey"],
                "\n", ["to-string", ["get", "survey_score"]], " tags"
            ],
            "text-font": ["Open Sans Bold"],
            "text-size": [
                "interpolate", ["linear"], ["coalesce", ["get", "survey_score"], 0],
                1, 10,
                100, 14,
                500, 18
            ],
            "text-offset": [0, 1.5],
            "text-allow-overlap": false
        },
        paint: {
            "text-color": "#6c2d8b",
            "text-halo-color": "#fff",
            "text-halo-width": 1.5
        }
    });

    // --- POIs needing survey (circles) ---
    map.addLayer({
        id: "pois",
        source: "poi-survey",
        "source-layer": "pois",
        type: "circle",
        paint: {
            "circle-radius": 6,
            "circle-color": [
                "case",
                [">=", ["get", "missing_count"], 4], COLOR_RED,
                [">=", ["get", "missing_count"], 2], COLOR_YELLOW,
                COLOR_GREEN
            ],
            "circle-stroke-color": "#fff",
            "circle-stroke-width": 1
        }
    });

    // --- Anchor labels (on top of all data layers) ---
    map.addLayer({
        id: "parks-label",
        source: "infra-survey",
        "source-layer": "parks_labels",
        type: "symbol",
        minzoom: 13,
        filter: [">", ["coalesce", ["get", "survey_score"], 0], 0],
        layout: {
            "text-field": ["concat",
                ["coalesce", ["get", "name"], "Needs Name Survey"],
                "\n", ["to-string", ["get", "survey_score"]], " tags"
            ],
            "text-font": ["Open Sans Bold"],
            "text-size": [
                "interpolate", ["linear"], ["coalesce", ["get", "survey_score"], 0],
                1, 10,
                100, 14,
                500, 18
            ],
            "text-allow-overlap": false
        },
        paint: {
            "text-color": "#1a7a3a",
            "text-halo-color": "#fff",
            "text-halo-width": 1.5
        }
    });

    // --- Click popups ---
    const interactiveLayers = ["roads", "pois", "buildings"];

    interactiveLayers.forEach(layerId => {
        map.on("click", layerId, (e) => {
            const f = e.features[0];
            const props = f.properties;
            const missingTags = props.missing_tags ? props.missing_tags.split(",") : [];
            const name = props.name || "(unnamed)";
            const osmId = props.osm_id || "";

            // Build iD editor URL
            let editUrl = "https://www.openstreetmap.org/edit?editor=id";
            if (osmId) {
                const parts = osmId.split("/");
                if (parts.length === 2) {
                    editUrl += `&${parts[0]}=${parts[1]}`;
                }
            }

            const missingHtml = missingTags
                .filter(t => t.trim())
                .map(t => `<li><code>${t}</code></li>`)
                .join("");

            const html = `
                <h3>${name}</h3>
                <div class="popup-category">${props.category || layerId}</div>
                ${missingHtml ? `<ul class="popup-missing">${missingHtml}</ul>` : ""}
                <a class="popup-edit" href="${editUrl}" target="_blank">Edit in iD</a>
            `;

            new maplibregl.Popup({ maxWidth: "280px" })
                .setLngLat(e.lngLat)
                .setHTML(html)
                .addTo(map);
        });

        // Cursor changes
        map.on("mouseenter", layerId, () => {
            map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layerId, () => {
            map.getCanvas().style.cursor = "";
        });
    });

    // Also handle clicks on parks and museums for info (with survey score)
    ["parks", "museums"].forEach(layerId => {
        map.on("click", layerId, (e) => {
            const props = e.features[0].properties;
            const name = props.name || `(unnamed ${layerId.slice(0, -1)})`;
            const score = props.survey_score || 0;
            const label = layerId === "parks" ? "Park" : "Museum";
            new maplibregl.Popup()
                .setLngLat(e.lngLat)
                .setHTML(`<h3>${name}</h3><div class="popup-category">${label}</div><p><strong>${score}</strong> missing tags within ${BUFFER_METERS}m</p>`)
                .addTo(map);
        });
        map.on("mouseenter", layerId, () => map.getCanvas().style.cursor = "pointer");
        map.on("mouseleave", layerId, () => map.getCanvas().style.cursor = "");
    });
});

// --- Layer toggle controls ---
// Map from base layer to associated label layer
const labelLayers = { parks: "parks-label", museums: "museums-label" };

function applyLayerVisibility(layerId, visible) {
    const visibility = visible ? "visible" : "none";
    map.setLayoutProperty(layerId, "visibility", visibility);
    if (labelLayers[layerId]) {
        map.setLayoutProperty(labelLayers[layerId], "visibility", visibility);
    }
}

document.querySelectorAll("#controls input[data-layer]").forEach(input => {
    input.addEventListener("change", (e) => {
        applyLayerVisibility(e.target.dataset.layer, e.target.checked);
    });
});

// Sync layer visibility with checkbox state after map loads
// (browser may restore unchecked checkboxes from cache on reload)
map.on("load", () => {
    document.querySelectorAll("#controls input[data-layer]").forEach(input => {
        applyLayerVisibility(input.dataset.layer, input.checked);
    });
});
