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
};

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
