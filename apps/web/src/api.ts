// Thin client for the AIA API (TDD §7). Types mirror the scorecard schema.

export type DomainResult = {
  score: number | null;
  confidence: string;
  status: "ok" | "degraded" | "pending" | "demo";
  score_direction: "higher_is_better" | "higher_is_worse";
  rating: string | null;
  included_in_fit: boolean;
  evidence: Record<string, unknown>;
  note: string | null;
};

export type PersonaInfo = {
  key: string;
  label: string;
  blurb: string;
};

export type DevelopmentProject = {
  official_id: string;
  name: string;
  authority: string;
  agency: string | null;
  sector: string;
  lifecycle_stage: "budgeted" | "procurement" | "awarded" | "ongoing";
  status: string | null;
  budget_ngn: number | null;
  location_text: string;
  ward: string | null;
  area_council: string | null;
  location_precision: string;
  distance_m: number | null;
  geometry: GeoJSON.Geometry | null;
  source_url: string;
  source_published_at: string;
  source_updated_at: string | null;
  verified_at: string;
};

export type DevelopmentOutlook = {
  radius_m: number;
  status: "ok" | "pending" | "degraded";
  confidence: string;
  population: {
    estimate_2025: number | null;
    projection_2030: number | null;
    change: number | null;
    change_pct: number | null;
    cagr_pct: number | null;
    source: string;
    modelled: boolean;
  } | null;
  settlement: {
    built_share_current_pct: number | null;
    built_change_pct: number | null;
    source: string;
    modelled: boolean;
  } | null;
  migration_pressure: {
    band: "Low" | "Moderate" | "High";
    index: number;
    confidence: string;
    components: Record<string, number>;
    advisory: string;
  } | null;
  projects: {
    counts_by_sector: Record<string, number>;
    counts_by_stage: Record<string, number>;
    nearby: DevelopmentProject[];
    broader_area: DevelopmentProject[];
    total_count: number;
    returned_count: number;
    advisory: string;
  };
  data_period: string | null;
  sources: string[];
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
    designations?: string[];
    advisory: string;
  };
};

export type Professional3DFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    id: string;
    geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
    properties: Record<string, unknown>;
  }>;
  metadata: {
    status: "published" | "unpublished";
    version: string | null;
    source?: string | null;
    source_url?: string;
    total_count: number;
    feature_count: number;
    truncated: boolean;
    advisory: string;
  };
};

export type LandCoverInfo = {
  class_value: number;
  category: string;
  label: string;
  designation: "observed_land_cover";
  source: string;
  source_url: string | null;
  period_start: string | null;
  period_end: string | null;
  resolution_m: number;
  advisory: string;
};

export type Scorecard = {
  location: {
    district: string | null;
    ward?: string | null;
    area_council?: string | null;
    state: string | null;
    geohash8: string | null;
    land_use?: LandUseInfo | null;
    land_cover?: LandCoverInfo | null;
    planning_status: "official" | "mapped_reference" | "observed_cover_only" | "unmapped";
  };
  domains: Record<string, DomainResult>;
  analysis_radius_m: number;
  layer_versions: Record<string, string>;
  scoring_profile: string;
  cached: boolean;
  persona?: PersonaInfo | null;
  fit_score?: number | null;
  summary?: string | null;
  highlights?: Array<{
    domain: string;
    title: string;
    text: string;
    tone: "positive" | "neutral" | "caution";
  }>;
  domain_priority?: string[];
  development_outlook?: DevelopmentOutlook | null;
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
  radiusM = 5_000,
  signal?: AbortSignal,
): Promise<Scorecard> {
  const res = await fetch("/v1/locations/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      geometry: { type: "Point", coordinates: [lng, lat] },
      profile,
      radius_m: radiusM,
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

async function fetchProfessional3DLayer(
  layer: "buildings" | "vegetation",
  bounds: [number, number, number, number],
  lon: number,
  lat: number,
  signal?: AbortSignal,
): Promise<Professional3DFeatureCollection> {
  const params = new URLSearchParams({
    min_lon: bounds[0].toString(),
    min_lat: bounds[1].toString(),
    max_lon: bounds[2].toString(),
    max_lat: bounds[3].toString(),
    lon: lon.toString(),
    lat: lat.toString(),
  });
  const response = await fetch(`/v1/locations/3d/${layer}?${params}`, { signal });
  if (!response.ok) throw new Error(`${layer} 3D layer failed: ${response.status}`);
  return response.json();
}

export function fetchProfessionalBuildings(
  bounds: [number, number, number, number],
  lon: number,
  lat: number,
  signal?: AbortSignal,
) {
  return fetchProfessional3DLayer("buildings", bounds, lon, lat, signal);
}

export function fetchProfessionalVegetation(
  bounds: [number, number, number, number],
  lon: number,
  lat: number,
  signal?: AbortSignal,
) {
  return fetchProfessional3DLayer("vegetation", bounds, lon, lat, signal);
}
