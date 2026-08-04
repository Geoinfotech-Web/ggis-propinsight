import { useState } from "react";
import clsx from "clsx";
import { DOMAIN_ORDER, type DomainResult, type Scorecard } from "../api";
import { getPersona, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";

const DOMAIN_LABELS: Record<(typeof DOMAIN_ORDER)[number], string> = {
  flood: "Flood",
  security: "Security",
  amenities: "Amenities",
  accessibility: "Accessibility",
  tenure: "Tenure",
  market: "Market",
  livability: "Livability",
  feasibility: "Feasibility",
};

const DOMAIN_KICKERS: Record<(typeof DOMAIN_ORDER)[number], string> = {
  flood: "Hazard · GGIS Flood Watch",
  security: "Safety · district aggregates",
  amenities: "Services · nearest POIs",
  accessibility: "Connectivity · roads & destinations",
  tenure: "Planning · overlays",
  market: "Prices · samples",
  livability: "Community · reviews",
  feasibility: "Buildability · terrain",
};

const AMENITY_LABELS: Record<string, string> = {
  school: "School",
  hospital: "Hospital / clinic",
  water: "Water point",
  power: "Power",
  isp: "Internet / ISP",
  market: "Market",
  bank: "Bank",
  fuel: "Fuel station",
};

const ACCESS_LABELS: Record<string, string> = {
  road_distance: "Nearest road",
  cbd_time: "CBD (est.)",
  airport_time: "Airport (est.)",
  market_time: "Market (est.)",
  rainy_season: "Rainy-season access",
};

const FLOOD_LABELS: Record<string, string> = {
  risk_class: "Risk class",
  risk_score: "Hazard score",
  elevation_m: "Elevation",
  dist_to_drainage_m: "Distance to drainage",
  flow_accumulation_pct: "Flow accumulation",
  historical_inundation_events: "Past inundation events",
  model_version: "Model version",
  data_currency: "Data currency",
  last_event: "Last event",
  history_events: "History",
};

const FEASIBILITY_LABELS: Record<string, string> = {
  slope: "Slope",
  flood: "Flood contribution",
  utility_distance: "Nearest utility",
  catchment: "Wetness (TWI)",
};

const SECURITY_LABELS: Record<string, string> = {
  safety_level: "Safety level",
  reported_incidents: "Reported incidents",
  most_common: "Most common",
  nearest_police: "Nearest police",
  coverage: "Based on",
};

const TENURE_LABELS: Record<string, string> = {
  headline: "Status",
  advisory: "Advisory",
  overlays: "Planning overlays",
};

const MARKET_LABELS: Record<string, string> = {
  headline: "Market read",
  estimated_price: "Spatial estimate",
  price_range: "Nearby price range",
  trend: "Price trend",
  gross_yield: "Gross yield",
  sample_count: "Nearby samples",
  sample_mix: "Property sample",
  record_mix: "Record type",
  verified_samples: "Partner verified",
  sources: "Sources",
  coverage_radius_m: "Coverage radius",
  as_of: "Latest observation",
  method: "Method",
};
function scoreBarColor(score: number | null, status: DomainResult["status"]): string {
  if (status === "pending" || score === null) return "#94a3b8";
  if (score >= 70) return "#0d9488";
  if (score >= 40) return "#ca8a04";
  return "#dc2626";
}

/**
 * Badge that reflects score quality (not just data availability): a scored
 * domain shows Strong / Moderate / Weak, so a poor score never reads as a
 * green "OK". Degraded / pending keep their own meaning.
 */
function qualityBadge(
  score: number | null,
  status: DomainResult["status"],
  dark: boolean,
): { label: string; classes: string } {
  if (status === "pending") {
    return {
      label: "No data",
      classes: dark
        ? "border-gray-700 bg-gray-900 text-gray-400"
        : "border-slate-200 bg-slate-100 text-slate-600",
    };
  }
  if (status === "degraded" || score === null) {
    return {
      label: status === "degraded" ? "Limited" : "No score",
      classes: dark
        ? "border-amber-700/60 bg-amber-950/40 text-amber-300"
        : "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  if (score >= 70) {
    return {
      label: "Strong",
      classes: dark
        ? "border-teal-700/60 bg-teal-950/50 text-teal-300"
        : "border-teal-200 bg-teal-50 text-teal-800",
    };
  }
  if (score >= 40) {
    return {
      label: "Moderate",
      classes: dark
        ? "border-amber-700/60 bg-amber-950/40 text-amber-300"
        : "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  return {
    label: "Weak",
    classes: dark
      ? "border-red-800/60 bg-red-950/40 text-red-300"
      : "border-red-200 bg-red-50 text-red-700",
  };
}

function formatMetres(m: number): string {
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toFixed(1)} km`;
}

function formatEvidenceValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object" && value !== null) {
    const obj = value as Record<string, unknown>;
    if (typeof obj.min === "number" && typeof obj.max === "number" && typeof obj.unit === "string") {
      return `${formatMarketPrice(obj.min, obj.unit)} – ${formatMarketPrice(obj.max, obj.unit)}`;
    }
    if (typeof obj.distance_m === "number") {
      const parts: string[] = [];
      if (typeof obj.name === "string" && obj.name.trim()) parts.push(obj.name.trim());
      parts.push(formatMetres(obj.distance_m));
      if (typeof obj.est_minutes === "number") parts.push(`~${obj.est_minutes} min`);
      return parts.join(" · ");
    }
    if (typeof obj.slope_deg === "number") return `${obj.slope_deg.toFixed(1)}°`;
    if (typeof obj.twi === "number") return `TWI ${obj.twi.toFixed(1)}`;
    if (typeof obj.flood_normalised === "number") return `${(obj.flood_normalised * 100).toFixed(0)} / 100`;
    if (typeof obj.value === "number" && typeof obj.unit === "string") {
      const formatted = obj.unit.toUpperCase().startsWith("NGN")
        ? new Intl.NumberFormat("en-NG", {
            style: "currency",
            currency: "NGN",
            maximumFractionDigits: 0,
          }).format(obj.value)
        : `${new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 }).format(obj.value)} ${obj.unit}`;
      return typeof obj.kind === "string" ? `${formatted} · ${obj.kind}` : formatted;
    }
    if ("date" in obj && "severity" in obj) {
      return `${obj.date} · ${obj.severity}${obj.source ? ` (${obj.source})` : ""}`;
    }
    if (Array.isArray(value)) {
      return value
        .slice(0, 3)
        .map((e) => formatEvidenceValue(key, e))
        .join("; ");
    }
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (key.endsWith("_m") || key.includes("distance") || key.includes("elevation")) {
      return key.includes("elevation") ? `${value.toFixed(0)} m` : formatMetres(value);
    }
    if (key.includes("pct") || key.includes("score")) return value.toFixed(2);
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  return String(value);
}

function labelFor(domain: string, key: string): string {
  if (domain === "amenities") return AMENITY_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "accessibility") return ACCESS_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "flood") return FLOOD_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "feasibility") return FEASIBILITY_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "security") return SECURITY_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "tenure") return TENURE_LABELS[key] ?? key.replace(/_/g, " ");
  if (domain === "market") return MARKET_LABELS[key] ?? key.replace(/_/g, " ");
  return key.replace(/_/g, " ");
}

const SECURITY_ORDER = [
  "safety_level",
  "reported_incidents",
  "most_common",
  "nearest_police",
  "coverage",
] as const;

function tenureRows(
  evidence: Record<string, unknown>,
): Array<{ key: string; label: string; value: string }> {
  const rows: Array<{ key: string; label: string; value: string }> = [];
  if (typeof evidence.headline === "string") {
    rows.push({ key: "headline", label: "Status", value: evidence.headline });
  }
  const overlays = Array.isArray(evidence.overlays) ? evidence.overlays : [];
  const text =
    overlays.length === 0
      ? "None mapped at this point"
      : overlays
          .map((o) => {
            const x = o as Record<string, unknown>;
            const kind = String(x.kind ?? "").replace(/_/g, " ");
            return x.status ? `${kind} (${x.status})` : kind;
          })
          .join("; ");
  rows.push({ key: "overlays", label: "Planning overlays", value: text });
  return rows;
}

type NearbyPoi = {
  category: string;
  name: string;
  distance_m: number;
  lon: number;
  lat: number;
};

type MarketListing = {
  id?: string;
  title: string;
  area?: string;
  address?: string;
  bedrooms?: number;
  property_type?: string;
  price: number;
  unit: string;
  observed_at?: string;
  source_url?: string;
};

function formatMarketPrice(value: number, unit: string): string {
  const amount = unit.toUpperCase().startsWith("NGN")
    ? new Intl.NumberFormat("en-NG", {
        style: "currency",
        currency: "NGN",
        maximumFractionDigits: 0,
      }).format(value)
    : `${new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 }).format(value)} ${unit}`;
  return unit.toLowerCase().includes("year") ? `${amount} / year` : amount;
}

function parseMarketListings(evidence: Record<string, unknown>): MarketListing[] {
  if (!Array.isArray(evidence.listings)) return [];
  return evidence.listings
    .map<MarketListing | null>((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      if (typeof row.title !== "string" || typeof row.price !== "number" || typeof row.unit !== "string") return null;
      return {
        id: typeof row.id === "string" ? row.id : undefined,
        title: row.title,
        area: typeof row.area === "string" ? row.area : undefined,
        address: typeof row.address === "string" ? row.address : undefined,
        bedrooms: typeof row.bedrooms === "number" ? row.bedrooms : undefined,
        property_type: typeof row.property_type === "string" ? row.property_type : undefined,
        price: row.price,
        unit: row.unit,
        observed_at: typeof row.observed_at === "string" ? row.observed_at : undefined,
        source_url: typeof row.source_url === "string" ? row.source_url : undefined,
      };
    })
    .filter((item): item is MarketListing => item !== null);
}

const NEARBY_ORDER = ["school", "hospital", "market", "bank"] as const;

function parseNearby(
  evidence: Record<string, unknown>,
  amenityOrder: readonly string[] = NEARBY_ORDER,
): NearbyPoi[] {
  const raw = evidence.nearby;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const o = item as Record<string, unknown>;
      if (typeof o.category !== "string" || typeof o.distance_m !== "number") return null;
      if (typeof o.lon !== "number" || typeof o.lat !== "number") return null;
      const name = typeof o.name === "string" && o.name.trim() ? o.name.trim() : AMENITY_LABELS[o.category] ?? o.category;
      return { category: o.category, name, distance_m: o.distance_m, lon: o.lon, lat: o.lat };
    })
    .filter((x): x is NearbyPoi => x !== null)
    .sort((a, b) => {
      const ai = amenityOrder.indexOf(a.category);
      const bi = amenityOrder.indexOf(b.category);
      if (ai !== bi) return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
      return a.distance_m - b.distance_m;
    });
}

function evidenceRows(domain: string, evidence: Record<string, unknown>): Array<{ key: string; label: string; value: string }> {
  if (domain === "tenure") return tenureRows(evidence);

  const preferred =
    domain === "security"
      ? [...SECURITY_ORDER]
      : domain === "amenities"
      ? Object.keys(AMENITY_LABELS)
      : domain === "accessibility"
        ? Object.keys(ACCESS_LABELS)
        : domain === "flood"
          ? ["risk_class", "risk_score", "elevation_m", "dist_to_drainage_m", "flow_accumulation_pct", "historical_inundation_events", "last_event", "data_currency", "model_version"]
          : domain === "feasibility"
            ? Object.keys(FEASIBILITY_LABELS)
            : domain === "market"
              ? Object.keys(MARKET_LABELS)
            : Object.keys(evidence);

  const keys = preferred.filter((k) => k in evidence);
  for (const k of Object.keys(evidence)) {
    if (!keys.includes(k) && !["history_events", "nearby", "listings", "listing_kind"].includes(k)) keys.push(k);
  }

  return keys.map((key) => ({
    key,
    label: labelFor(domain, key),
    value: formatEvidenceValue(key, evidence[key]),
  }));
}

type Props = {
  theme: Theme;
  card: Scorecard | null;
  loading: boolean;
  error: string | null;
  placeLabel?: string | null;
  persona?: PersonaKey;
  onClose?: () => void;
  onViewNearbyList?: () => void;
};

const PREVIEW_PER_CATEGORY = 2;

function domainLabel(key: string): string {
  return DOMAIN_LABELS[key as (typeof DOMAIN_ORDER)[number]] ?? key.replace(/_/g, " ");
}

function domainKicker(key: string): string {
  return DOMAIN_KICKERS[key as (typeof DOMAIN_ORDER)[number]] ?? "Location intelligence";
}

export function ScorecardConsole({
  theme,
  card,
  loading,
  error,
  placeLabel,
  persona = "home_buyer",
  onClose,
  onViewNearbyList,
}: Props) {
  const dark = theme === "dark";
  const personaDef = getPersona(persona);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    amenities: true,
    accessibility: true,
    flood: true,
    feasibility: true,
    market: true,
  });

  const toggle = (id: string) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  const orderedDomains =
    card?.domain_priority && card.domain_priority.length > 0
      ? [...card.domain_priority]
      : card
        ? Object.keys(card.domains)
        : [...DOMAIN_ORDER];

  const topDomains = new Set(orderedDomains.slice(0, 3));
  const personaLabel = card?.persona?.label ?? personaDef.label;
  const showMarketListings = ["home_buyer", "tenant"].includes(
    card?.persona?.key ?? persona,
  );

  return (
    <aside
      className={clsx(
        "flex h-full w-full flex-col border-r",
        dark ? "border-gray-800 bg-gray-900/95 text-gray-100" : "border-slate-200 bg-white/95 text-slate-900",
      )}
    >
      <div
        className={clsx(
          "flex items-start justify-between gap-3 border-b px-5 py-4",
          dark ? "border-gray-800" : "border-slate-200",
        )}
      >
        <div>
          <p className="app-kicker">Location report</p>
          <h2 className="font-display text-xl font-semibold tracking-tight">Scorecard</h2>
          <p className={clsx("mt-0.5 text-[11px] leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
            {card?.persona?.blurb ?? personaDef.blurb}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className={clsx(
              "rounded-lg border px-2 py-1 text-xs font-semibold sm:hidden",
              dark ? "border-gray-700 text-gray-300" : "border-slate-200 text-slate-600",
            )}
          >
            Close
          </button>
        )}
      </div>

      <div className="scorecard-scroll flex-1 overflow-y-auto px-5 py-4">
        {!card && !loading && !error && (
          <p className={clsx("text-sm leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
            Search a place, use your current location, or click the map to generate a Location
            Intelligence Report.
          </p>
        )}

        {loading && (
          <div className={clsx("flex items-center gap-2 text-sm", dark ? "text-sky-400" : "text-sky-700")}>
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600" />
            Analysing location…
          </div>
        )}

        {error && <p className="text-sm text-status-emergency">Error: {error}</p>}

        {card && (
          <div className="space-y-4">
            <div
              className={clsx(
                "rounded-lg border px-3 py-2 text-[11px]",
                dark ? "border-gray-800 bg-gray-950/60 text-gray-400" : "border-slate-200 bg-slate-50 text-slate-500",
              )}
            >
              {placeLabel && (
                <p className={clsx("mb-1 truncate text-xs font-semibold", dark ? "text-gray-200" : "text-slate-800")}>
                  {placeLabel}
                </p>
              )}
              <div className="mb-2 flex items-end justify-between gap-3">
                <div>
                  <p
                    className={clsx(
                      "text-[10px] font-semibold uppercase tracking-[0.14em]",
                      dark ? "text-sky-400" : "text-sky-700",
                    )}
                  >
                    Fit for {personaLabel}
                  </p>
                  <p className="font-display text-3xl font-semibold tabular-nums leading-none">
                    {card.fit_score != null ? card.fit_score.toFixed(0) : "—"}
                  </p>
                </div>
                <div
                  className="h-2 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-gray-800"
                  aria-hidden
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${card.fit_score != null ? Math.max(4, card.fit_score) : 4}%`,
                      backgroundColor: scoreBarColor(card.fit_score ?? null, "ok"),
                    }}
                  />
                </div>
              </div>
              {card.summary && (
                <p
                  className={clsx(
                    "mb-2 text-[12px] font-medium leading-snug",
                    dark ? "text-gray-200" : "text-slate-700",
                  )}
                >
                  {card.summary}
                </p>
              )}
              <div className="tabular-nums">
                geohash <span className="font-semibold">{card.location.geohash8}</span>
                {card.location.district && <> · {card.location.district}</>}
              </div>
              {card.location.land_use && (
                <div
                  className={clsx(
                    "mt-2 rounded-md border px-2 py-1.5",
                    dark
                      ? "border-amber-800/70 bg-amber-950/30 text-amber-200"
                      : "border-amber-200 bg-amber-50 text-amber-900",
                  )}
                >
                  <p className="text-[10px] font-semibold uppercase tracking-wide">
                    Mapped land use
                  </p>
                  <p className="text-xs font-semibold">{card.location.land_use.label}</p>
                  {card.location.land_use.name && (
                    <p className="truncate text-[10px]">{card.location.land_use.name}</p>
                  )}
                  <p className="mt-1 text-[9px] leading-snug">
                    Reference context only—confirm zoning and development rights with AGIS/FCTA.
                  </p>
                </div>
              )}
              <div className="tabular-nums">
                profile <span className="font-semibold">{card.scoring_profile}</span>
                {card.cached && (
                  <>
                    {" "}
                    · <span className="text-status-normal">cached</span>
                  </>
                )}
              </div>
            </div>

            <div className="space-y-2">
              {orderedDomains.map((d) => {
                const r = card.domains[d];
                if (!r) return null;
                const isOpen = expanded[d] ?? false;
                const rows = evidenceRows(d, r.evidence ?? {});
                const bar = scoreBarColor(r.score, r.status);
                const highPriority = topDomains.has(d);

                return (
                  <section
                    key={d}
                    className={clsx(
                      "overflow-hidden rounded-xl border",
                      dark ? "border-gray-800" : "border-slate-200",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => toggle(d)}
                      className="flex w-full items-start gap-3 px-3 py-3 text-left"
                      aria-expanded={isOpen}
                    >
                      <div className="min-w-0 flex-1">
                        <p
                          className={clsx(
                            "text-[10px] font-semibold uppercase tracking-[0.14em]",
                            dark ? "text-sky-400" : "text-sky-700",
                          )}
                        >
                          {domainKicker(d)}
                        </p>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2">
                          <h3 className="font-display text-base font-semibold tracking-tight">
                            {domainLabel(d)}
                          </h3>
                          {(() => {
                            const badge = qualityBadge(r.score, r.status, dark);
                            return (
                              <span
                                className={clsx(
                                  "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                                  badge.classes,
                                )}
                              >
                                {badge.label}
                              </span>
                            );
                          })()}
                          {highPriority && (
                            <span
                              className={clsx(
                                "rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                                dark
                                  ? "border-sky-700/50 bg-sky-950/40 text-sky-300"
                                  : "border-sky-200 bg-sky-50 text-sky-800",
                              )}
                            >
                              High priority · {personaLabel}
                            </span>
                          )}
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-gray-800">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${r.score !== null ? Math.max(4, r.score) : 4}%`,
                              backgroundColor: bar,
                            }}
                          />
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="font-display text-2xl font-semibold tabular-nums leading-none">
                          {r.score !== null ? r.score.toFixed(0) : "—"}
                        </p>
                        <p className={clsx("mt-1 text-[10px] uppercase tracking-wide", dark ? "text-gray-500" : "text-slate-400")}>
                          {isOpen ? "Hide" : "Details"}
                        </p>
                      </div>
                    </button>

                    {isOpen && (
                      <div className={clsx("border-t px-3 py-2.5", dark ? "border-gray-800" : "border-slate-100")}>
                        {r.note && (
                          <p className={clsx("mb-2 text-xs leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
                            {r.note}
                          </p>
                        )}

                        {r.status === "pending" && rows.length === 0 ? (
                          <p className={clsx("text-[11px]", dark ? "text-gray-500" : "text-slate-400")}>
                            No indicators yet — waiting on published data layers.
                          </p>
                        ) : (
                          <table className="w-full border-collapse text-left">
                            <tbody>
                              {rows.map((row) => (
                                <tr
                                  key={row.key}
                                  className={clsx(
                                    "border-b last:border-0",
                                    dark ? "border-gray-800/80" : "border-slate-100",
                                  )}
                                >
                                  <th
                                    scope="row"
                                    className={clsx(
                                      "py-1.5 pr-3 text-[10px] font-semibold uppercase tracking-widest",
                                      dark ? "text-gray-500" : "text-slate-400",
                                    )}
                                  >
                                    {row.label}
                                  </th>
                                  <td className="py-1.5 text-right text-[11px] tabular-nums font-medium">
                                    {row.value}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}

                        {d === "amenities" && (() => {
                          const nearby = parseNearby(r.evidence ?? {}, personaDef.amenityOrder);
                          const groups = personaDef.amenityOrder
                            .map((cat) => ({
                              cat,
                              items: nearby.filter((p) => p.category === cat),
                            }))
                            .filter((g) => g.items.length > 0);
                          const hasMore = groups.some((g) => g.items.length > PREVIEW_PER_CATEGORY)
                            || nearby.length > PREVIEW_PER_CATEGORY * 2;
                          return (
                            <div className={clsx("mt-3 border-t pt-2.5", dark ? "border-gray-800" : "border-slate-100")}>
                              <div className="mb-1.5 flex items-center justify-between gap-2">
                                <p
                                  className={clsx(
                                    "text-[10px] font-semibold uppercase tracking-widest",
                                    dark ? "text-gray-500" : "text-slate-400",
                                  )}
                                >
                                  Nearby (5 km)
                                </p>
                                {nearby.length > 0 && onViewNearbyList && (
                                  <button
                                    type="button"
                                    onClick={onViewNearbyList}
                                    className={clsx(
                                      "rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                                      dark
                                        ? "border-sky-700/60 bg-sky-950/40 text-sky-300 hover:bg-sky-900/50"
                                        : "border-sky-200 bg-sky-50 text-sky-800 hover:bg-sky-100",
                                    )}
                                  >
                                    View list · {nearby.length}
                                  </button>
                                )}
                              </div>
                              {groups.length === 0 ? (
                                <p className={clsx("text-[11px]", dark ? "text-gray-500" : "text-slate-400")}>
                                  No named schools, hospitals, markets, or banks within 5 km.
                                </p>
                              ) : (
                                <div className="space-y-2.5">
                                  {groups.map(({ cat, items }) => {
                                    const preview = items.slice(0, PREVIEW_PER_CATEGORY);
                                    const extra = items.length - preview.length;
                                    return (
                                      <div key={cat}>
                                        <p
                                          className={clsx(
                                            "mb-1 text-[10px] font-semibold",
                                            dark ? "text-sky-400" : "text-sky-700",
                                          )}
                                        >
                                          {AMENITY_LABELS[cat] ?? cat}
                                          {items.length > 1 ? ` · ${items.length}` : ""}
                                        </p>
                                        <ul className="space-y-1">
                                          {preview.map((p) => (
                                            <li
                                              key={`${p.category}-${p.name}-${p.distance_m}`}
                                              className="flex items-baseline justify-between gap-2 text-[11px]"
                                            >
                                              <span className={clsx("min-w-0 truncate", dark ? "text-gray-200" : "text-slate-800")}>
                                                {p.name}
                                              </span>
                                              <span
                                                className={clsx(
                                                  "shrink-0 tabular-nums",
                                                  dark ? "text-gray-500" : "text-slate-400",
                                                )}
                                              >
                                                {formatMetres(p.distance_m)}
                                              </span>
                                            </li>
                                          ))}
                                        </ul>
                                        {extra > 0 && onViewNearbyList && (
                                          <button
                                            type="button"
                                            onClick={onViewNearbyList}
                                            className={clsx(
                                              "mt-1 text-[10px] font-semibold",
                                              dark ? "text-sky-400 hover:text-sky-300" : "text-sky-700 hover:text-sky-800",
                                            )}
                                          >
                                            +{extra} more — view list
                                          </button>
                                        )}
                                      </div>
                                    );
                                  })}
                                  {hasMore && onViewNearbyList && (
                                    <button
                                      type="button"
                                      onClick={onViewNearbyList}
                                      className={clsx(
                                        "w-full rounded-lg border px-3 py-2 text-xs font-semibold",
                                        dark
                                          ? "border-gray-700 bg-gray-950/60 text-sky-300 hover:bg-gray-900"
                                          : "border-slate-200 bg-slate-50 text-sky-800 hover:bg-sky-50",
                                      )}
                                    >
                                      View all schools, hospitals, markets & banks
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {d === "market" && showMarketListings && (() => {
                          const evidence = r.evidence ?? {};
                          const listings = parseMarketListings(evidence);
                          const listingKind = evidence.listing_kind === "rent" ? "rent" : "sale";
                          return (
                            <div className={clsx("mt-3 border-t pt-2.5", dark ? "border-gray-800" : "border-slate-100")}>
                              <p
                                className={clsx(
                                  "text-[10px] font-semibold uppercase tracking-widest",
                                  dark ? "text-gray-500" : "text-slate-400",
                                )}
                              >
                                {listingKind === "rent"
                                  ? "Homes & apartments for rent"
                                  : "Homes & apartments for sale"}
                              </p>
                              {listings.length === 0 ? (
                                <p className={clsx("mt-1.5 text-[11px]", dark ? "text-gray-500" : "text-slate-400")}>
                                  No source listings are available for this location yet.
                                </p>
                              ) : (
                                <ul className="mt-2 space-y-2">
                                  {listings.map((listing, index) => (
                                    <li
                                      key={listing.id ?? `${listing.title}-${index}`}
                                      className={clsx(
                                        "rounded-lg border p-2.5",
                                        dark ? "border-gray-800 bg-gray-950/40" : "border-slate-200 bg-slate-50",
                                      )}
                                    >
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                          <p className="line-clamp-2 text-[11px] font-semibold leading-snug">{listing.title}</p>
                                          <p className={clsx("mt-0.5 text-[10px]", dark ? "text-gray-500" : "text-slate-500")}>
                                            {[listing.area, listing.address && listing.address !== listing.area ? listing.address : null]
                                              .filter(Boolean)
                                              .join(" · ")}
                                          </p>
                                        </div>
                                        <p className={clsx("shrink-0 text-right text-[11px] font-semibold tabular-nums", dark ? "text-teal-300" : "text-teal-800")}>
                                          {formatMarketPrice(listing.price, listing.unit)}
                                        </p>
                                      </div>
                                      <div className={clsx("mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px]", dark ? "text-gray-500" : "text-slate-500")}>
                                        {listing.bedrooms !== undefined && <span>{listing.bedrooms} bed</span>}
                                        {listing.property_type && <span>{listing.property_type}</span>}
                                        {listing.observed_at && <span>Observed {listing.observed_at}</span>}
                                        {listing.source_url && (
                                          <a
                                            href={listing.source_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={clsx("font-semibold", dark ? "text-sky-400 hover:text-sky-300" : "text-sky-700 hover:text-sky-800")}
                                          >
                                            View source
                                          </a>
                                        )}
                                      </div>
                                    </li>
                                  ))}
                                </ul>
                              )}
                              <p className={clsx("mt-2 text-[10px] leading-relaxed", dark ? "text-amber-300/80" : "text-amber-800")}>
                                Asking-price snapshot. Confirm current availability, price, and terms with the listing source.
                              </p>
                            </div>
                          );
                        })()}

                        {r.confidence && r.status !== "pending" && (
                          <p className={clsx("mt-2 text-[10px] uppercase tracking-wide", dark ? "text-gray-500" : "text-slate-400")}>
                            Confidence · {r.confidence}
                          </p>
                        )}
                      </div>
                    )}
                  </section>
                );
              })}
            </div>

            {Object.keys(card.layer_versions).length > 0 && (
              <footer
                className={clsx(
                  "border-t pt-3 text-[10px]",
                  dark ? "border-gray-800 text-gray-500" : "border-slate-200 text-slate-400",
                )}
              >
                Layer versions:{" "}
                {Object.entries(card.layer_versions)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </footer>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
