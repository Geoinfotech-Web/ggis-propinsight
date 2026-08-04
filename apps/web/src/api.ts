// Thin client for the AIA API (TDD §7). Types mirror the scorecard schema.

export type DomainResult = {
  score: number | null;
  confidence: string;
  status: "ok" | "degraded" | "pending";
  evidence: Record<string, unknown>;
  note: string | null;
};

export type PersonaInfo = {
  key: string;
  label: string;
  blurb: string;
};

export type LandUseInfo = {
  category: string;
  label: string;
  name: string | null;
  source_class: string | null;
  source_subtype: string | null;
  designation: string;
  source: string;
  source_url: string | null;
  effective_date: string | null;
  advisory: string;
};

export type LandUseFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    id: string;
    geometry: GeoJSON.Geometry;
    properties: LandUseInfo;
  }>;
  metadata: {
    status: "published" | "unpublished";
    version: string | null;
    feature_count?: number;
    designation?: string;
    advisory: string;
  };
};

export type Scorecard = {
  location: {
    district: string | null;
    state: string | null;
    geohash8: string | null;
    land_use?: LandUseInfo | null;
  };
  domains: Record<string, DomainResult>;
  layer_versions: Record<string, string>;
  scoring_profile: string;
  cached: boolean;
  persona?: PersonaInfo | null;
  fit_score?: number | null;
  summary?: string | null;
  domain_priority?: string[];
};

export const DOMAIN_ORDER = [
  "flood",
  "security",
  "amenities",
  "accessibility",
  "tenure",
  "market",
  "livability",
  "feasibility",
] as const;

export async function analyzePoint(
  lng: number,
  lat: number,
  profile = "home_buyer",
): Promise<Scorecard> {
  const res = await fetch("/v1/locations/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      geometry: { type: "Point", coordinates: [lng, lat] },
      profile,
    }),
  });
  if (!res.ok) throw new Error(`analyze failed: ${res.status}`);
  return res.json();
}

export async function fetchLandUse(
  bounds: [number, number, number, number],
): Promise<LandUseFeatureCollection> {
  const params = new URLSearchParams({
    min_lon: bounds[0].toString(),
    min_lat: bounds[1].toString(),
    max_lon: bounds[2].toString(),
    max_lat: bounds[3].toString(),
    limit: "5000",
  });
  const res = await fetch(`/v1/locations/land-use?${params}`);
  if (!res.ok) throw new Error(`land-use layer failed: ${res.status}`);
  return res.json();
}
