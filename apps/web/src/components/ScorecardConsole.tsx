import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { DOMAIN_ORDER, type DomainResult, type Scorecard } from "../api";
import { getPersona, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconCopy, IconCube3D, IconEdit, IconMore, IconPin, IconX } from "./Icons";
import { ScoreRing } from "./ScoreRing";

const DOMAIN_LABELS: Record<(typeof DOMAIN_ORDER)[number], string> = {
  flood: "Flood hazard",
  security: "Security",
  amenities: "Amenities",
  accessibility: "Accessibility",
  tenure: "Tenure",
  market: "Market",
  livability: "Habitability",
  feasibility: "Feasibility",
};

const DOMAIN_KICKERS: Record<(typeof DOMAIN_ORDER)[number], string> = {
  flood: "Risk · GGIS Flood Watch",
  security: "Safety · local context",
  amenities: "Services · nearest POIs",
  accessibility: "Connectivity · roads & destinations",
  tenure: "Planning · overlays",
  market: "Prices · samples",
  livability: "Environment · comfort",
  feasibility: "Buildability · 1 km site",
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
  hazard_index: "PropInsight hazard index",
  susceptibility_class: "Susceptibility class",
  zones_inside: "Zones containing this point",
  zones_nearby: "Nearby flood zones",
  assessment_radius_km: "Zone search radius",
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
  data_source: "Incident source",
  nearby_count: "Police locations in radius",
  coverage_radius_m: "Coverage radius",
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

function floodHazardColor(result: DomainResult): string {
  if (result.status === "pending") return "#94a3b8";
  const rating = (result.rating ?? String(result.evidence?.risk_class ?? "")).toLowerCase();
  if (rating.includes("very high") || rating.includes("high")) return "#dc2626";
  if (rating.includes("moderate")) return "#ca8a04";
  if (rating.includes("low")) return "#0d9488";
  if (result.score === null) return "#94a3b8";
  if (result.score >= 60) return "#dc2626";
  if (result.score >= 40) return "#ca8a04";
  return "#0d9488";
}

function floodRiskBadge(
  result: DomainResult,
  dark: boolean,
): { label: string; classes: string } {
  if (result.status === "pending") return qualityBadge(result.score, result.status, dark);
  const label = result.rating ?? "Risk unavailable";
  const color = floodHazardColor(result);
  if (color === "#dc2626") {
    return {
      label,
      classes: dark
        ? "border-red-800/60 bg-red-950/40 text-red-300"
        : "border-red-200 bg-red-50 text-red-700",
    };
  }
  if (color === "#ca8a04") {
    return {
      label,
      classes: dark
        ? "border-amber-700/60 bg-amber-950/40 text-amber-300"
        : "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  if (color === "#0d9488") {
    return {
      label,
      classes: dark
        ? "border-teal-700/60 bg-teal-950/50 text-teal-300"
        : "border-teal-200 bg-teal-50 text-teal-800",
    };
  }
  return {
    label,
    classes: dark
      ? "border-gray-700 bg-gray-900 text-gray-400"
      : "border-slate-200 bg-slate-100 text-slate-600",
  };
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
  if ((key === "zones_inside" || key === "zones_nearby") && Array.isArray(value)) {
    if (value.length === 0) {
      return key === "zones_inside"
        ? "None identified by GGIS"
        : "None identified within the GGIS search radius";
    }
    return value
      .slice(0, 5)
      .map((zone) => {
        if (!zone || typeof zone !== "object") return null;
        const item = zone as Record<string, unknown>;
        return [
          typeof item.name === "string" ? item.name : "Flood zone",
          typeof item.risk_tier === "string" ? item.risk_tier : null,
          typeof item.risk_score === "number"
            ? `${Math.round(item.risk_score * 100)} / 100 zone score`
            : null,
          typeof item.distance_km === "number" ? `${item.distance_km.toFixed(1)} km away` : null,
        ].filter(Boolean).join(" · ");
      })
      .filter((item): item is string => Boolean(item))
      .join("; ");
  }
  if (key === "assessment_radius_km" && typeof value === "number") return `${value} km`;
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
  if (domain === "amenities") {
    if (key === "coverage_radius_m") return "Coverage radius";
    return AMENITY_LABELS[key] ?? key.replace(/_/g, " ");
  }
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
          ? ["risk_class", "hazard_index", "susceptibility_class", "zones_inside", "zones_nearby", "assessment_radius_km", "elevation_m", "dist_to_drainage_m", "flow_accumulation_pct", "historical_inundation_events", "last_event", "data_currency", "model_version"]
          : domain === "feasibility"
            ? Object.keys(FEASIBILITY_LABELS)
            : domain === "market"
              ? Object.keys(MARKET_LABELS)
            : Object.keys(evidence);

  const keys = preferred.filter((k) => k in evidence);
  for (const k of Object.keys(evidence)) {
    if (
      !keys.includes(k) &&
      !["history_events", "nearby", "nearby_counts", "listings", "listing_kind", "data_mode", "hazard_index_eligible"].includes(k)
    ) keys.push(k);
  }

  return keys.map((key) => ({
    key,
    label: labelFor(domain, key),
    value: formatEvidenceValue(key, evidence[key]),
  }));
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function metricValue(value: unknown, suffix = ""): string {
  return typeof value === "number" ? `${value.toLocaleString("en-NG", { maximumFractionDigits: 1 })}${suffix}` : "—";
}

function DetailGroup({
  title,
  description,
  rows,
  dark,
}: {
  title: string;
  description: string;
  rows: Array<[string, string]>;
  dark: boolean;
}) {
  return (
    <section className={clsx("bento-card rounded-2xl border p-3", dark ? "border-gray-700 bg-gray-950/60" : "border-slate-200 bg-slate-50") }>
      <p className={clsx("text-[10px] font-semibold uppercase tracking-widest", dark ? "text-sky-300" : "text-sky-800")}>{title}</p>
      <p className={clsx("mt-1 text-[10px] leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>{description}</p>
      <dl className="mt-2 space-y-0">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className={clsx(
              "flex items-start justify-between gap-3 border-b py-1.5 last:border-0",
              dark ? "border-gray-800/80" : "border-slate-100",
            )}
          >
            <dt className={clsx("min-w-0 text-[10px] font-semibold uppercase tracking-widest", dark ? "text-gray-500" : "text-slate-400")}>{label}</dt>
            <dd className={clsx("max-w-[58%] text-right text-[11px] font-medium tabular-nums", dark ? "text-white" : "text-slate-950")}>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function HabitabilityDetails({ result, dark }: { result: DomainResult; dark: boolean }) {
  const green = asRecord(result.evidence.green_cover);
  const heat = asRecord(result.evidence.surface_temperature);
  const pressure = asRecord(result.evidence.environmental_pressure);
  if (!Object.keys(green).length || !Object.keys(heat).length) {
    return <p className={clsx("text-[11px]", dark ? "text-gray-500" : "text-slate-500")}>Environmental metrics are unavailable until both land-cover and surface-heat coverage is published for this site.</p>;
  }
  return (
    <div className="grid gap-2">
      <DetailGroup
        title="Environmental comfort"
        description="A fixed 1 km neighbourhood view. Surface temperature is satellite-observed ground temperature, not air temperature."
        dark={dark}
        rows={[
          ["Overall rating", result.rating ?? "Unavailable"],
          ["Green cover", metricValue(green.share_pct, "%")],
          ["Surface heat", `${metricValue(heat.value, " °C")} · warmer than ${metricValue(heat.fct_percentile, "% of FCT")}`],
          ["Built-up or bare land", metricValue(pressure.built_bare_share_pct, "%")],
          ["Context", metricValue(result.evidence.context_radius_m, " m")],
          ["Data period", String(result.evidence.data_period ?? "—")],
        ]}
      />
    </div>
  );
}

function FeasibilityDetails({ result, dark }: { result: DomainResult; dark: boolean }) {
  const [section, setSection] = useState<"terrain" | "drainage" | "servicing">("terrain");
  const terrain = asRecord(result.evidence.terrain);
  if (!Object.keys(terrain).length) {
    return <p className={clsx("text-[11px]", dark ? "text-gray-500" : "text-slate-500")}>A detailed one-kilometre terrain profile is not available at this point yet.</p>;
  }
  const drainage = asRecord(result.evidence.drainage);
  const modelled = asRecord(drainage.modelled);
  const watercourse = asRecord(drainage.mapped_watercourse);
  const servicing = asRecord(result.evidence.servicing);
  const water = asRecord(servicing.water);
  const power = asRecord(servicing.power);
  const road = asRecord(servicing.nearest_road);
  const sectionButton = (
    key: "terrain" | "drainage" | "servicing",
    label: string,
    summary: string,
  ) => (
    <button
      type="button"
      onClick={() => setSection(key)}
      aria-pressed={section === key}
      className={clsx(
        "min-w-0 bento-card rounded-xl border px-2 py-2 text-left transition",
        section === key
          ? dark
            ? "border-sky-500 bg-sky-950/70 text-white"
            : "border-sky-500 bg-sky-50 text-sky-950"
          : dark
            ? "border-gray-700 bg-gray-950/40 text-gray-300 hover:border-gray-500"
            : "border-slate-200 bg-white text-slate-700 hover:border-slate-400",
      )}
    >
      <span className="block truncate text-[10px] font-bold uppercase tracking-wide">{label}</span>
      <span className={clsx("mt-0.5 block truncate text-[9px]", section === key ? "opacity-90" : "opacity-75")}>{summary}</span>
    </button>
  );
  return (
    <div className="grid gap-2">
      <div className="grid grid-cols-3 gap-1.5" aria-label="Feasibility detail sections">
        {sectionButton("terrain", "Terrain", `${metricValue(terrain.buildable_share_pct, "%")} gentle`)}
        {sectionButton(
          "drainage",
          "Drainage",
          modelled.distance_m != null ? `${formatMetres(modelled.distance_m as number)} path` : "No path mapped",
        )}
        {sectionButton(
          "servicing",
          "Servicing",
          road.distance_m != null ? `${formatMetres(road.distance_m as number)} to road` : "Check services",
        )}
      </div>
      {section === "terrain" && (
        <DetailGroup
          title="Terrain"
          description="Shows the selected point and variation across the surrounding 1 km, which can affect earthworks and foundation cost."
          dark={dark}
          rows={[
            ["Point elevation", metricValue(terrain.point_elevation_m, " m")],
            ["Elevation range", `${metricValue(terrain.elevation_min_m, " m")} – ${metricValue(terrain.elevation_max_m, " m")}`],
            ["Relief", metricValue(terrain.elevation_relief_m, " m")],
            ["Point slope", metricValue(terrain.point_slope_deg, "°")],
            ["Mean / P90 slope", `${metricValue(terrain.slope_mean_deg, "°")} / ${metricValue(terrain.slope_p90_deg, "°")}`],
            ["Terrain at or below 5°", metricValue(terrain.buildable_share_pct, "%")],
          ]}
        />
      )}
      {section === "drainage" && (
        <DetailGroup
          title="Drainage and wetness"
          description="Terrain-derived drainage indicates likely flow paths only; a site survey and drainage design are still required."
          dark={dark}
          rows={[
            ["Median / P90 wetness", `${metricValue(terrain.twi_median)} / ${metricValue(terrain.twi_p90)}`],
            ["High-wetness terrain", metricValue(terrain.wet_share_pct, "%")],
            ["Modelled drainage path", modelled.distance_m != null ? formatMetres(modelled.distance_m as number) : "Not mapped"],
            ["Contributing catchment", metricValue(modelled.contributing_area_km2, " km²")],
            ["Mapped watercourse", watercourse.distance_m != null ? `${String(watercourse.name ?? "Watercourse")} · ${formatMetres(watercourse.distance_m as number)}` : "Not mapped"],
          ]}
        />
      )}
      {section === "servicing" && (
        <DetailGroup
          title="Servicing"
          description="Distances are service-access proxies, not confirmation of capacity, connection rights or construction cost."
          dark={dark}
          rows={[
            ["Water facility", water.distance_m != null ? `${String(water.name ?? "Water") } · ${formatMetres(water.distance_m as number)}` : "Not mapped"],
            ["Power facility", power.distance_m != null ? `${String(power.name ?? "Power") } · ${formatMetres(power.distance_m as number)}` : "Not mapped"],
            ["Mapped road", road.distance_m != null ? formatMetres(road.distance_m as number) : "Not mapped"],
            ["Inputs available", metricValue(result.evidence.available_weight_pct, "%")],
          ]}
        />
      )}
    </div>
  );
}

function ProfessionalDecisionSummary({ card, dark }: { card: Scorecard; dark: boolean }) {
  const terrain = asRecord(card.domains.feasibility?.evidence.terrain);
  const outlook = card.development_outlook;
  const signals = [
    terrain.buildable_share_pct != null
      ? `${metricValue(terrain.buildable_share_pct, "%")} of sampled terrain is at or below 5° within 1 km.`
      : null,
    card.domains.flood?.rating ? `${card.domains.flood.rating}; confirm drainage during due diligence.` : null,
    card.location.land_use ? `${card.location.land_use.label} is the current ${card.location.land_use.designation === "official_masterplan" ? "official planning" : "mapped reference"} context.` : null,
    outlook?.migration_pressure ? `${outlook.migration_pressure.band} likely in-migration pressure to 2030.` : null,
    outlook?.projects?.total_count ? `${outlook.projects.total_count} verified public project record${outlook.projects.total_count === 1 ? "" : "s"} in the radius or broader administrative area.` : null,
  ].filter((item): item is string => Boolean(item));
  if (!signals.length) return null;
  return (
    <div className={clsx("mt-2 border-t pt-2", dark ? "border-gray-800" : "border-slate-200") }>
      <p className="text-[9px] font-semibold uppercase tracking-widest">Decision checks</p>
      <ul className="mt-1 space-y-1 text-[10px] leading-relaxed">
        {signals.map((signal) => <li key={signal}>• {signal}</li>)}
      </ul>
    </div>
  );
}

function DevelopmentOutlookCard({
  card,
  dark,
  open,
  onToggle,
}: {
  card: Scorecard;
  dark: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const outlook = card.development_outlook;
  if (!outlook) return null;
  const projects = [...(outlook.projects.nearby ?? []), ...(outlook.projects.broader_area ?? [])];
  const population = outlook.population;
  const settlement = outlook.settlement;
  const pressure = outlook.migration_pressure;
  return (
    <section className={clsx("bento-card overflow-hidden rounded-2xl border", dark ? "border-amber-900/60" : "border-amber-200") }>
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left">
        <div>
          <p className={clsx("text-[10px] font-semibold uppercase tracking-[0.14em]", dark ? "text-amber-300" : "text-amber-700")}>Professional context · {outlook.radius_m / 1000} km</p>
          <h3 className="font-display text-base font-semibold">Development outlook</h3>
          <p className={clsx("mt-1 text-[10px]", dark ? "text-gray-400" : "text-slate-500")}>Growth, settlement and verified public-project signals; not part of the fit score.</p>
        </div>
        <span className="text-[10px] font-semibold uppercase">{open ? "Hide" : "Details"}</span>
      </button>
      {open && (
        <div className={clsx("space-y-2 border-t p-3", dark ? "border-amber-900/50" : "border-amber-100") }>
          <DetailGroup
            title="Population and settlement"
            description="Modelled estimates and projections within the selected radius. They describe demand pressure, not guaranteed property demand."
            dark={dark}
            rows={[
              ["Population 2025", metricValue(population?.estimate_2025)],
              ["Population 2030", metricValue(population?.projection_2030)],
              ["Projected change", population?.change_pct != null ? `${metricValue(population.change)} · ${metricValue(population.change_pct, "%")}` : "—"],
              ["Annual growth", metricValue(population?.cagr_pct, "%")],
              ["Current built share", metricValue(settlement?.built_share_current_pct, "%")],
              ["Built-area change", metricValue(settlement?.built_change_pct, "%")],
            ]}
          />
          <DetailGroup
            title="Likely in-migration pressure"
            description={pressure?.advisory ?? "The migration-pressure signal is unavailable until both population and settlement layers publish."}
            dark={dark}
            rows={[
              ["Pressure band", pressure?.band ?? "Unavailable"],
              ["Relative index", pressure ? metricValue(pressure.index, " / 100") : "—"],
              ["Confidence", pressure?.confidence ?? "Low"],
            ]}
          />
    <section className={clsx("bento-card rounded-2xl border p-2.5", dark ? "border-gray-800 bg-gray-950/40" : "border-slate-100 bg-slate-50") }>
          <p className={clsx("text-[10px] font-semibold uppercase tracking-widest", dark ? "text-amber-300" : "text-amber-700")}>Verified public projects · {outlook.projects.total_count ?? outlook.projects.returned_count ?? 0}</p>
            <p className={clsx("mt-1 text-[10px] leading-relaxed", dark ? "text-gray-500" : "text-slate-500")}>{outlook.projects.advisory}</p>
            {projects.length ? (
              <ul className="mt-2 space-y-2">
                {projects.map((project) => (
                  <li key={project.official_id} className={clsx("border-t pt-2 first:border-0 first:pt-0", dark ? "border-gray-800" : "border-slate-200") }>
                    <a href={project.source_url} target="_blank" rel="noreferrer" className={clsx("text-[11px] font-semibold hover:underline", dark ? "text-amber-300" : "text-amber-800")}>{project.name}</a>
                    <p className="text-[10px] capitalize">{project.lifecycle_stage} · {project.sector}{project.distance_m != null ? ` · ${formatMetres(project.distance_m)}` : " · broader area"}</p>
                    <p className={clsx("text-[9px]", dark ? "text-gray-500" : "text-slate-500")}>{project.authority} · source {project.source_published_at} · {project.location_precision}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="mt-2 text-[11px]">No current verified project records are available for this radius.</p>}
          </section>
        </div>
      )}
    </section>
  );
}

type Props = {
  theme: Theme;
  card: Scorecard | null;
  loading: boolean;
  error: string | null;
  placeLabel?: string | null;
  coordinates?: { lon: number; lat: number } | null;
  persona?: PersonaKey;
  onClose?: () => void;
  onReset?: () => void;
  onViewNearbyList?: (category?: string) => void;
  onEditAnalysis?: () => void;
  onOpenProfessional3D?: () => void;
};

function domainLabel(key: string): string {
  return DOMAIN_LABELS[key as (typeof DOMAIN_ORDER)[number]] ?? key.replace(/_/g, " ");
}

function domainKicker(key: string): string {
  return DOMAIN_KICKERS[key as (typeof DOMAIN_ORDER)[number]] ?? "Location intelligence";
}

function fitRating(score: number | null | undefined): { label: string; color: string } {
  if (score == null) return { label: "Unavailable", color: "#94a3b8" };
  if (score >= 70) return { label: "Strong", color: "#10b981" };
  if (score >= 40) return { label: "Moderate", color: "#d97706" };
  return { label: "Weak", color: "#ef4444" };
}

async function copyText(text: string): Promise<boolean> {
  const value = text.trim();
  if (!value) return false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Fall through to execCommand fallback.
  }
  try {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}

type BentoMenuItem = {
  id: string;
  label: string;
  onSelect: () => void;
};

function BentoCardMenu({
  dark,
  items,
  ariaLabel = "Card options",
}: {
  dark: boolean;
  items: BentoMenuItem[];
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const updatePosition = () => {
    const button = buttonRef.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const left = Math.min(
      Math.max(8, rect.right - menuWidth),
      window.innerWidth - menuWidth - 8,
    );
    setCoords({ top: rect.bottom + 4, left });
  };

  useLayoutEffect(() => {
    if (!open) return undefined;
    updatePosition();
    const onReposition = () => updatePosition();
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!items.length) return null;

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-haspopup="menu"
        title={ariaLabel}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
        className={clsx(
          "inline-flex h-7 w-7 items-center justify-center rounded-full border transition",
          dark
            ? "border-gray-600 text-gray-400 hover:border-gray-500 hover:bg-gray-800 hover:text-white"
            : "border-slate-300 text-slate-400 hover:border-slate-400 hover:bg-slate-50 hover:text-slate-700",
        )}
      >
        <IconMore size={14} />
      </button>
      {open &&
        coords &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{ top: coords.top, left: coords.left }}
            className={clsx(
              "fixed z-[80] min-w-[10.5rem] overflow-hidden rounded-xl border py-1 shadow-xl",
              dark ? "border-gray-700 bg-gray-900" : "border-slate-200 bg-white",
            )}
          >
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                onClick={(event) => {
                  event.stopPropagation();
                  setOpen(false);
                  item.onSelect();
                }}
                className={clsx(
                  "block w-full px-3 py-2 text-left text-[11px] font-semibold transition",
                  dark
                    ? "text-gray-200 hover:bg-gray-800"
                    : "text-slate-700 hover:bg-slate-50",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}

export function ScorecardConsole({
  theme,
  card,
  loading,
  error,
  placeLabel,
  coordinates,
  persona = "home_buyer",
  onClose,
  onReset,
  onViewNearbyList,
  onEditAnalysis,
  onOpenProfessional3D,
}: Props) {
  const dark = theme === "dark";
  const personaDef = getPersona(persona);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copiedTimerRef = useRef<number | null>(null);

  const toggle = (id: string) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  const toggleDomain = (id: string) => {
    setExpanded((prev) => {
      const opening = !prev[id];
      const next: Record<string, boolean> = {
        fit_overview: prev.fit_overview ?? false,
        summary_overview: prev.summary_overview ?? false,
        development_outlook: prev.development_outlook ?? false,
      };
      if (opening) next[id] = true;
      return next;
    });
  };

  const flashCopied = (key: string) => {
    setCopiedKey(key);
    if (copiedTimerRef.current != null) window.clearTimeout(copiedTimerRef.current);
    copiedTimerRef.current = window.setTimeout(() => {
      setCopiedKey((current) => (current === key ? null : current));
      copiedTimerRef.current = null;
    }, 1500);
  };

  const copyWithFeedback = async (key: string, text: string) => {
    const ok = await copyText(text);
    if (ok) flashCopied(key);
  };

  useEffect(() => () => {
    if (copiedTimerRef.current != null) window.clearTimeout(copiedTimerRef.current);
  }, []);

  const orderedDomains =
    card?.domain_priority && card.domain_priority.length > 0
      ? [...card.domain_priority]
      : card
        ? Object.keys(card.domains)
        : [...DOMAIN_ORDER];

  const topDomains = new Set(orderedDomains.slice(0, 3));
  const personaLabel = card?.persona?.label ?? personaDef.label;
  const reportPersona = card?.persona?.key ?? persona;
  const isConsumerReport = ["home_buyer", "tenant"].includes(reportPersona);
  const showPlanningContext = ["investor", "developer"].includes(reportPersona);
  const showMarketListings = ["home_buyer", "tenant"].includes(
    reportPersona,
  );
  const overviewHighlights = (card?.highlights ?? []).slice(0, 3);
  const suitabilityHighlights = overviewHighlights.filter(
    (highlight) => highlight.tone === "positive",
  );
  const cautionHighlights = overviewHighlights.filter(
    (highlight) => highlight.tone !== "positive",
  );
  const fit = fitRating(card?.fit_score);
  const coordinateText = coordinates
    ? `${coordinates.lat.toFixed(5)}, ${coordinates.lon.toFixed(5)}`
    : (placeLabel ?? "");
  const copyLocation = () => {
    void copyWithFeedback("coordinates", coordinateText);
  };
  const domainEntries = card
    ? orderedDomains
        .map((d) => ({ d, r: card.domains[d] }))
        .filter((entry): entry is { d: string; r: DomainResult } => Boolean(entry.r))
    : [];
  const openDomainId = domainEntries.find(({ d }) => expanded[d])?.d ?? null;
  const closedDomainEntries = domainEntries.filter(({ d }) => d !== openDomainId);

  return (
    <aside
      className={clsx(
        "flex h-full w-full flex-col border-r",
        dark ? "border-gray-800 bg-gray-950/80 text-gray-100 backdrop-blur-2xl" : "border-slate-200 bg-slate-50/75 text-slate-900 backdrop-blur-2xl",
      )}
    >
      <div
        className={clsx(
          "bento-card m-2 mb-0 flex items-start justify-between gap-2 rounded-xl border p-3",
          dark ? "border-gray-800 bg-gray-900" : "border-slate-200 bg-white",
        )}
      >
        <div className="min-w-0 flex-1">
          <p className="app-kicker">Location report</p>
          <h2 className="font-display text-lg font-semibold tracking-tight">Scorecard</h2>
          <p className={clsx("mt-0.5 line-clamp-2 text-[10px] leading-snug", dark ? "text-gray-400" : "text-slate-500")}>
            {card?.persona?.blurb ?? personaDef.blurb}
          </p>
          {card && (
            <>
              <div className={clsx("mt-2 border-t pt-2", dark ? "border-gray-800" : "border-slate-200")}>
                <button
                  type="button"
                  onClick={copyLocation}
                  disabled={!coordinateText}
                  className="inline-flex max-w-full items-center gap-2 text-left"
                  title="Copy coordinates"
                >
                  <IconPin size={14} className="shrink-0 text-amber-600" />
                  <span className="truncate text-sm font-bold tabular-nums text-amber-600">
                    {coordinateText || "Coordinates unavailable"}
                  </span>
                  <IconCopy size={13} className={dark ? "text-gray-500" : "text-slate-400"} />
                  {copiedKey === "coordinates" && (
                    <span className={clsx("shrink-0 text-[10px] font-semibold uppercase tracking-wide", dark ? "text-teal-300" : "text-teal-700")}>
                      Copied
                    </span>
                  )}
                </button>
                {(card.location.ward || card.location.area_council) && (
                  <p className={clsx("mt-1 truncate text-xs", dark ? "text-gray-400" : "text-slate-500")}>
                    {[card.location.ward && `${card.location.ward} ward`, card.location.area_council].filter(Boolean).join(" · ")}
                  </p>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {onReset && (
                  <button
                    type="button"
                    onClick={onReset}
                    className={clsx(
                      "inline-flex h-8 items-center rounded-lg px-2.5 text-[11px] font-semibold",
                      dark ? "bg-gray-800 text-gray-200" : "bg-slate-100 text-slate-700",
                    )}
                  >
                    Reset
                  </button>
                )}
                {onEditAnalysis && (
                  <button
                    type="button"
                    onClick={onEditAnalysis}
                    className={clsx(
                      "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-semibold",
                      dark
                        ? "border-gray-700 bg-gray-800 text-gray-100 hover:border-gray-500"
                        : "border-slate-200 bg-white text-slate-800 hover:border-slate-300",
                    )}
                  >
                    <IconEdit size={13} />
                    Adjust radius
                  </button>
                )}
                {onOpenProfessional3D && (
                  <button
                    type="button"
                    onClick={onOpenProfessional3D}
                    className={clsx(
                      "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-semibold",
                      dark
                        ? "border-gray-700 bg-gray-800 text-gray-100 hover:border-gray-500"
                        : "border-slate-200 bg-white text-slate-800 hover:border-slate-300",
                    )}
                  >
                    <IconCube3D size={13} />
                    3D site view
                  </button>
                )}
              </div>
            </>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close location report"
              title="Close report"
              className={clsx(
                "inline-flex h-9 w-9 items-center justify-center rounded-full border transition",
                dark
                  ? "border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white"
                  : "border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900",
              )}
            >
              <IconX size={16} />
            </button>
          )}
        </div>
      </div>

      <div className="scorecard-scroll flex-1 overflow-y-auto overflow-x-hidden px-2.5 py-2">
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
          <div className="grid w-full grid-cols-2 gap-2">
            <section className={clsx("bento-card relative col-span-2 w-full overflow-visible rounded-2xl border", dark ? "border-gray-800 bg-gray-900" : "border-slate-200 bg-white")}>
              <div className="absolute right-2 top-2 z-10">
                <BentoCardMenu
                  dark={dark}
                  ariaLabel="Fit card options"
                  items={[
                    {
                      id: "view",
                      label: (expanded.fit_overview ?? false) ? "Hide Details" : "View Details",
                      onSelect: () => toggle("fit_overview"),
                    },
                    {
                      id: "copy-fit",
                      label: copiedKey === "fit" ? "Copied" : "Copy fit score",
                      onSelect: () => {
                        const scoreText = card.fit_score != null ? `${Math.round(card.fit_score)}/100` : "—";
                        void copyWithFeedback(
                          "fit",
                          `${scoreText} · ${fit.label} · Fit for ${personaLabel}`,
                        );
                      },
                    },
                    ...(onEditAnalysis
                      ? [{ id: "radius", label: "Adjust radius", onSelect: onEditAnalysis }]
                      : []),
                    ...(onOpenProfessional3D
                      ? [{ id: "3d", label: "Open 3D site view", onSelect: onOpenProfessional3D }]
                      : []),
                  ]}
                />
              </div>
              <button
                type="button"
                onClick={() => toggle("fit_overview")}
                aria-expanded={expanded.fit_overview ?? false}
                className="relative flex w-full items-center gap-3 p-3 pr-11 text-left"
              >
                <ScoreRing score={card.fit_score ?? null} size="md" color={fit.color} label={`Fit for ${personaLabel}`} />
                <div className="min-w-0 flex-1">
                  <p className={clsx("text-[11px] font-semibold uppercase tracking-wide", dark ? "text-gray-400" : "text-slate-500")}>Fit for {personaLabel}</p>
                  <p className="font-display text-2xl font-bold tabular-nums">{card.fit_score != null ? Math.round(card.fit_score) : "—"} / 100</p>
                  <span className={clsx(
                    "mt-2 inline-flex rounded-lg px-3 py-1 text-[11px] font-bold uppercase",
                    fit.label === "Strong" ? "bg-emerald-100 text-emerald-700" : fit.label === "Moderate" ? "bg-amber-100 text-amber-700" : fit.label === "Weak" ? "bg-red-100 text-red-700" : "bg-slate-200 text-slate-600",
                  )}>{fit.label}</span>
                </div>
              </button>
              {(expanded.fit_overview ?? false) && (
                <div className={clsx("border-t px-5 py-4 text-xs leading-relaxed", dark ? "border-gray-800 text-gray-400" : "border-slate-100 text-slate-500")}>
                  The fit score combines the report domains using the priorities for {personaLabel}. Open any domain card below to review its supporting evidence.
                </div>
              )}
            </section>

            {card.summary && (
              <section className={clsx("bento-card relative col-span-2 w-full overflow-visible rounded-2xl border", dark ? "border-gray-800 bg-gray-900" : "border-slate-200 bg-white")}>
                <div className="absolute right-2 top-2 z-10">
                  <BentoCardMenu
                    dark={dark}
                    ariaLabel="Summary card options"
                    items={[
                      {
                        id: "view",
                        label: (expanded.summary_overview ?? false) ? "Hide Details" : "View Details",
                        onSelect: () => toggle("summary_overview"),
                      },
                      {
                        id: "copy-summary",
                        label: copiedKey === "summary" ? "Copied" : "Copy summary",
                        onSelect: () => {
                          void copyWithFeedback(
                            "summary",
                            card.summary!.replace(/\s*—\s*/g, " - ").replace(/\s*--\s*/g, " - "),
                          );
                        },
                      },
                      ...(overviewHighlights.length > 0
                        ? [{
                            id: "copy-takeaways",
                            label: copiedKey === "takeaways" ? "Copied" : "Copy takeaways",
                            onSelect: () => {
                              const text = overviewHighlights
                                .map((highlight) => `${highlight.title}: ${highlight.text}`)
                                .join("\n");
                              void copyWithFeedback("takeaways", text);
                            },
                          }]
                        : []),
                    ]}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => toggle("summary_overview")}
                  aria-expanded={expanded.summary_overview ?? false}
                  className="relative w-full p-3 pr-11 text-left"
                >
                  <p className={clsx("pr-1 text-[11px] font-semibold uppercase tracking-wide", dark ? "text-gray-400" : "text-slate-500")}>What this means for you</p>
                  <p className={clsx("mt-2 text-sm font-normal leading-snug", dark ? "text-gray-300" : "text-slate-600")}>
                    {card.summary.replace(/\s*—\s*/g, " - ").replace(/\s*--\s*/g, " - ")}
                  </p>
                  {(expanded.summary_overview ?? false) && overviewHighlights.length > 0 && (
                    <div className="mt-4 space-y-3">
                      {overviewHighlights.map((highlight) => (
                        <div key={highlight.domain} className="flex gap-3 text-xs leading-relaxed">
                          <span className={clsx("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", highlight.tone === "positive" ? "bg-emerald-500" : highlight.tone === "caution" ? "bg-amber-500" : "bg-sky-500")} />
                          <p><span className="font-bold">{highlight.title}:</span> <span className={dark ? "text-gray-400" : "text-slate-500"}>{highlight.text}</span></p>
                        </div>
                      ))}
                    </div>
                  )}
                </button>
              </section>
            )}

            <div
              className={clsx(
                "col-span-2 hidden rounded-lg border px-3 py-2 text-[11px]",
                dark ? "border-gray-800 bg-gray-950/60 text-gray-400" : "border-slate-200 bg-slate-50 text-slate-500",
              )}
            >
              {placeLabel && (
                <p className={clsx("mb-1 truncate text-xs font-semibold", dark ? "text-gray-200" : "text-slate-800")}>
                  {placeLabel}
                </p>
              )}
              {isConsumerReport && card.location.ward && (
                <p className="mb-1 text-[10px]">
                  {card.location.ward} ward
                  {card.location.area_council && ` · ${card.location.area_council}`}
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
                <div
                  className={clsx(
                    "mb-2 rounded-lg border px-3 py-2.5",
                    isConsumerReport
                      ? dark
                        ? "border-teal-800/70 bg-teal-950/30 text-teal-100"
                        : "border-teal-200 bg-teal-50 text-teal-950"
                      : dark
                        ? "border-gray-800 bg-gray-950/50 text-gray-200"
                        : "border-slate-200 bg-white text-slate-700",
                  )}
                >
                  {isConsumerReport && (
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em]">
                      What this means for you
                    </p>
                  )}
                  <p className="text-[12px] font-normal leading-relaxed">
                    {card.summary.replace(/\s*—\s*/g, " - ").replace(/\s*--\s*/g, " - ")}
                  </p>
                  {!isConsumerReport && <ProfessionalDecisionSummary card={card} dark={dark} />}
                  {isConsumerReport && overviewHighlights.length > 0 && (
                    <div
                      className={clsx(
                        "mt-2 space-y-2 border-t pt-2",
                        dark ? "border-teal-800/60" : "border-teal-200",
                      )}
                    >
                      {[
                        {
                          title: "Why it could suit you",
                          highlights: suitabilityHighlights,
                          headingClass: dark ? "text-teal-300" : "text-teal-700",
                          dotClass: "bg-teal-500",
                        },
                        {
                          title: "Why it may not suit you",
                          highlights: cautionHighlights,
                          headingClass: dark ? "text-amber-300" : "text-amber-700",
                          dotClass: "bg-amber-500",
                        },
                      ].map((group) =>
                        group.highlights.length > 0 ? (
                          <section key={group.title}>
                            <p
                              className={clsx(
                                "mb-1 text-[9px] font-semibold uppercase tracking-[0.1em]",
                                group.headingClass,
                              )}
                            >
                              {group.title}
                            </p>
                            <div className="space-y-1.5">
                              {group.highlights.map((highlight) => (
                                <div key={highlight.domain} className="flex gap-2">
                                  <span
                                    className={clsx(
                                      "mt-1 h-2 w-2 shrink-0 rounded-full",
                                      group.dotClass,
                                    )}
                                    aria-hidden
                                  />
                                  <p className="text-[10px] leading-relaxed">
                                    <span className="font-semibold">{highlight.title}:</span>{" "}
                                    {highlight.text}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </section>
                        ) : null,
                      )}
                    </div>
                  )}
                </div>
              )}
              {showPlanningContext && (
                <>
                  <div className="tabular-nums">
                    geohash <span className="font-semibold">{card.location.geohash8}</span>
                    {card.location.district && <> · {card.location.district}</>}
                    {card.location.ward && <> · {card.location.ward} ward</>}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[10px]">
                    <span className="font-semibold uppercase tracking-wide">Planning context</span>
                    <span
                      className={clsx(
                        "rounded-full px-1.5 py-0.5 font-semibold",
                        card.location.planning_status === "official"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : card.location.planning_status === "mapped_reference"
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                            : "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
                      )}
                    >
                      {card.location.planning_status === "official"
                        ? "Official plan"
                        : card.location.planning_status === "mapped_reference"
                          ? "Mapped reference"
                          : card.location.planning_status === "observed_cover_only"
                            ? "Observed cover only"
                            : "Unmapped"}
                    </span>
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
                        {card.location.land_use.designation === "official_masterplan"
                          ? "Official planned land use"
                          : "Mapped land use reference"}
                      </p>
                      <p className="text-xs font-semibold">{card.location.land_use.label}</p>
                      {card.location.land_use.name && (
                        <p className="truncate text-[10px]">{card.location.land_use.name}</p>
                      )}
                      <p className="mt-1 text-[9px] leading-snug">
                        {card.location.land_use.advisory}
                      </p>
                    </div>
                  )}
                  {card.location.land_cover && (
                    <div
                      className={clsx(
                        "mt-2 rounded-md border px-2 py-1.5",
                        dark
                          ? "border-sky-800/70 bg-sky-950/30 text-sky-200"
                          : "border-sky-200 bg-sky-50 text-sky-900",
                      )}
                    >
                      <p className="text-[10px] font-semibold uppercase tracking-wide">
                        Observed land cover
                      </p>
                      <p className="text-xs font-semibold">{card.location.land_cover.label}</p>
                      <p className="text-[9px]">
                        {card.location.land_cover.source} · {card.location.land_cover.resolution_m} m
                      </p>
                      <p className="mt-1 text-[9px] leading-snug">
                        {card.location.land_cover.advisory}
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
                </>
              )}
            </div>

            {!isConsumerReport && (
              <div className="col-span-2 w-full">
                <DevelopmentOutlookCard
                  card={card}
                  dark={dark}
                  open={expanded.development_outlook ?? false}
                  onToggle={() => toggle("development_outlook")}
                />
              </div>
            )}

            {openDomainId && (() => {
              const d = openDomainId;
              const r = card.domains[d]!;
              const isFlood = d === "flood";
              const rows = evidenceRows(d, r.evidence ?? {});
              const bar = isFlood ? floodHazardColor(r) : scoreBarColor(r.score, r.status);
              const highPriority = topDomains.has(d);
              const badge = isFlood
                ? floodRiskBadge(r, dark)
                : qualityBadge(r.score, r.status, dark);
              if (d === "livability" && r.rating) badge.label = r.rating;
              const scoreSnippet = r.score !== null
                ? r.score.toFixed(0)
                : isFlood
                  ? "N/P"
                  : "—";
              const evidenceText = [
                r.note && r.status !== "demo" ? r.note : null,
                ...rows.map((row) => `${row.label}: ${row.value}`),
              ]
                .filter(Boolean)
                .join("\n");
              const domainMenuItems: BentoMenuItem[] = [
                {
                  id: "view",
                  label: "Hide Details",
                  onSelect: () => toggleDomain(d),
                },
                {
                  id: "copy-score",
                  label: copiedKey === `domain-${d}` ? "Copied" : "Copy domain score",
                  onSelect: () => {
                    void copyWithFeedback(
                      `domain-${d}`,
                      `${domainLabel(d)} · ${scoreSnippet} · ${badge.label}`,
                    );
                  },
                },
                {
                  id: "copy-evidence",
                  label: copiedKey === `evidence-${d}` ? "Copied" : "Copy evidence",
                  onSelect: () => {
                    void copyWithFeedback(
                      `evidence-${d}`,
                      evidenceText || `${domainLabel(d)} · no evidence rows yet`,
                    );
                  },
                },
              ];
              if (d === "amenities" && onViewNearbyList) {
                domainMenuItems.push({
                  id: "nearby",
                  label: "View nearby list",
                  onSelect: () => onViewNearbyList(),
                });
              }
              if (d === "feasibility" && onOpenProfessional3D) {
                domainMenuItems.push({
                  id: "3d",
                  label: "Open 3D site view",
                  onSelect: onOpenProfessional3D,
                });
              }

              return (
                <section
                  key={`open-${d}`}
                  className={clsx(
                    "bento-card relative col-span-2 w-full overflow-visible rounded-2xl border",
                    dark ? "border-gray-800 bg-gray-900" : "border-slate-200 bg-white",
                  )}
                >
                  <div className="absolute right-2 top-2 z-10">
                    <BentoCardMenu
                      dark={dark}
                      ariaLabel={`${domainLabel(d)} options`}
                      items={domainMenuItems}
                    />
                  </div>
                  <div className="flex w-full items-start gap-3 p-3 pr-11 text-left">
                    <ScoreRing score={r.score} size="sm" color={bar} label={domainLabel(d)} />
                    <div className="min-w-0 flex-1">
                      <h3 className="font-display text-base font-semibold tracking-tight">
                        {domainLabel(d)}
                      </h3>
                      <p
                        className={clsx(
                          "mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]",
                          dark ? "text-sky-400" : "text-sky-700",
                        )}
                      >
                        {domainKicker(d)}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <span
                          className={clsx(
                            "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                            badge.classes,
                          )}
                        >
                          {badge.label}
                        </span>
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
                        <span className="font-display text-lg font-semibold tabular-nums">
                          {scoreSnippet}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleDomain(d)}
                      className={clsx(
                        "shrink-0 rounded-lg px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
                        dark ? "text-gray-400 hover:bg-gray-800" : "text-slate-500 hover:bg-slate-50",
                      )}
                    >
                      Hide
                    </button>
                  </div>
                  <div className={clsx("border-t px-3 py-3", dark ? "border-gray-800" : "border-slate-100")}>
                    {r.note && r.status !== "demo" && (
                      <p className={clsx("mb-2 text-xs leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
                        {r.note}
                      </p>
                    )}
                    {r.status === "pending" && rows.length === 0 ? (
                      <p className={clsx("text-[11px]", dark ? "text-gray-500" : "text-slate-400")}>
                        No indicators yet - waiting on published data layers.
                      </p>
                    ) : d === "livability" ? (
                      <HabitabilityDetails result={r} dark={dark} />
                    ) : d === "feasibility" ? (
                      <FeasibilityDetails result={r} dark={dark} />
                    ) : (
                      <table className="w-full border-collapse text-left">
                        <tbody>
                          {rows.map((row) => {
                            const rawCount =
                              d === "amenities" &&
                              r.evidence.nearby_counts &&
                              typeof r.evidence.nearby_counts === "object" &&
                              !Array.isArray(r.evidence.nearby_counts)
                                ? (r.evidence.nearby_counts as Record<string, unknown>)[row.key]
                                : undefined;
                            const amenityCount =
                              row.key in AMENITY_LABELS && typeof rawCount === "number"
                                ? rawCount
                                : 0;
                            return (
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
                                <td className="py-1.5 text-right text-[11px] font-medium tabular-nums">
                                  <span className="block">{row.value}</span>
                                  {amenityCount > 0 && onViewNearbyList && (
                                    <button
                                      type="button"
                                      onClick={() => onViewNearbyList(row.key)}
                                      className={clsx(
                                        "mt-1 text-[10px] font-semibold",
                                        dark
                                          ? "text-sky-400 hover:text-sky-300"
                                          : "text-sky-700 hover:text-sky-800",
                                      )}
                                    >
                                      View list · {amenityCount}
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
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
                                    "bento-card rounded-2xl border p-2.5",
                                    dark ? "border-gray-800 bg-gray-950/40" : "border-slate-200 bg-white",
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
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })()}
                    {r.confidence && r.status !== "pending" && (
                      <p className={clsx("mt-2 text-[10px] uppercase tracking-wide", dark ? "text-gray-500" : "text-slate-400")}>
                        Confidence · {r.confidence}
                      </p>
                    )}
                  </div>
                </section>
              );
            })()}

            {closedDomainEntries.map(({ d, r }) => {
              const isFlood = d === "flood";
              const rows = evidenceRows(d, r.evidence ?? {});
              const bar = isFlood ? floodHazardColor(r) : scoreBarColor(r.score, r.status);
              const badge = isFlood
                ? floodRiskBadge(r, dark)
                : qualityBadge(r.score, r.status, dark);
              if (d === "livability" && r.rating) badge.label = r.rating;
              const scoreSnippet = r.score !== null
                ? r.score.toFixed(0)
                : isFlood
                  ? "N/P"
                  : "—";
              const evidenceText = [
                r.note && r.status !== "demo" ? r.note : null,
                ...rows.map((row) => `${row.label}: ${row.value}`),
              ]
                .filter(Boolean)
                .join("\n");
              const domainMenuItems: BentoMenuItem[] = [
                {
                  id: "view",
                  label: "View Details",
                  onSelect: () => toggleDomain(d),
                },
                {
                  id: "copy-score",
                  label: copiedKey === `domain-${d}` ? "Copied" : "Copy domain score",
                  onSelect: () => {
                    void copyWithFeedback(
                      `domain-${d}`,
                      `${domainLabel(d)} · ${scoreSnippet} · ${badge.label}`,
                    );
                  },
                },
                {
                  id: "copy-evidence",
                  label: copiedKey === `evidence-${d}` ? "Copied" : "Copy evidence",
                  onSelect: () => {
                    void copyWithFeedback(
                      `evidence-${d}`,
                      evidenceText || `${domainLabel(d)} · no evidence rows yet`,
                    );
                  },
                },
              ];
              if (d === "amenities" && onViewNearbyList) {
                domainMenuItems.push({
                  id: "nearby",
                  label: "View nearby list",
                  onSelect: () => onViewNearbyList(),
                });
              }
              if (d === "feasibility" && onOpenProfessional3D) {
                domainMenuItems.push({
                  id: "3d",
                  label: "Open 3D site view",
                  onSelect: onOpenProfessional3D,
                });
              }

              return (
                <section
                  key={d}
                  className={clsx(
                    "bento-card relative col-span-1 flex min-h-[11.5rem] w-full min-w-0 flex-col overflow-visible rounded-[1.5rem] border",
                    dark ? "border-gray-800 bg-gray-900" : "border-slate-200 bg-white",
                  )}
                >
                  <div className="absolute right-2.5 top-2.5 z-10">
                    <BentoCardMenu
                      dark={dark}
                      ariaLabel={`${domainLabel(d)} options`}
                      items={domainMenuItems}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleDomain(d)}
                    className="flex w-full flex-1 flex-col items-center justify-center px-3 pb-4 pt-5 text-center"
                    aria-expanded={false}
                  >
                    <ScoreRing score={r.score} size="md" color={bar} label={domainLabel(d)} />
                    <h3 className={clsx(
                      "mt-3 font-display text-base font-semibold tracking-tight",
                      dark ? "text-gray-100" : "text-slate-900",
                    )}>
                      {domainLabel(d)}
                    </h3>
                    <span
                      className={clsx(
                        "mt-2 inline-flex max-w-full rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                        badge.classes,
                      )}
                    >
                      {badge.label}
                    </span>
                  </button>
                </section>
              );
            })}

            {Object.keys(card.layer_versions).length > 0 && (
              <footer
                className={clsx(
                  "col-span-2 border-t pt-3 text-[10px]",
                  dark ? "border-gray-800 text-gray-500" : "border-slate-200 text-slate-400",
                )}
              >
                Layer versions:{" "}
                {Object.entries(card.layer_versions)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </footer>
            )}
            <p className={clsx("col-span-2 pb-2 text-center text-[10px] leading-relaxed", dark ? "text-gray-600" : "text-slate-400")}>
              Advisory property intelligence - not a legal or engineering sign-off · Geoinfotech / GGIS
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
