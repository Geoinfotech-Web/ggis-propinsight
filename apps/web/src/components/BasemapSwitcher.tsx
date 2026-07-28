import { useState } from "react";
import clsx from "clsx";
import { BASEMAPS, type BasemapId } from "../lib/basemap";
import type { Theme } from "../theme";

type Props = {
  theme: Theme;
  activeId: BasemapId;
  onChange: (id: BasemapId) => void;
};

/** Collapsible basemap control — sits bottom-left, clear of MapLibre zoom (top-right). */
export function BasemapSwitcher({ theme, activeId, onChange }: Props) {
  const dark = theme === "dark";
  const [open, setOpen] = useState(false);
  const active = BASEMAPS.find((b) => b.id === activeId) ?? BASEMAPS[0];

  return (
    <div
      className={clsx(
        "pointer-events-auto absolute bottom-12 left-3 z-[2] sm:bottom-14 sm:left-4",
      )}
    >
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={clsx(
            "rounded-xl border px-3 py-2 text-left shadow-sm",
            dark ? "border-gray-700 bg-gray-950/95 text-gray-100" : "border-slate-200 bg-white/95 text-slate-900",
          )}
          aria-expanded={false}
          aria-label="Open basemap picker"
        >
          <p
            className={clsx(
              "text-[9px] font-semibold uppercase tracking-[0.16em]",
              dark ? "text-sky-400" : "text-sky-700",
            )}
          >
            Basemap
          </p>
          <p className="text-xs font-semibold">{active.label}</p>
        </button>
      ) : (
        <div
          className={clsx(
            "w-44 rounded-xl border p-1.5 shadow-sm",
            dark ? "border-gray-700 bg-gray-950/95" : "border-slate-200 bg-white/95",
          )}
          role="group"
          aria-label="Basemap"
        >
          <div className="mb-1 flex items-center justify-between px-1.5">
            <p
              className={clsx(
                "text-[9px] font-semibold uppercase tracking-[0.16em]",
                dark ? "text-sky-400" : "text-sky-700",
              )}
            >
              Basemap
            </p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className={clsx(
                "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                dark ? "text-gray-400 hover:bg-gray-900" : "text-slate-500 hover:bg-slate-100",
              )}
              aria-label="Collapse basemap picker"
            >
              Close
            </button>
          </div>
          {BASEMAPS.map((b) => {
            const isActive = b.id === activeId;
            return (
              <button
                key={b.id}
                type="button"
                onClick={() => {
                  onChange(b.id);
                  setOpen(false);
                }}
                className={clsx(
                  "w-full rounded-lg px-2.5 py-1.5 text-left text-xs font-semibold transition-colors",
                  isActive
                    ? "bg-sky-700 text-white"
                    : dark
                      ? "text-gray-300 hover:bg-gray-800"
                      : "text-slate-700 hover:bg-slate-100",
                )}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
