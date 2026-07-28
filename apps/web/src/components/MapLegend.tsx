import { useState } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";
import type { OverlayLayer } from "./LayersPanel";
import { IconChevronDown, IconChevronUp } from "./Icons";

const SCORE_LEGEND = [
  { label: "Strong (70–100)", color: "#0d9488" },
  { label: "Moderate (40–69)", color: "#ca8a04" },
  { label: "Weak (0–39)", color: "#dc2626" },
  { label: "Pending / unavailable", color: "#94a3b8" },
];

type Props = {
  theme: Theme;
  layers: OverlayLayer[];
  collapsedByDefault?: boolean;
};

/** Flood Watch FloodRiskLegend chrome — bottom-left collapsible legend. */
export function MapLegend({ theme, layers, collapsedByDefault = false }: Props) {
  const [collapsed, setCollapsed] = useState(collapsedByDefault);
  const dark = theme === "dark";
  const visibleOverlays = layers.filter((l) => l.enabled);

  return (
    <div
      className={clsx(
        "w-56 overflow-hidden rounded-lg border shadow-xl",
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
        <span className={dark ? "text-gray-500" : "text-slate-500"}>
          {collapsed ? <IconChevronUp size={13} /> : <IconChevronDown size={13} />}
        </span>
      </button>

      {!collapsed && (
        <div className="max-h-[min(40vh,16rem)] space-y-3.5 overflow-y-auto p-3">
          <div>
            <p
              className={clsx(
                "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                dark ? "text-gray-500" : "text-slate-500",
              )}
            >
              Domain score
            </p>
            <div className="space-y-1.5">
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
          </div>

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
              <div className="space-y-1.5">
                {visibleOverlays.map((layer) => (
                  <div key={layer.id} className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 shrink-0 rounded-sm"
                      style={{ background: layer.swatch }}
                      aria-hidden
                    />
                    <span
                      className={clsx(
                        "text-[11px] font-medium",
                        dark ? "text-gray-200" : "text-slate-800",
                      )}
                    >
                      {layer.label}
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
