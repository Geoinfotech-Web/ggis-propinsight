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

  return (
    <div className={clsx("space-y-2", compact && "space-y-1.5")}>
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={inputId} className="text-xs font-semibold">
          Analysis radius
        </label>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min={MIN_ANALYSIS_RADIUS_KM}
            max={MAX_ANALYSIS_RADIUS_KM}
            step={1}
            value={value}
            onChange={(event) => commit(Number(event.target.value))}
            aria-label="Analysis radius in kilometres"
            className={clsx(
              "w-14 rounded-lg border px-2 py-1 text-right text-xs font-semibold tabular-nums outline-none focus:border-sky-500",
              dark
                ? "border-gray-700 bg-gray-950 text-gray-100"
                : "border-slate-200 bg-white text-slate-900",
            )}
          />
          <span className={clsx("text-xs", dark ? "text-gray-400" : "text-slate-500")}>km</span>
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
        className="h-2 w-full cursor-pointer accent-sky-600"
      />
      <div
        className={clsx(
          "flex justify-between text-[10px] tabular-nums",
          dark ? "text-gray-500" : "text-slate-400",
        )}
      >
        <span>{MIN_ANALYSIS_RADIUS_KM} km</span>
        <span>{MAX_ANALYSIS_RADIUS_KM} km</span>
      </div>
    </div>
  );
}
