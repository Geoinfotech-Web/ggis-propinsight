import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";
import { getPersona, PERSONAS, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { RadiusControl } from "./RadiusControl";

export type AnalysisCandidate = {
  lon: number;
  lat: number;
  label?: string;
};

type Props = {
  theme: Theme;
  candidate: AnalysisCandidate | null;
  persona: PersonaKey;
  radiusKm: number;
  onPersonaChange: (persona: PersonaKey) => void;
  onRadiusChange: (radiusKm: number) => void;
  onCancel: () => void;
  onAnalyse: () => void;
};

export function AnalysisSetupDialog({
  theme,
  candidate,
  persona,
  radiusKm,
  onPersonaChange,
  onRadiusChange,
  onCancel,
  onAnalyse,
}: Props) {
  const dark = theme === "dark";
  const [step, setStep] = useState<1 | 2>(1);
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!candidate) return;
    setStep(1);
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      restoreFocusRef.current?.focus();
    };
  }, [candidate, onCancel]);

  useEffect(() => {
    if (!candidate) return;
    window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }, 0);
  }, [step, candidate]);

  if (!candidate) return null;
  const currentPersona = getPersona(persona);
  const place = candidate.label ?? `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/55 backdrop-blur-[2px]"
        aria-label="Cancel location analysis setup"
        onClick={onCancel}
      />
      <div
        ref={panelRef}
        className={clsx(
          "relative z-10 w-full max-w-lg overflow-hidden rounded-t-3xl border shadow-2xl sm:rounded-3xl",
          dark
            ? "border-gray-700 bg-gray-900 text-gray-100"
            : "border-slate-200 bg-white text-slate-900",
        )}
      >
        <div className={clsx("border-b px-5 py-4", dark ? "border-gray-800" : "border-slate-200")}>
          <div className="mb-3 flex items-center gap-2" aria-label={`Step ${step} of 2`}>
            {[1, 2].map((item) => (
              <span
                key={item}
                className={clsx(
                  "h-1.5 flex-1 rounded-full",
                  item <= step ? "bg-sky-600" : dark ? "bg-gray-700" : "bg-slate-200",
                )}
              />
            ))}
          </div>
          <p className={clsx("text-[10px] font-semibold uppercase tracking-[0.14em]", dark ? "text-sky-400" : "text-sky-700")}>
            Step {step} of 2
          </p>
          <h2 id={titleId} className="font-display text-xl font-semibold tracking-tight">
            {step === 1 ? "Who is this report for?" : "Set the analysis area"}
          </h2>
          <p className={clsx("mt-1 truncate text-xs", dark ? "text-gray-400" : "text-slate-500")} title={place}>
            {place}
          </p>
        </div>

        <div className="space-y-4 px-5 py-5">
          {step === 1 ? (
            <>
              <div>
                <label htmlFor="analysis-persona" className="mb-1.5 block text-xs font-semibold">
                  I am a
                </label>
                <select
                  id="analysis-persona"
                  data-autofocus
                  value={persona}
                  onChange={(event) => onPersonaChange(event.target.value as PersonaKey)}
                  className={clsx(
                    "w-full rounded-xl border px-3 py-3 text-sm font-semibold outline-none focus:border-sky-500",
                    dark
                      ? "border-gray-700 bg-gray-950 text-gray-100"
                      : "border-slate-200 bg-white text-slate-900",
                  )}
                >
                  {PERSONAS.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className={clsx("rounded-xl border px-3 py-3 text-sm", dark ? "border-sky-900 bg-sky-950/40 text-sky-100" : "border-sky-100 bg-sky-50 text-sky-950")}>
                <p className="font-semibold">Report for {currentPersona.label}</p>
                <p className="mt-1 text-xs leading-relaxed opacity-80">{currentPersona.blurb}</p>
              </div>
            </>
          ) : (
            <div data-autofocus tabIndex={-1} className="outline-none">
              <RadiusControl
                theme={theme}
                value={radiusKm}
                onChange={onRadiusChange}
                idPrefix="analysis-setup"
              />
              <p className={clsx("mt-4 rounded-xl border px-3 py-3 text-xs leading-relaxed", dark ? "border-gray-800 bg-gray-950/60 text-gray-300" : "border-slate-200 bg-slate-50 text-slate-600")}>
                Nearby amenities, police locations, and market evidence will use this radius. Flood, land use, tenure, and other plot-specific facts remain tied to the selected point.
              </p>
            </div>
          )}
        </div>

        <div className={clsx("flex items-center justify-between gap-3 border-t px-5 py-4", dark ? "border-gray-800" : "border-slate-200")}>
          <button
            type="button"
            onClick={onCancel}
            className={clsx("rounded-xl px-3 py-2 text-sm font-semibold", dark ? "text-gray-300 hover:bg-gray-800" : "text-slate-600 hover:bg-slate-100")}
          >
            Cancel
          </button>
          <div className="flex items-center gap-2">
            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(1)}
                className={clsx("rounded-xl border px-4 py-2 text-sm font-semibold", dark ? "border-gray-700 hover:bg-gray-800" : "border-slate-200 hover:bg-slate-50")}
              >
                Back
              </button>
            )}
            {step === 1 ? (
              <button
                type="button"
                onClick={() => setStep(2)}
                className="rounded-xl bg-sky-700 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-800"
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={onAnalyse}
                className="rounded-xl bg-sky-700 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-800"
              >
                Analyse Location
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
