import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";
import { IconChevronLeft, IconChevronRight } from "./Icons";

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
  categoryCounts?: Record<string, number>;
  elevated?: boolean;
  radiusKm?: number;
  totalCount?: number;
  onClose: () => void;
  onCategoryChange?: (category: string) => void;
  onSelect?: (item: NearbyPoiItem) => void;
};

/** Full amenities list within the scorecard's selected search radius. */
export function NearbyAmenitiesList({
  theme,
  items,
  open,
  category,
  categoryCounts,
  elevated = false,
  radiusKm = 5,
  totalCount,
  onClose,
  onCategoryChange,
  onSelect,
}: Props) {
  const dark = theme === "dark";
  const tabsRef = useRef<HTMLDivElement>(null);
  const activeTabRef = useRef<HTMLButtonElement>(null);
  const [tabScroll, setTabScroll] = useState({ left: false, right: false });
  const availableCategories = CATEGORY_ORDER.filter((cat) => {
    const count = categoryCounts?.[cat] ?? items.filter((item) => item.category === cat).length;
    return count > 0 || cat === category;
  });
  const activeCategory = category && availableCategories.includes(category as (typeof CATEGORY_ORDER)[number])
    ? category
    : availableCategories[0] ?? category ?? null;
  const visibleItems = activeCategory
    ? items.filter((item) => item.category === activeCategory).sort((a, b) => a.distance_m - b.distance_m)
    : [];
  const activeTotal = activeCategory
    ? categoryCounts?.[activeCategory] ?? totalCount ?? visibleItems.length
    : totalCount ?? 0;

  useEffect(() => {
    if (!open) return undefined;
    const strip = tabsRef.current;
    if (!strip) return undefined;
    const updateScrollState = () => {
      const maxScrollLeft = strip.scrollWidth - strip.clientWidth;
      setTabScroll({
        left: strip.scrollLeft > 2,
        right: strip.scrollLeft < maxScrollLeft - 2,
      });
    };
    updateScrollState();
    strip.addEventListener("scroll", updateScrollState, { passive: true });
    const resizeObserver = new ResizeObserver(updateScrollState);
    resizeObserver.observe(strip);
    return () => {
      strip.removeEventListener("scroll", updateScrollState);
      resizeObserver.disconnect();
    };
  }, [open, availableCategories.length]);

  useEffect(() => {
    if (!open) return;
    activeTabRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [activeCategory, open]);

  if (!open) return null;

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
        className="absolute inset-0 bg-slate-950/10 backdrop-blur-[2px]"
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
              Amenities
            </h2>
            <p className={clsx("text-[11px]", dark ? "text-gray-400" : "text-slate-500")}>
              {activeTotal > visibleItems.length
                ? `Showing ${visibleItems.length} closest of ${activeTotal} places`
                : `${visibleItems.length} place${visibleItems.length === 1 ? "" : "s"}`}
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

        {availableCategories.length > 0 && (
          <div
            className={clsx(
              "relative shrink-0 border-b",
              dark ? "border-gray-800" : "border-slate-200/80",
            )}
          >
            <div
              ref={tabsRef}
              className={clsx(
                "amenity-tabs-scroll flex divide-x overflow-x-auto px-8",
                dark ? "divide-gray-700/80" : "divide-slate-300/80",
              )}
              role="tablist"
              aria-label="Amenity categories"
            >
              {availableCategories.map((cat) => {
                const selected = cat === activeCategory;
                const count = categoryCounts?.[cat] ?? items.filter((item) => item.category === cat).length;
                return (
                  <button
                    key={cat}
                    ref={selected ? activeTabRef : undefined}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls="nearby-amenities-panel"
                    onClick={() => onCategoryChange?.(cat)}
                    className={clsx(
                      "relative inline-flex shrink-0 items-center gap-1.5 px-3 py-3 text-xs font-semibold transition focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-400",
                      selected
                        ? dark
                          ? "text-sky-200 after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-sky-400"
                          : "text-sky-800 after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-sky-600"
                        : dark
                          ? "text-gray-300 hover:bg-white/5 hover:text-white"
                          : "text-slate-600 hover:bg-white/25 hover:text-slate-900",
                    )}
                  >
                    <span>{CATEGORY_LABELS[cat] ?? cat}</span>
                    <span
                      className={clsx(
                        "text-[10px] font-medium tabular-nums",
                        selected
                          ? dark ? "text-sky-300" : "text-sky-700"
                          : dark ? "text-gray-500" : "text-slate-400",
                      )}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
            {tabScroll.left && (
              <button
                type="button"
                aria-label="Scroll amenity categories left"
                onClick={() => tabsRef.current?.scrollBy({ left: -180, behavior: "smooth" })}
                className={clsx(
                  "absolute inset-y-0 left-0 z-10 flex w-8 items-center justify-center border-r",
                  dark
                    ? "border-gray-700 bg-gray-900/65 text-gray-200"
                    : "border-slate-200 bg-white/70 text-slate-600",
                )}
              >
                <IconChevronLeft size={14} />
              </button>
            )}
            {tabScroll.right && (
              <button
                type="button"
                aria-label="Scroll amenity categories right"
                onClick={() => tabsRef.current?.scrollBy({ left: 180, behavior: "smooth" })}
                className={clsx(
                  "absolute inset-y-0 right-0 z-10 flex w-8 items-center justify-center border-l",
                  dark
                    ? "border-gray-700 bg-gray-900/65 text-gray-200"
                    : "border-slate-200 bg-white/70 text-slate-600",
                )}
              >
                <IconChevronRight size={14} />
              </button>
            )}
          </div>
        )}

        <div
          id="nearby-amenities-panel"
          role="tabpanel"
          className="flex-1 space-y-4 overflow-y-auto px-4 py-3"
        >
          {visibleItems.length === 0 ? (
            <p className={clsx("text-sm", dark ? "text-gray-400" : "text-slate-500")}>
              No named {activeCategory ? (CATEGORY_LABELS[activeCategory] ?? activeCategory).toLowerCase() : "amenities"} found in this radius.
            </p>
          ) : (
            <ul className={clsx("divide-y rounded-xl border", dark ? "divide-gray-800 border-gray-800" : "divide-slate-100 border-slate-200")}>
              {visibleItems.map((p) => (
                <li key={`${p.category}-${p.name}-${p.distance_m}`}>
                  <button
                    type="button"
                    className={clsx(
                      "flex w-full items-baseline justify-between gap-3 px-3 py-2.5 text-left text-sm transition",
                      dark ? "hover:bg-gray-800/80" : "hover:bg-white/45",
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
          )}
        </div>
      </div>
    </div>
  );
}
