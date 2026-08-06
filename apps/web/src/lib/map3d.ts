import maplibregl from "maplibre-gl";

export const AUTO_3D_ENTER_ZOOM = 15;
export const AUTO_3D_EXIT_ZOOM = 13.75;
const BUILDINGS_3D_MIN_ZOOM = AUTO_3D_ENTER_ZOOM;
const BUILDINGS_FULL_HEIGHT_ZOOM = AUTO_3D_ENTER_ZOOM + 0.35;

const TERRAIN_SOURCE_ID = "aia-terrain-dem";
const BUILDINGS_SOURCE_ID = "aia-buildings";
const BUILDINGS_LAYER_ID = "aia-buildings-3d";

const TERRAIN_TILEJSON_URL =
  import.meta.env.VITE_TERRAIN_TILEJSON_URL || "https://tiles.mapterhorn.com/tilejson.json";
const TERRAIN_ENCODING =
  import.meta.env.VITE_TERRAIN_ENCODING === "mapbox" ? "mapbox" : "terrarium";
const TERRAIN_TILE_SIZE = Number(import.meta.env.VITE_TERRAIN_TILE_SIZE || 512);
const TERRAIN_ENABLED = import.meta.env.VITE_3D_TERRAIN_ENABLED === "true";
const BUILDINGS_TILEJSON_URL =
  import.meta.env.VITE_BUILDINGS_TILEJSON_URL || "https://tiles.openfreemap.org/planet";

function firstSymbolLayerId(map: maplibregl.Map): string | undefined {
  return map.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;
}

/** Restore terrain/building sources after a basemap style swap. */
export function syncMap3DStyle(map: maplibregl.Map, enabled: boolean): void {
  if (!enabled) {
    map.setTerrain(null);
    if (map.getLayer(BUILDINGS_LAYER_ID)) {
      map.removeLayer(BUILDINGS_LAYER_ID);
    }
    if (map.getSource(BUILDINGS_SOURCE_ID)) {
      map.removeSource(BUILDINGS_SOURCE_ID);
    }
    if (map.getSource(TERRAIN_SOURCE_ID)) {
      map.removeSource(TERRAIN_SOURCE_ID);
    }
    return;
  }

  if (TERRAIN_ENABLED && !map.getSource(TERRAIN_SOURCE_ID)) {
    map.addSource(TERRAIN_SOURCE_ID, {
      type: "raster-dem",
      url: TERRAIN_TILEJSON_URL,
      encoding: TERRAIN_ENCODING,
      tileSize: TERRAIN_TILE_SIZE,
    });
  }

  if (!map.getSource(BUILDINGS_SOURCE_ID)) {
    map.addSource(BUILDINGS_SOURCE_ID, {
      type: "vector",
      url: BUILDINGS_TILEJSON_URL,
    });
  }

  if (!map.getLayer(BUILDINGS_LAYER_ID)) {
    map.addLayer(
      {
        id: BUILDINGS_LAYER_ID,
        type: "fill-extrusion",
        source: BUILDINGS_SOURCE_ID,
        "source-layer": "building",
        minzoom: BUILDINGS_3D_MIN_ZOOM,
        filter: ["!=", ["get", "hide_3d"], true],
        paint: {
          "fill-extrusion-color": "#94a3b8",
          "fill-extrusion-height": [
            "interpolate",
            ["linear"],
            ["zoom"],
            BUILDINGS_3D_MIN_ZOOM,
            0,
            BUILDINGS_FULL_HEIGHT_ZOOM,
            ["max", ["coalesce", ["get", "render_height"], 9], 9],
          ],
          "fill-extrusion-base": [
            "interpolate",
            ["linear"],
            ["zoom"],
            BUILDINGS_3D_MIN_ZOOM,
            0,
            BUILDINGS_FULL_HEIGHT_ZOOM,
            ["coalesce", ["get", "render_min_height"], 0],
          ],
          "fill-extrusion-opacity": 0.9,
          "fill-extrusion-vertical-gradient": true,
        },
      },
      firstSymbolLayerId(map),
    );
  } else {
    map.setLayoutProperty(BUILDINGS_LAYER_ID, "visibility", "visible");
  }

  if (TERRAIN_ENABLED) {
    map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: 1.05 });
  } else {
    map.setTerrain(null);
  }
}

/** Animate the camera between a familiar north-up 2D view and an oblique 3D view. */
export function transitionMapDimension(map: maplibregl.Map, enabled: boolean): void {
  map.easeTo({
    zoom: enabled ? Math.max(map.getZoom(), BUILDINGS_FULL_HEIGHT_ZOOM) : map.getZoom(),
    pitch: enabled ? 55 : 0,
    bearing: enabled ? -15 : 0,
    duration: 650,
    essential: true,
  });
}
