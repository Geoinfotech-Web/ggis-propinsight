import clsx from "clsx";
import type { Theme } from "../theme";

export type NearbyPoiItem = {
  category: string;
  name: string;
  distance_m: number;
  lon?: number;
  lat?: number;
};

const CATEGORY_LABELS: Record<string, string> = {
  school: "Schools",
  hospital: "Hospitals / clinics",
  market: "Markets",
  bank: "Banks",
  power: "Power infrastructure",
  fuel: "Fuel stations",
};

const CATEGORY_ORDER = ["school", "hospital", "market", "bank", "power", "fuel"] as const;

function formatMetres(m: number): string {
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toFixed(1)} km`;
}

type Props = {
  theme: Theme;
  items: NearbyPoiItem[];
  open: boolean;
  category?: string | null;
  elevated?: boolean;
  radiusKm?: number;
  totalCount?: number;
  onClose: () => void;
  onSelect?: (item: NearbyPoiItem) => void;
};

/** Full amenities list within the scorecard's selected search radius. */
export function NearbyAmenitiesList({ theme, items, open, category, elevated = false, radiusKm = 5, totalCount, onClose, onSelect }: Props) {
  if (!open) return null;
  const dark = theme === "dark";
  const visibleItems = category ? items.filter((item) => item.category === category) : items;
  const groups = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: visibleItems.filter((p) => p.category === cat).sort((a, b) => a.distance_m - b.distance_m),
  })).filter((g) => g.items.length > 0);
  const title = category ? (CATEGORY_LABELS[category] ?? category) : "Amenities";

  return (
    <div
      className={clsx(
        "fixed inset-0 flex items-end justify-center sm:items-center sm:p-4",
        elevated ? "z-[90]" : "z-50",
      )}
      role="dialog"
      aria-modal
      aria-labelledby="nearby-amenities-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/20 backdrop-blur-[2px]"
        aria-label="Close amenities list"
        onClick={onClose}
      />
      <div
        className={clsx(
          "glass-surface view-list-glass relative z-10 flex max-h-[min(85vh,36rem)] w-full max-w-md flex-col overflow-hidden rounded-t-3xl border sm:rounded-3xl",
          dark ? "border-gray-700 bg-gray-900 text-gray-100" : "border-slate-200 bg-white text-slate-900",
        )}
      >
        <div
          className={clsx(
            "flex items-start justify-between gap-3 border-b px-4 py-3",
            dark ? "border-gray-800" : "border-slate-200",
          )}
        >
          <div>
            <p className={clsx("text-[10px] font-semibold uppercase tracking-[0.14em]", dark ? "text-sky-400" : "text-sky-700")}>
              Within {radiusKm} km
            </p>
            <h2 id="nearby-amenities-title" className="font-display text-lg font-semibold tracking-tight">
              {title}
            </h2>
            <p className={clsx("text-[11px]", dark ? "text-gray-400" : "text-slate-500")}>
              {totalCount && totalCount > visibleItems.length
                ? `Showing ${visibleItems.length} closest of ${totalCount} places`
                : `${visibleItems.length} place${visibleItems.length === 1 ? "" : "s"}`}
              {!category && " · schools, hospitals, markets, banks"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={clsx(
              "rounded-lg border px-2.5 py-1 text-xs font-semibold",
              dark ? "border-gray-700 text-gray-300 hover:bg-gray-800" : "border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
          {groups.length === 0 ? (
            <p className={clsx("text-sm", dark ? "text-gray-400" : "text-slate-500")}>
              No named amenities found in this radius.
            </p>
          ) : (
            groups.map(({ cat, items: groupItems }) => (
              <section key={cat}>
                <h3
                  className={clsx(
                    "mb-1.5 text-[10px] font-semibold uppercase tracking-widest",
                    dark ? "text-gray-500" : "text-slate-400",
                  )}
                >
                  {CATEGORY_LABELS[cat] ?? cat} · {groupItems.length}
                </h3>
                <ul className={clsx("divide-y rounded-lg border", dark ? "divide-gray-800 border-gray-800" : "divide-slate-100 border-slate-200")}>
                  {groupItems.map((p) => (
                    <li key={`${p.category}-${p.name}-${p.distance_m}`}>
                      <button
                        type="button"
                        className={clsx(
                          "flex w-full items-baseline justify-between gap-3 px-3 py-2.5 text-left text-sm transition",
                          dark ? "hover:bg-gray-800/80" : "hover:bg-slate-50",
                          !onSelect && "cursor-default",
                        )}
                        onClick={() => onSelect?.(p)}
                        disabled={!onSelect}
                      >
                        <span className="min-w-0 font-medium leading-snug">{p.name}</span>
                        <span className={clsx("shrink-0 tabular-nums text-xs", dark ? "text-gray-400" : "text-slate-500")}>
                          {formatMetres(p.distance_m)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
