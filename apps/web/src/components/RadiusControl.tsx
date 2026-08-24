import clsx from "clsx";
import {
  MAX_ANALYSIS_RADIUS_KM,
  MIN_ANALYSIS_RADIUS_KM,
  clampAnalysisRadius,
} from "../lib/analysisRadius";
import type { Theme } from "../theme";

type Props = {
  theme: Theme;
  value: number;
  onChange: (radiusKm: number) => void;
  idPrefix: string;
  compact?: boolean;
};

export function RadiusControl({ theme, value, onChange, idPrefix, compact = false }: Props) {
  const dark = theme === "dark";
  const inputId = `${idPrefix}-radius`;
  const commit = (raw: number) => onChange(clampAnalysisRadius(raw));
  const fillPercent = ((value - MIN_ANALYSIS_RADIUS_KM) / (MAX_ANALYSIS_RADIUS_KM - MIN_ANALYSIS_RADIUS_KM)) * 100;

  return (
    <div className={clsx(
      compact ? "space-y-1.5" : "space-y-5 rounded-2xl border p-5",
      !compact && (dark ? "border-gray-700 bg-gray-950/90 text-gray-100" : "border-white/70 bg-white/95 text-slate-900 shadow-sm"),
    )}>
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={inputId} className={clsx("font-semibold", compact ? "text-xs" : "text-base")}>
          Analysis radius
        </label>
        <div className={clsx(
          "flex items-center rounded-xl border",
          compact ? "gap-1" : "gap-0 border-[#087df1] px-1",
          dark && !compact ? "bg-gray-900" : "bg-white",
        )}>
          <input
            type="number"
            min={MIN_ANALYSIS_RADIUS_KM}
            max={MAX_ANALYSIS_RADIUS_KM}
            step={1}
            value={value}
            onChange={(event) => commit(Number(event.target.value))}
            aria-label="Analysis radius in kilometres"
            className={clsx(
              "w-12 rounded-lg px-2 text-right font-semibold tabular-nums outline-none",
              compact ? "border py-1 text-xs" : "border-0 py-2 text-base text-[#087df1]",
              dark
                ? compact ? "border-gray-700 bg-gray-950 text-gray-100" : "bg-gray-900"
                : compact ? "border-slate-200 bg-white text-slate-900" : "bg-white",
            )}
          />
          <span className={clsx(compact ? "pr-1 text-xs" : "pr-2 text-base font-semibold text-[#087df1]", compact && (dark ? "text-gray-400" : "text-slate-500"))}>km</span>
        </div>
      </div>
      <input
        id={inputId}
        type="range"
        min={MIN_ANALYSIS_RADIUS_KM}
        max={MAX_ANALYSIS_RADIUS_KM}
        step={1}
        value={value}
        onChange={(event) => commit(Number(event.target.value))}
        className="analysis-range h-2 w-full cursor-pointer accent-[#087df1]"
        style={{ background: `linear-gradient(90deg, #087df1 0 ${fillPercent}%, #dbe3ec ${fillPercent}% 100%)` }}
      />
      <div
        className={clsx(
          "flex justify-between text-[10px] tabular-nums",
          dark ? "text-gray-500" : "text-slate-400",
        )}
      >
        <span>{MIN_ANALYSIS_RADIUS_KM} km</span>
        {!compact && <span>{Math.floor((MIN_ANALYSIS_RADIUS_KM + MAX_ANALYSIS_RADIUS_KM) / 2)} km</span>}
        <span>{MAX_ANALYSIS_RADIUS_KM} km</span>
      </div>
    </div>
  );
}
