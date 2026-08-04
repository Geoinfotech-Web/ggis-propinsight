/** Nearby amenity POIs for map overlay (from amenities evidence.nearby). */

export type NearbyAmenity = {
  category: string;
  name: string;
  distance_m: number;
  lon: number;
  lat: number;
};

export const AMENITY_MARKER_COLORS: Record<string, string> = {
  school: "#0369a1",
  hospital: "#dc2626",
  market: "#ca8a04",
  bank: "#0d9488",
  power: "#7c3aed",
  fuel: "#ea580c",
  police: "#4f46e5",
};

/** Simple, dependency-free map symbols: cap, medical cross, bank, shop, bolt, pump, shield. */
export const POI_SYMBOL_PATHS: Record<string, string[]> = {
  school: [
    "m2 10 10-5 10 5-10 5L2 10Z",
    "M6 12.5V17c3.5 2.5 8.5 2.5 12 0v-4.5",
    "M22 10v6",
  ],
  hospital: ["M12 4v16", "M4 12h16"],
  bank: [
    "M3 9h18L12 3 3 9Z",
    "M5 10v8M9 10v8M15 10v8M19 10v8",
    "M3 21h18M2 18h20",
  ],
  market: [
    "M4 10v10h16V10",
    "M3 4h18l-2 6H5L3 4Z",
    "M8 20v-6h8v6",
    "M5 10c0 2 3 2 3 0 0 2 4 2 4 0 0 2 4 2 4 0 0 2 3 2 3 0",
  ],
  power: ["m13 2-8 12h7l-1 8 8-12h-7l1-8Z"],
  fuel: [
    "M5 3h9v18H5V3Z",
    "M7 6h5v5H7V6Z",
    "M14 8h2l3 3v7a2 2 0 0 0 4 0v-6l-3-3",
    "M3 21h13",
  ],
  police: ["M12 2 20 5v6c0 5.2-3.4 9.5-8 11-4.6-1.5-8-5.8-8-11V5l8-3Z", "m9 12 2 2 4-5"],
};

export function createPoiSymbolElement(category: string, size = 14): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const pathData of POI_SYMBOL_PATHS[category] ?? POI_SYMBOL_PATHS.market) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    svg.appendChild(path);
  }
  return svg;
}

export function nearbyFromScorecard(evidence: Record<string, unknown> | undefined): NearbyAmenity[] {
  if (!evidence || !Array.isArray(evidence.nearby)) return [];
  return evidence.nearby
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const o = item as Record<string, unknown>;
      if (typeof o.category !== "string" || typeof o.distance_m !== "number") return null;
      if (typeof o.lon !== "number" || typeof o.lat !== "number") return null;
      const name =
        typeof o.name === "string" && o.name.trim() ? o.name.trim() : o.category;
      return {
        category: o.category,
        name,
        distance_m: o.distance_m,
        lon: o.lon,
        lat: o.lat,
      };
    })
    .filter((x): x is NearbyAmenity => x !== null);
}

export function nearbyToGeoJSON(pois: NearbyAmenity[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: pois.map((p, i) => ({
      type: "Feature",
      id: i,
      properties: {
        name: p.name,
        category: p.category,
        distance_m: p.distance_m,
        color: AMENITY_MARKER_COLORS[p.category] ?? "#0d9488",
      },
      geometry: {
        type: "Point",
        coordinates: [p.lon, p.lat],
      },
    })),
  };
}

export const AMENITY_SOURCE_ID = "amenities-nearby";
export const AMENITY_CIRCLE_LAYER = "amenities-nearby-circle";
export const AMENITY_LABEL_LAYER = "amenities-nearby-label";

export const SECURITY_SOURCE_ID = "security-nearby";
export const SECURITY_CIRCLE_LAYER = "security-nearby-circle";
export const SECURITY_LABEL_LAYER = "security-nearby-label";
