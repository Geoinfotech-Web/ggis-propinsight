import { useState } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";

export type OverlayLayerId = "score_marker" | "flood_context" | "amenities_poi";

export type OverlayLayer = {
  id: OverlayLayerId;
  label: string;
  description: string;
  swatch: string;
  enabled: boolean;
};

type Props = {
  theme: Theme;
  layers: OverlayLayer[];
  onToggle: (id: OverlayLayerId) => void;
};

const SCORE_LEGEND = [
  { label: "Strong (70–100)", color: "#0d9488" },
  { label: "Moderate (40–69)", color: "#ca8a04" },
  { label: "Weak (0–39)", color: "#dc2626" },
  { label: "Pending / unavailable", color: "#94a3b8" },
];

/** Flood-dashboard style layers + legend stack (bottom-left, above basemap). */
export function LayersLegendPanel({ theme, layers, onToggle }: Props) {
  const dark = theme === "dark";
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<"layers" | "legend">("layers");

  return (
    <div className="pointer-events-auto absolute bottom-28 left-3 z-[2] w-[min(17.5rem,calc(100%-1.5rem))] sm:bottom-32 sm:left-4">
      <div
        className={clsx(
          "overflow-hidden rounded-xl border shadow-sm",
          dark ? "border-gray-700 bg-gray-950/95 text-gray-100" : "border-slate-200 bg-white/95 text-slate-900",
        )}
      >
        <div
          className={clsx(
            "flex items-center justify-between border-b px-3 py-2",
            dark ? "border-gray-800" : "border-slate-200",
          )}
        >
          <div className="flex gap-1">
            {(["layers", "legend"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => {
                  setTab(t);
                  setOpen(true);
                }}
                className={clsx(
                  "rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]",
                  tab === t
                    ? "bg-sky-700 text-white"
                    : dark
                      ? "text-gray-400 hover:bg-gray-900"
                      : "text-slate-500 hover:bg-slate-100",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className={clsx(
              "text-[10px] font-semibold",
              dark ? "text-gray-400" : "text-slate-500",
            )}
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"}
          </button>
        </div>

        {open && (
          <div className="max-h-52 overflow-y-auto px-3 py-2">
            {tab === "layers" ? (
              <ul className="space-y-2">
                {layers.map((layer) => (
                  <li key={layer.id} className="flex items-start gap-2">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={layer.enabled}
                      onClick={() => onToggle(layer.id)}
                      className={clsx(
                        "mt-0.5 h-4 w-7 shrink-0 rounded-full transition-colors",
                        layer.enabled ? "bg-sky-600" : dark ? "bg-gray-600" : "bg-slate-300",
                      )}
                    >
                      <span
                        className={clsx(
                          "block h-3 w-3 translate-y-0.5 rounded-full bg-white transition-transform",
                          layer.enabled ? "translate-x-3.5" : "translate-x-0.5",
                        )}
                      />
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                          style={{ backgroundColor: layer.swatch }}
                          aria-hidden
                        />
                        <p className="text-xs font-semibold">{layer.label}</p>
                      </div>
                      <p className={clsx("text-[10px] leading-snug", dark ? "text-gray-500" : "text-slate-400")}>
                        {layer.description}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="space-y-3">
                <div>
                  <p
                    className={clsx(
                      "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                      dark ? "text-gray-500" : "text-slate-400",
                    )}
                  >
                    Domain score
                  </p>
                  <ul className="space-y-1.5">
                    {SCORE_LEGEND.map((row) => (
                      <li key={row.label} className="flex items-center gap-2 text-[11px]">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: row.color }}
                        />
                        <span className={dark ? "text-gray-300" : "text-slate-600"}>{row.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p
                    className={clsx(
                      "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                      dark ? "text-gray-500" : "text-slate-400",
                    )}
                  >
                    Overlays
                  </p>
                  <ul className="space-y-1.5">
                    {layers.map((layer) => (
                      <li key={layer.id} className="flex items-center gap-2 text-[11px]">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-sm"
                          style={{ backgroundColor: layer.swatch }}
                        />
                        <span className={dark ? "text-gray-300" : "text-slate-600"}>{layer.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
