import { useState } from "react";
import clsx from "clsx";
import { AMENITY_MARKER_COLORS } from "../lib/amenitiesMap";
import { LAND_USE_COLORS, LAND_USE_LEGEND } from "../lib/landUseMap";
import { LAND_COVER_LEGEND } from "../lib/landCoverMap";
import type { Theme } from "../theme";
import type { OverlayLayer } from "./LayersPanel";
import { IconChevronDown, IconChevronUp } from "./Icons";
import { PoiSymbol } from "./PoiSymbol";

const SCORE_LEGEND = [
  { label: "Strong (70–100)", color: "#0d9488" },
  { label: "Moderate (40–69)", color: "#ca8a04" },
  { label: "Weak (0–39)", color: "#dc2626" },
  { label: "Pending / unavailable", color: "#94a3b8" },
];

const AMENITY_LEGEND = [
  { id: "school_poi", label: "School", color: AMENITY_MARKER_COLORS.school },
  { id: "hospital_poi", label: "Hospital / clinic", color: AMENITY_MARKER_COLORS.hospital },
  { id: "bank_poi", label: "Bank", color: AMENITY_MARKER_COLORS.bank },
  { id: "market_poi", label: "Market", color: AMENITY_MARKER_COLORS.market },
  { id: "power_poi", label: "Power", color: AMENITY_MARKER_COLORS.power },
  { id: "fuel_poi", label: "Fuel station", color: AMENITY_MARKER_COLORS.fuel },
];

const SECURITY_LEGEND = [
  { id: "police", label: "Police station", color: AMENITY_MARKER_COLORS.police },
];

type Props = {
  theme: Theme;
  layers: OverlayLayer[];
  collapsedByDefault?: boolean;
  radiusKm?: number;
  amenityCounts?: Record<string, number>;
  securityCount?: number;
};

type ExpandableGroup = "amenities" | "land_use" | "land_cover";

const GROUP_PREVIEW_SIZE = 4;

function LegendMoreButton({
  theme,
  expanded,
  hiddenCount,
  onClick,
}: {
  theme: Theme;
  expanded: boolean;
  hiddenCount: number;
  onClick: () => void;
}) {
  if (hiddenCount <= 0 && !expanded) return null;
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide",
        dark ? "text-sky-400 hover:text-sky-300" : "text-sky-700 hover:text-sky-900",
      )}
      aria-expanded={expanded}
    >
      {expanded ? `First ${GROUP_PREVIEW_SIZE}` : `More · ${hiddenCount}`}
      {expanded ? <IconChevronUp size={11} /> : <IconChevronDown size={11} />}
    </button>
  );
}

/** Flood Watch FloodRiskLegend chrome — bottom-left collapsible legend. */
export function MapLegend({
  theme,
  layers,
  collapsedByDefault = false,
  radiusKm = 5,
  amenityCounts,
  securityCount,
}: Props) {
  const [collapsed, setCollapsed] = useState(collapsedByDefault);
  const [expandedGroup, setExpandedGroup] = useState<ExpandableGroup | null>(null);
  const dark = theme === "dark";
  const visibleOverlays = layers.filter(
    (layer) =>
      layer.enabled &&
      (layer.id === "score_marker" ||
        layer.id === "flood_context" ||
        layer.id === "government_projects"),
  );
  const visibleAmenityLegend = AMENITY_LEGEND.filter((item) =>
    layers.some((layer) => layer.id === item.id && layer.enabled),
  );
  const showSecurityCats = layers.some((l) => l.id === "security_poi" && l.enabled);
  const showLandUse = layers.some((l) => l.id === "land_use" && l.enabled);
  const showLandCover = layers.some((l) => l.id === "land_cover" && l.enabled);
  const toggleGroup = (group: ExpandableGroup) =>
    setExpandedGroup((current) => (current === group ? null : group));
  const visibleAmenities = expandedGroup === "amenities"
    ? visibleAmenityLegend.slice(GROUP_PREVIEW_SIZE)
    : visibleAmenityLegend.slice(0, GROUP_PREVIEW_SIZE);
  const visibleLandUse = expandedGroup === "land_use"
    ? LAND_USE_LEGEND.slice(GROUP_PREVIEW_SIZE)
    : LAND_USE_LEGEND.slice(0, GROUP_PREVIEW_SIZE);
  const visibleLandCover = expandedGroup === "land_cover"
    ? LAND_COVER_LEGEND.slice(GROUP_PREVIEW_SIZE)
    : LAND_COVER_LEGEND.slice(0, GROUP_PREVIEW_SIZE);

  return (
    <div
      className={clsx(
        "w-[min(22rem,calc(100vw-6rem))] overflow-hidden rounded-lg border shadow-xl",
        dark ? "border-gray-700/80 bg-gray-900/90 backdrop-blur" : "border-slate-200 bg-white",
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className={clsx(
          "flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left transition",
          dark ? "border-gray-800/90 hover:bg-gray-800/40" : "border-slate-200 hover:bg-slate-50",
        )}
        aria-label={collapsed ? "Expand legend" : "Collapse legend"}
      >
        <p
          className={clsx(
            "text-[10px] font-semibold uppercase tracking-widest",
            dark ? "text-gray-500" : "text-slate-500",
          )}
        >
          Legend
        </p>
        <span className="flex items-center gap-2">
          <span
            className={clsx(
              "flex items-center gap-1.5 text-[10px] font-semibold tabular-nums",
              dark ? "text-sky-300" : "text-sky-700",
            )}
          >
            <span
              className="h-2.5 w-4 rounded-sm border-2 border-dashed border-sky-600 bg-sky-400/10"
              aria-hidden
            />
            {radiusKm} km
          </span>
          <span className={dark ? "text-gray-500" : "text-slate-500"}>
            {collapsed ? <IconChevronUp size={13} /> : <IconChevronDown size={13} />}
          </span>
        </span>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-2 items-start gap-x-3 gap-y-2 p-3">
          <div className="col-span-2">
            <p
              className={clsx(
                "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                dark ? "text-gray-500" : "text-slate-500",
              )}
            >
              Suitability scores
            </p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1">
              {SCORE_LEGEND.map((item) => (
                <div key={item.label} className="flex items-center gap-2">
                  <span
                    className="h-3 w-3 shrink-0 rounded-sm"
                    style={{ background: item.color }}
                    aria-hidden
                  />
                  <span
                    className={clsx(
                      "text-[11px] font-medium",
                      dark ? "text-gray-200" : "text-slate-800",
                    )}
                  >
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
            <p
              className={clsx(
                "mt-1.5 text-[9px] leading-snug",
                dark ? "text-sky-300" : "text-sky-800",
              )}
            >
              Flood uses a hazard score: higher means greater risk.
            </p>
          </div>

          {visibleAmenityLegend.length > 0 && (
            <div>
              <p
                className={clsx(
                  "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                  dark ? "text-gray-500" : "text-slate-500",
                )}
              >
                Amenities ({radiusKm} km)
              </p>
              <div className="space-y-1">
                {visibleAmenities.map((item) => {
                  const category = item.id.replace("_poi", "");
                  const count = amenityCounts?.[category];
                  return (
                    <div key={item.id} className="flex items-center gap-2">
                      <PoiSymbol category={category} color={item.color} size={20} />
                      <span
                        className={clsx(
                          "text-[11px] font-medium",
                          dark ? "text-gray-200" : "text-slate-800",
                        )}
                      >
                        {item.label}
                        {typeof count === "number" && ` · ${count}`}
                      </span>
                    </div>
                  );
                })}
              </div>
              <LegendMoreButton
                theme={theme}
                expanded={expandedGroup === "amenities"}
                hiddenCount={visibleAmenityLegend.length - GROUP_PREVIEW_SIZE}
                onClick={() => toggleGroup("amenities")}
              />
            </div>
          )}

          {showSecurityCats && (
            <div>
              <p
                className={clsx(
                  "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                  dark ? "text-gray-500" : "text-slate-500",
                )}
              >
                Security ({radiusKm} km)
              </p>
              <div className="space-y-1">
                {SECURITY_LEGEND.map((item) => (
                  <div key={item.id} className="flex items-center gap-2">
                    <PoiSymbol category={item.id} color={item.color} size={20} />
                    <span
                      className={clsx(
                        "text-[11px] font-medium",
                        dark ? "text-gray-200" : "text-slate-800",
                      )}
                    >
                      {item.label}
                      {typeof securityCount === "number" && ` · ${securityCount}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {showLandUse && (
            <div>
              <p
                className={clsx(
                  "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                  dark ? "text-gray-500" : "text-slate-500",
                )}
              >
                Land use (reference)
              </p>
              <div className="space-y-1">
                {visibleLandUse.map(([category, label]) => (
                  <div key={category} className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 shrink-0 rounded-sm border border-black/10"
                      style={{ background: LAND_USE_COLORS[category] }}
                      aria-hidden
                    />
                    <span
                      className={clsx(
                        "text-[11px] font-medium",
                        dark ? "text-gray-200" : "text-slate-800",
                      )}
                    >
                      {label}
                    </span>
                  </div>
                ))}
              </div>
              <LegendMoreButton
                theme={theme}
                expanded={expandedGroup === "land_use"}
                hiddenCount={LAND_USE_LEGEND.length - GROUP_PREVIEW_SIZE}
                onClick={() => toggleGroup("land_use")}
              />
              <p
                className={clsx(
                  "mt-2 text-[9px] leading-snug",
                  dark ? "text-amber-300" : "text-amber-800",
                )}
              >
                Reference only · verify with AGIS/FCTA.
              </p>
            </div>
          )}

          {showLandCover && (
            <div>
              <p
                className={clsx(
                  "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                  dark ? "text-gray-500" : "text-slate-500",
                )}
              >
                Observed land cover · FCT
              </p>
              <div className="space-y-1">
                {visibleLandCover.map(([color, label]) => (
                  <div key={label} className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 shrink-0 rounded-sm border border-black/10"
                      style={{ background: color }}
                      aria-hidden
                    />
                    <span
                      className={clsx(
                        "text-[11px] font-medium",
                        dark ? "text-gray-200" : "text-slate-800",
                      )}
                    >
                      {label}
                    </span>
                  </div>
                ))}
              </div>
              <LegendMoreButton
                theme={theme}
                expanded={expandedGroup === "land_cover"}
                hiddenCount={LAND_COVER_LEGEND.length - GROUP_PREVIEW_SIZE}
                onClick={() => toggleGroup("land_cover")}
              />
              <p
                className={clsx(
                  "mt-2 text-[9px] leading-snug",
                  dark ? "text-sky-300" : "text-sky-800",
                )}
              >
                Observed cover · not zoning.
              </p>
            </div>
          )}

          {visibleOverlays.length > 0 && (
            <div>
              <p
                className={clsx(
                  "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                  dark ? "text-gray-500" : "text-slate-500",
                )}
              >
                Overlays
              </p>
              <div className="space-y-1">
                {visibleOverlays.map((layer) => (
                  <div key={layer.id} className="flex items-center gap-2">
                    {layer.symbol ? (
                      <PoiSymbol category={layer.symbol} color={layer.swatch} size={20} />
                    ) : (
                      <span
                        className="h-3 w-3 shrink-0 rounded-sm"
                        style={{ background: layer.swatch }}
                        aria-hidden
                      />
                    )}
                    <span
                      className={clsx(
                        "text-[11px] font-medium",
                        dark ? "text-gray-200" : "text-slate-800",
                      )}
                    >
                      {layer.label}
                      {layer.id === "government_projects" && ` (${radiusKm} km)`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
