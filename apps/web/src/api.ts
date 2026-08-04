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

export type Scorecard = {
  location: { district: string | null; state: string | null; geohash8: string | null };
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
