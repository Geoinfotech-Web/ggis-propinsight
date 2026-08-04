import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";
import { PERSONAS, getPersona, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconChevronDown, IconCheck } from "./Icons";

type Props = {
  theme: Theme;
  persona: PersonaKey;
  onPersonaChange: (key: PersonaKey) => void;
  className?: string;
};

/**
 * Target-user persona picker as a dropdown, sized to sit to the left of the
 * search bar. Closes on outside click or Escape.
 */
export function PersonaSelect({ theme, persona, onPersonaChange, className }: Props) {
  const dark = theme === "dark";
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const current = getPersona(persona);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const select = (key: PersonaKey) => {
    onPersonaChange(key);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className={clsx("relative shrink-0", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        title={current.blurb}
        className={clsx(
          "inline-flex h-10 items-center gap-1.5 rounded-xl border px-2.5 shadow-sm transition",
          dark
            ? "border-gray-700 bg-gray-900 text-gray-100 hover:bg-gray-800"
            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300",
        )}
      >
        <span
          className={clsx(
            "hidden text-[10px] font-medium uppercase tracking-wide sm:inline",
            dark ? "text-gray-500" : "text-slate-400",
          )}
        >
          For
        </span>
        <span className="text-[13px] font-semibold">
          <span className="sm:hidden">{current.shortLabel}</span>
          <span className="hidden sm:inline">{current.label}</span>
        </span>
        <IconChevronDown
          size={14}
          className={clsx("transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Target user"
          className={clsx(
            "absolute left-0 top-full z-30 mt-1.5 w-64 overflow-hidden rounded-xl border shadow-lg",
            dark ? "border-gray-700 bg-gray-900" : "border-slate-200 bg-white",
          )}
        >
          {PERSONAS.map((p) => {
            const active = p.key === persona;
            return (
              <li key={p.key} role="option" aria-selected={active}>
                <button
                  type="button"
                  onClick={() => select(p.key)}
                  className={clsx(
                    "flex w-full items-start gap-2 px-3 py-2 text-left transition",
                    active
                      ? dark
                        ? "bg-sky-950/60"
                        : "bg-sky-50"
                      : dark
                        ? "hover:bg-gray-800"
                        : "hover:bg-slate-50",
                  )}
                >
                  <span className="mt-0.5 h-4 w-4 shrink-0">
                    {active && (
                      <IconCheck size={16} className={dark ? "text-sky-400" : "text-sky-600"} />
                    )}
                  </span>
                  <span className="min-w-0">
                    <span
                      className={clsx(
                        "block text-[13px] font-semibold",
                        dark ? "text-gray-100" : "text-slate-800",
                      )}
                    >
                      {p.label}
                    </span>
                    <span
                      className={clsx(
                        "block text-[11px] leading-snug",
                        dark ? "text-gray-400" : "text-slate-500",
                      )}
                    >
                      {p.blurb}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
