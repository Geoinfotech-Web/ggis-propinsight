import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { searchPlaces, type PlaceHit } from "../lib/geocode";
import type { Theme } from "../theme";
import { IconSearch, IconX } from "./Icons";

type Props = {
  theme?: Theme;
  size?: "md" | "lg";
  placeholder?: string;
  resetKey?: number;
  onResult: (hit: PlaceHit) => void;
};

/** Flood Watch–style search field (bordered shell, icon, clear, dropdown). */
export function SearchBar({
  theme = "light",
  size = "md",
  placeholder = "Search a place, district, or landmark…",
  resetKey = 0,
  onResult,
}: Props) {
  const dark = theme === "dark";
  const large = size === "lg";
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlaceHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    setQuery("");
    setResults([]);
    setOpen(false);
    setLoading(false);
  }, [resetKey]);

  useEffect(() => {
    abortRef.current?.abort();
    if (query.trim().length < 2) {
      setResults([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    const t = window.setTimeout(() => {
      searchPlaces(query, ctrl.signal)
        .then((rows) => {
          if (ctrl.signal.aborted) return;
          setResults(rows);
          setOpen(rows.length > 0);
        })
        .catch(() => {
          if (!ctrl.signal.aborted) {
            setResults([]);
            setOpen(false);
          }
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, 400);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [query]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const select = (hit: PlaceHit) => {
    setQuery(hit.label.split(",")[0] ?? hit.label);
    setOpen(false);
    onResult(hit);
  };

  return (
    <div ref={wrapRef} className="relative w-full">
      <div
        className={clsx(
          "flex items-center gap-2 border shadow-lg backdrop-blur transition-colors focus-within:border-sky-500/70",
          large ? "rounded-2xl px-4" : "rounded-lg px-3",
          dark ? "border-gray-700 bg-gray-900/95" : "border-slate-200 bg-white/96",
        )}
      >
        {loading ? (
          <span
            className={clsx(
              "h-4 w-4 shrink-0 animate-spin rounded-full border-2",
              dark ? "border-gray-600 border-t-sky-400" : "border-slate-300 border-t-sky-600",
            )}
          />
        ) : (
          <IconSearch
            size={large ? 17 : 15}
            className={clsx("shrink-0", dark ? "text-gray-500" : "text-slate-500")}
          />
        )}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className={clsx(
            "flex-1 bg-transparent outline-none",
            large ? "py-3.5 text-[15px]" : "py-2.5 text-sm",
            dark ? "text-white placeholder-gray-500" : "text-slate-900 placeholder-slate-400",
          )}
        />
        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setResults([]);
              setOpen(false);
            }}
            className={clsx(
              "shrink-0 transition-colors",
              dark ? "text-gray-500 hover:text-gray-300" : "text-slate-500 hover:text-slate-700",
            )}
            aria-label="Clear search"
          >
            <IconX size={13} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div
          className={clsx(
            "absolute top-full z-50 mt-1.5 w-full divide-y overflow-hidden border shadow-2xl backdrop-blur",
            large ? "rounded-2xl" : "rounded-lg",
            dark
              ? "divide-gray-800 border-gray-700 bg-gray-900/98"
              : "divide-slate-200 border-slate-200 bg-white/98",
          )}
        >
          {results.map((r) => {
            const short = r.label.split(",")[0] ?? r.label;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => select(r)}
                className={clsx(
                  "w-full px-4 py-2.5 text-left transition-colors",
                  dark ? "hover:bg-gray-800" : "hover:bg-slate-100",
                )}
              >
                <p className={clsx("text-sm font-semibold", dark ? "text-white" : "text-slate-900")}>
                  {short}
                </p>
                <p className={clsx("truncate text-[11px]", dark ? "text-gray-400" : "text-slate-500")}>
                  {r.label}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
