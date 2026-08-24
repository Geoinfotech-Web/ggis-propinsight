import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";
import { IconChevronLeft, IconLayers } from "./Icons";
import { PoiSymbol } from "./PoiSymbol";

export type OverlayLayerId =
  | "score_marker"
  | "flood_context"
  | "land_use"
  | "land_cover"
  | "school_poi"
  | "hospital_poi"
  | "bank_poi"
  | "market_poi"
  | "power_poi"
  | "fuel_poi"
  | "security_poi"
  | "government_projects";

export type OverlayLayer = {
  id: OverlayLayerId;
  label: string;
  description: string;
  swatch: string;
  symbol?: string;
  enabled: boolean;
};

type Props = {
  theme: Theme;
  layers: OverlayLayer[];
  onToggle: (id: OverlayLayerId) => void;
  radiusKm?: number;
};

function Toggle({
  label,
  on,
  onToggle,
  theme,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  theme: Theme;
}) {
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
      aria-label={`${on ? "Hide" : "Show"} ${label}`}
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
  symbol,
}: {
  label: string;
  hint?: string;
  on: boolean;
  onToggle: () => void;
  theme: Theme;
  swatch: string;
  symbol?: string;
}) {
  const dark = theme === "dark";
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {symbol ? (
            <PoiSymbol category={symbol} color={swatch} size={20} />
          ) : (
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: swatch }}
              aria-hidden
            />
          )}
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
      <Toggle label={label} on={on} onToggle={onToggle} theme={theme} />
    </div>
  );
}

/**
 * Flood Watch–style icon layers control: a 40×40 button matching the Home /
 * basemap buttons, opening a left-hand popover of overlay toggles.
 */
export function LayersPanel({ theme, layers, onToggle, radiusKm = 5 }: Props) {
  const [expanded, setExpanded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const dark = theme === "dark";

  useEffect(() => {
    if (!expanded) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setExpanded(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded]);

  return (
    <div ref={rootRef} className="relative z-20">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        title="Layers"
        className={clsx(
          "glass-tool liquid-tool-mint inline-flex h-10 w-10 items-center justify-center rounded-xl border transition",
          dark
            ? "border-teal-900/80 bg-teal-950/60 text-teal-300 hover:border-teal-700 hover:bg-teal-950/80"
            : "border-teal-100/80 bg-teal-50/60 text-teal-700 hover:border-teal-300 hover:bg-teal-100/80",
        )}
        aria-label="Layers"
        aria-expanded={expanded}
      >
        <IconLayers size={17} className={dark ? "text-teal-300" : "text-teal-700"} />
      </button>

      {expanded && (
        <div
          className={clsx(
            "glass-surface absolute right-full top-0 z-30 mr-2 w-[min(15.5rem,calc(100vw-4.5rem))] overflow-hidden rounded-2xl border",
            dark ? "border-gray-700 bg-gray-900" : "border-slate-200 bg-white",
          )}
          role="menu"
          aria-label="Overlay layers"
        >
          <div
            className={clsx(
              "flex items-center justify-between border-b px-3 py-2.5",
              dark ? "border-gray-800" : "border-slate-100",
            )}
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
            <IconChevronLeft size={12} className={dark ? "text-gray-500" : "text-slate-400"} />
          </div>

          <div className="max-h-[min(60vh,24rem)] space-y-3 overflow-y-auto p-3">
            {layers.map((layer) => (
              <Row
                key={layer.id}
                label={`${layer.label}${layer.id.endsWith("_poi") ? ` (${radiusKm} km)` : ""}`}
                hint={layer.description}
                on={layer.enabled}
                onToggle={() => onToggle(layer.id)}
                theme={theme}
                swatch={layer.swatch}
                symbol={layer.symbol}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
