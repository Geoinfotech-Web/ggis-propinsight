import { useState } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";
import { IconChevronDown, IconChevronUp, IconLayers } from "./Icons";

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

function Toggle({ on, onToggle, theme }: { on: boolean; onToggle: () => void; theme: Theme }) {
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onToggle}
      className={clsx(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200",
        on ? "bg-sky-600" : dark ? "bg-gray-600" : "bg-slate-300",
      )}
      role="switch"
      aria-checked={on}
    >
      <span
        className={clsx(
          "inline-block h-4 w-4 translate-y-0.5 rounded-full bg-white shadow transition",
          on ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

function Row({
  label,
  hint,
  on,
  onToggle,
  theme,
  swatch,
}: {
  label: string;
  hint?: string;
  on: boolean;
  onToggle: () => void;
  theme: Theme;
  swatch: string;
}) {
  const dark = theme === "dark";
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
            style={{ backgroundColor: swatch }}
            aria-hidden
          />
          <p className={clsx("text-[12px] font-medium leading-tight", dark ? "text-gray-200" : "text-slate-800")}>
            {label}
          </p>
        </div>
        {hint ? (
          <p className={clsx("mt-0.5 text-[10px] leading-snug", dark ? "text-gray-500" : "text-slate-500")}>
            {hint}
          </p>
        ) : null}
      </div>
      <Toggle on={on} onToggle={onToggle} theme={theme} />
    </div>
  );
}

/** Flood Watch LayersPanel chrome — collapsible, sectioned toggles. */
export function LayersPanel({ theme, layers, onToggle }: Props) {
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.matchMedia("(min-width: 768px)").matches;
  });
  const dark = theme === "dark";

  return (
    <div
      className={clsx(
        "w-[min(15.5rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border shadow-xl",
        dark ? "border-gray-700 bg-gray-900" : "border-slate-200 bg-white",
      )}
      style={
        dark
          ? { backgroundColor: "#111827", borderColor: "#374151" }
          : { backgroundColor: "#ffffff", borderColor: "#e2e8f0" }
      }
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={clsx(
          "flex w-full items-center justify-between gap-2 border-b px-3 py-2.5 text-left transition",
          dark ? "border-gray-800 hover:bg-gray-800/50" : "border-slate-100 hover:bg-slate-50",
        )}
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2">
          <IconLayers size={14} className={dark ? "text-sky-400" : "text-sky-700"} />
          <span
            className={clsx(
              "text-xs font-semibold uppercase tracking-wide",
              dark ? "text-gray-200" : "text-slate-800",
            )}
          >
            Layers
          </span>
        </span>
        <span className={dark ? "text-gray-500" : "text-slate-400"}>
          {open ? <IconChevronUp size={13} /> : <IconChevronDown size={13} />}
        </span>
      </button>

      {open && (
        <div className="max-h-[min(70vh,28rem)] space-y-3 overflow-y-auto p-3">
          <div
            className={clsx(
              "space-y-3 border-t pt-3",
              dark ? "border-gray-800" : "border-slate-200",
            )}
          >
            <p
              className={clsx(
                "text-[10px] font-semibold uppercase tracking-widest",
                dark ? "text-gray-500" : "text-slate-500",
              )}
            >
              Location intelligence
            </p>
            {layers.map((layer) => (
              <Row
                key={layer.id}
                label={layer.label}
                hint={layer.description}
                on={layer.enabled}
                onToggle={() => onToggle(layer.id)}
                theme={theme}
                swatch={layer.swatch}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
