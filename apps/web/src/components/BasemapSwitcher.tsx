import { useEffect, useRef, useState, type ComponentType } from "react";
import clsx from "clsx";
import { BASEMAPS, type BasemapId } from "../lib/basemap";
import type { Theme } from "../theme";
import {
  IconCheck,
  IconChevronLeft,
  IconChevronRight,
  IconGlobe,
  IconLayers,
  IconMap,
  IconMoon,
  IconMountain,
  IconSatellite,
  IconSun,
} from "./Icons";

type IconProps = { size?: number; className?: string };

const BASEMAP_ICON: Record<BasemapId, ComponentType<IconProps>> = {
  dark: IconMoon,
  positron: IconSun,
  streets: IconMap,
  satellite: IconSatellite,
  voyager: IconMountain,
};

type Props = {
  theme: Theme;
  activeId: BasemapId;
  onChange: (id: BasemapId) => void;
};

/** Flood Watch–style icon basemap control (menu opens left, clear of zoom). */
export function BasemapSwitcher({ theme, activeId, onChange }: Props) {
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
        title="Change basemap"
        className={clsx(
          "glass-tool liquid-tool-ivory inline-flex h-10 w-10 items-center justify-center rounded-xl border transition",
          dark
            ? "border-gray-700 bg-gray-900/60 text-gray-200 hover:border-gray-500 hover:bg-gray-800/80 hover:text-white"
            : "border-white/70 bg-white/60 text-slate-600 hover:border-slate-300 hover:text-slate-900",
        )}
        aria-label="Change basemap"
        aria-expanded={expanded}
      >
        <IconGlobe size={17} className={dark ? "text-sky-300" : "text-sky-700"} />
      </button>

      {expanded && (
        <div
          className={clsx(
            "glass-surface toolkit-glass absolute right-full top-0 z-30 mr-2 max-h-[min(50vh,22rem)] w-40 divide-y overflow-y-auto rounded-2xl border",
            dark
              ? "divide-gray-800 border-gray-700 bg-gray-900"
              : "divide-slate-200 border-slate-200 bg-white",
          )}
          role="menu"
          aria-label="Basemap options"
        >
          <div
            className={clsx(
              "flex items-center justify-between px-3 py-2 text-[11px] uppercase tracking-[0.18em]",
              dark ? "text-gray-500" : "text-slate-500",
            )}
          >
            <span>Basemap</span>
            {expanded ? (
              <IconChevronLeft size={11} className={dark ? "text-gray-500" : "text-slate-500"} />
            ) : (
              <IconChevronRight size={11} className={dark ? "text-gray-500" : "text-slate-500"} />
            )}
          </div>

          {BASEMAPS.map((b) => {
            const Icon = BASEMAP_ICON[b.id] ?? IconLayers;
            const active = activeId === b.id;
            return (
              <button
                key={b.id}
                type="button"
                role="menuitem"
                onClick={() => {
                  onChange(b.id);
                  setExpanded(false);
                }}
                className={clsx(
                  "flex w-full items-center gap-2.5 px-3 py-2.5 text-xs transition-colors",
                  active
                    ? dark
                      ? "bg-blue-950/45 text-blue-300"
                      : "bg-sky-100/45 text-sky-800"
                    : dark
                      ? "text-gray-300 hover:bg-gray-800/80 hover:text-white"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                <Icon
                  size={14}
                  className={active ? "text-blue-400" : dark ? "text-gray-400" : "text-slate-400"}
                />
                <span className="flex-1 text-left">{b.label}</span>
                {active && <IconCheck size={11} className="text-blue-400" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
