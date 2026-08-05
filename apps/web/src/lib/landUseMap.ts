import maplibregl from "maplibre-gl";
import type { LandUseFeatureCollection } from "../api";

export const LAND_USE_SOURCE_ID = "aia-land-use";
export const LAND_USE_FILL_ID = "aia-land-use-fill";
export const LAND_USE_LINE_ID = "aia-land-use-line";

export const LAND_USE_COLORS: Record<string, string> = {
  residential: "#eab308",
  commercial: "#ef4444",
  industrial: "#8b5cf6",
  institutional: "#3b82f6",
  protected_reserve: "#15803d",
  recreation_open_space: "#4ade80",
  agricultural: "#84cc16",
  military_restricted: "#64748b",
  transportation: "#78716c",
  construction_development: "#f97316",
  extractive: "#92400e",
  landfill: "#713f12",
  cemetery: "#0f766e",
  other: "#94a3b8",
};

export const LAND_USE_LEGEND = [
  ["residential", "Residential"],
  ["commercial", "Commercial / retail"],
  ["industrial", "Industrial"],
  ["institutional", "Institutional / public service"],
  ["protected_reserve", "Protected / reserve"],
  ["recreation_open_space", "Recreation / open space"],
  ["agricultural", "Agricultural"],
  ["military_restricted", "Military / restricted"],
  ["construction_development", "Construction / development"],
] as const;

const colorExpression: maplibregl.ExpressionSpecification = [
  "match",
  ["get", "category"],
  ...Object.entries(LAND_USE_COLORS).flatMap(([category, color]) => [category, color]),
  LAND_USE_COLORS.other,
] as unknown as maplibregl.ExpressionSpecification;

export function showLandUseLayer(
  map: maplibregl.Map,
  data: LandUseFeatureCollection,
): void {
  const source = map.getSource(LAND_USE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  if (source) {
    source.setData(data as GeoJSON.FeatureCollection);
  } else {
    map.addSource(LAND_USE_SOURCE_ID, {
      type: "geojson",
      data: data as GeoJSON.FeatureCollection,
      promoteId: "id",
    });
  }
  if (!map.getLayer(LAND_USE_FILL_ID)) {
    map.addLayer({
      id: LAND_USE_FILL_ID,
      type: "fill",
      source: LAND_USE_SOURCE_ID,
      paint: {
        "fill-color": colorExpression,
        "fill-opacity": [
          "case",
          ["==", ["get", "designation"], "official_masterplan"],
          0.52,
          0.3,
        ],
      },
    });
  } else {
    map.setLayoutProperty(LAND_USE_FILL_ID, "visibility", "visible");
  }
  if (!map.getLayer(LAND_USE_LINE_ID)) {
    map.addLayer({
      id: LAND_USE_LINE_ID,
      type: "line",
      source: LAND_USE_SOURCE_ID,
      paint: {
        "line-color": colorExpression,
        "line-opacity": 0.75,
        "line-width": [
          "case",
          ["==", ["get", "designation"], "official_masterplan"],
          2,
          ["interpolate", ["linear"], ["zoom"], 8, 0.3, 14, 1.1],
        ],
      },
    });
  } else {
    map.setLayoutProperty(LAND_USE_LINE_ID, "visibility", "visible");
  }
}

export function hideLandUseLayer(map: maplibregl.Map): void {
  for (const id of [LAND_USE_FILL_ID, LAND_USE_LINE_ID]) {
    if (!map.getLayer(id)) continue;
    try {
      map.setLayoutProperty(id, "visibility", "none");
    } catch {
      // A basemap style swap can remove the layer between lookup and mutation.
    }
  }
}
