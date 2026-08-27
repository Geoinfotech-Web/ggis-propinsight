import maplibregl from "maplibre-gl";

const SOURCE_ID = "analysis-buffer-source";
const FILL_LAYER_ID = "analysis-buffer-fill";
const LINE_LAYER_ID = "analysis-buffer-line";
const LABEL_LAYER_ID = "analysis-buffer-label";
const EARTH_RADIUS_M = 6_371_008.8;
const BUFFER_TEXT_FONT = ["Noto Sans Regular"];

function destinationPoint(
  lon: number,
  lat: number,
  distanceM: number,
  bearingDeg: number,
): [number, number] {
  const angularDistance = distanceM / EARTH_RADIUS_M;
  const bearing = (bearingDeg * Math.PI) / 180;
  const lat1 = (lat * Math.PI) / 180;
  const lon1 = (lon * Math.PI) / 180;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angularDistance) +
      Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
      Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2),
    );
  return [(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI];
}

function bufferData(lon: number, lat: number, radiusKm: number): GeoJSON.FeatureCollection {
  const radiusM = radiusKm * 1_000;
  const ring: [number, number][] = [];
  for (let index = 0; index <= 72; index += 1) {
    ring.push(destinationPoint(lon, lat, radiusM, (index / 72) * 360));
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { kind: "area" },
        geometry: { type: "Polygon", coordinates: [ring] },
      },
      {
        type: "Feature",
        properties: { kind: "label", label: `${radiusKm} km analysis area` },
        geometry: {
          type: "Point",
          coordinates: destinationPoint(lon, lat, radiusM, 0),
        },
      },
    ],
  };
}

export function analysisBufferBounds(
  lon: number,
  lat: number,
  radiusKm: number,
): maplibregl.LngLatBoundsLike {
  const radiusM = radiusKm * 1_000;
  const south = destinationPoint(lon, lat, radiusM, 180);
  const north = destinationPoint(lon, lat, radiusM, 0);
  const west = destinationPoint(lon, lat, radiusM, 270);
  const east = destinationPoint(lon, lat, radiusM, 90);
  return [
    [west[0], south[1]],
    [east[0], north[1]],
  ];
}

/** Keep the ring above later overlays (land use / land cover). */
export function raiseAnalysisBuffer(map: maplibregl.Map): void {
  for (const layerId of [FILL_LAYER_ID, LINE_LAYER_ID, LABEL_LAYER_ID]) {
    if (map.getLayer(layerId)) map.moveLayer(layerId);
  }
}

export function showAnalysisBuffer(
  map: maplibregl.Map,
  lon: number,
  lat: number,
  radiusKm: number,
  dark: boolean,
): void {
  if (!map.isStyleLoaded()) {
    map.once("style.load", () => showAnalysisBuffer(map, lon, lat, radiusKm, dark));
    return;
  }
  const data = bufferData(lon, lat, radiusKm);
  const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
  } else {
    map.addSource(SOURCE_ID, { type: "geojson", data });
  }

  if (!map.getLayer(FILL_LAYER_ID)) {
    map.addLayer({
      id: FILL_LAYER_ID,
      type: "fill",
      source: SOURCE_ID,
      filter: ["==", ["get", "kind"], "area"],
      paint: {
        "fill-color": dark ? "#38bdf8" : "#0369a1",
        "fill-opacity": 0.06,
      },
    });
  } else {
    map.setPaintProperty(FILL_LAYER_ID, "fill-color", dark ? "#38bdf8" : "#0369a1");
  }

  if (!map.getLayer(LINE_LAYER_ID)) {
    map.addLayer({
      id: LINE_LAYER_ID,
      type: "line",
      source: SOURCE_ID,
      filter: ["==", ["get", "kind"], "area"],
      paint: {
        "line-color": dark ? "#7dd3fc" : "#0369a1",
        "line-width": 2.5,
        "line-dasharray": [2, 1.5],
        "line-opacity": 1,
      },
    });
  } else {
    map.setPaintProperty(LINE_LAYER_ID, "line-color", dark ? "#7dd3fc" : "#0369a1");
  }

  if (!map.getLayer(LABEL_LAYER_ID)) {
    try {
      map.addLayer({
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: SOURCE_ID,
        filter: ["==", ["get", "kind"], "label"],
        layout: {
          "text-field": ["get", "label"],
          "text-font": BUFFER_TEXT_FONT,
          "text-size": 12,
          "text-offset": [0, -0.6],
          "text-anchor": "bottom",
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": dark ? "#e0f2fe" : "#075985",
          "text-halo-color": dark ? "#0f172a" : "#ffffff",
          "text-halo-width": 1.5,
        },
      });
    } catch {
      // Label is optional; the dashed ring is the important cue.
    }
  } else {
    map.setPaintProperty(LABEL_LAYER_ID, "text-color", dark ? "#e0f2fe" : "#075985");
    map.setPaintProperty(LABEL_LAYER_ID, "text-halo-color", dark ? "#0f172a" : "#ffffff");
  }

  raiseAnalysisBuffer(map);
}

export function hideAnalysisBuffer(map: maplibregl.Map): void {
  if (!map.isStyleLoaded()) return;
  for (const layerId of [LABEL_LAYER_ID, LINE_LAYER_ID, FILL_LAYER_ID]) {
    if (map.getLayer(layerId)) map.removeLayer(layerId);
  }
  if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
}
