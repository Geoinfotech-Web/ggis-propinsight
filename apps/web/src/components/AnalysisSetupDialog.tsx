import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";
import type { Scorecard } from "../api";
import { getPersona, PERSONAS, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { RadiusControl } from "./RadiusControl";

export type AnalysisCandidate = {
  lon: number;
  lat: number;
  label?: string;
};

export type AnalysisFlowPhase = "setup" | "analysing" | "ready" | "error";
export type PdfGenerationStatus = "idle" | "generating" | "downloaded" | "error";

type Props = {
  theme: Theme;
  candidate: AnalysisCandidate | null;
  persona: PersonaKey;
  radiusKm: number;
  phase: AnalysisFlowPhase;
  pendingCard: Scorecard | null;
  analysisError: string | null;
  pdfStatus: PdfGenerationStatus;
  pdfError: string | null;
  onPersonaChange: (persona: PersonaKey) => void;
  onRadiusChange: (radiusKm: number) => void;
  onCancel: () => void;
  onAnalyse: () => void;
  onRetry: () => void;
  onGenerateReport: () => void;
  onViewMap: () => void;
};

function fitLabel(card: Scorecard, personaLabel: string): string {
  if (card.fit_score == null) return `Evidence is limited for this ${personaLabel} report`;
  if (card.fit_score >= 70) return `Strong match for ${personaLabel}`;
  if (card.fit_score >= 40) return `Mixed match for ${personaLabel}`;
  return `Weak match for ${personaLabel}`;
}

export function AnalysisSetupDialog({
  theme,
  candidate,
  persona,
  radiusKm,
  phase,
  pendingCard,
  analysisError,
  pdfStatus,
  pdfError,
  onPersonaChange,
  onRadiusChange,
  onCancel,
  onAnalyse,
  onRetry,
  onGenerateReport,
  onViewMap,
}: Props) {
  const dark = theme === "dark";
  const [step, setStep] = useState<1 | 2>(1);
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const dismissible = phase === "setup" || phase === "error";
  const dismissibleRef = useRef(dismissible);
  const onCancelRef = useRef(onCancel);
  dismissibleRef.current = dismissible;
  onCancelRef.current = onCancel;

  useEffect(() => {
    if (!candidate) return undefined;
    setStep(1);
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && dismissibleRef.current) {
        event.preventDefault();
        onCancelRef.current();
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
  }, [candidate]);

  useEffect(() => {
    if (!candidate) return;
    window.setTimeout(() => {
      panelRef.current
        ?.querySelector<HTMLElement>("[data-phase-autofocus], [data-autofocus]")
        ?.focus();
    }, 0);
  }, [candidate, phase, step]);

  if (!candidate) return null;
  const currentPersona = getPersona(persona);
  const place = candidate.label ?? `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`;
  const generatingPdf = pdfStatus === "generating";
  const headerTitle =
    phase === "analysing"
      ? "Analysing location"
      : phase === "ready"
        ? "Your analysis is ready"
        : phase === "error"
          ? "Analysis could not finish"
          : step === 1
            ? "Who is this report for?"
            : "Set the analysis area";

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-busy={phase === "analysing" || generatingPdf}
    >
      {dismissible ? (
        <button
          type="button"
          className="absolute inset-0 bg-slate-950/55 backdrop-blur-[2px]"
          aria-label="Cancel location analysis setup"
          onClick={onCancel}
        />
      ) : (
        <div className="absolute inset-0 bg-slate-950/55 backdrop-blur-[2px]" aria-hidden />
      )}
      <div
        ref={panelRef}
        className={clsx(
          "relative z-10 w-full max-w-lg overflow-hidden rounded-t-3xl border shadow-2xl sm:rounded-3xl",
          dark
            ? "border-gray-700 bg-gray-900 text-gray-100"
            : "border-slate-200 bg-white text-slate-900",
        )}
      >
        <div
          className={clsx(
            "border-b px-5 py-4",
            dark ? "border-gray-800" : "border-slate-200",
          )}
        >
          {phase === "setup" ? (
            <>
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
              <p
                className={clsx(
                  "text-[10px] font-semibold uppercase tracking-[0.14em]",
                  dark ? "text-sky-400" : "text-sky-700",
                )}
              >
                Step {step} of 2
              </p>
            </>
          ) : (
            <p
              className={clsx(
                "text-[10px] font-semibold uppercase tracking-[0.14em]",
                phase === "ready"
                  ? dark
                    ? "text-teal-300"
                    : "text-teal-700"
                  : phase === "error"
                    ? dark
                      ? "text-red-300"
                      : "text-red-700"
                    : dark
                      ? "text-sky-300"
                      : "text-sky-700",
              )}
            >
              {phase === "ready"
                ? "Analysis complete"
                : phase === "error"
                  ? "Action needed"
                  : "Background analysis"}
            </p>
          )}
          <h2 id={titleId} className="font-display text-xl font-semibold tracking-tight">
            {headerTitle}
          </h2>
          <p
            className={clsx(
              "mt-1 truncate text-xs",
              dark ? "text-gray-400" : "text-slate-500",
            )}
            title={place}
          >
            {place}
          </p>
        </div>

        <div className="space-y-4 px-5 py-5">
          {phase === "setup" && step === 1 && (
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
              <div
                className={clsx(
                  "rounded-xl border px-3 py-3 text-sm",
                  dark
                    ? "border-sky-900 bg-sky-950/40 text-sky-100"
                    : "border-sky-100 bg-sky-50 text-sky-950",
                )}
              >
                <p className="font-semibold">Report for {currentPersona.label}</p>
                <p className="mt-1 text-xs leading-relaxed opacity-80">{currentPersona.blurb}</p>
              </div>
            </>
          )}

          {phase === "setup" && step === 2 && (
            <div data-autofocus tabIndex={-1} className="outline-none">
              <RadiusControl
                theme={theme}
                value={radiusKm}
                onChange={onRadiusChange}
                idPrefix="analysis-setup"
              />
              <p
                className={clsx(
                  "mt-4 rounded-xl border px-3 py-3 text-xs leading-relaxed",
                  dark
                    ? "border-gray-800 bg-gray-950/60 text-gray-300"
                    : "border-slate-200 bg-slate-50 text-slate-600",
                )}
              >
                Nearby amenities, police locations, and market evidence will use this radius.
                Flood, land use, tenure, and other plot-specific facts remain tied to the selected
                point.
              </p>
            </div>
          )}

          {phase === "analysing" && (
            <div data-phase-autofocus tabIndex={-1} className="py-4 text-center outline-none">
              <span
                className={clsx(
                  "mx-auto block h-11 w-11 animate-spin rounded-full border-4",
                  dark
                    ? "border-gray-700 border-t-sky-400"
                    : "border-slate-200 border-t-sky-700",
                )}
                aria-hidden
              />
              <p className="mt-4 text-sm font-semibold">
                Building the {currentPersona.label} report for {radiusKm} km
              </p>
              <p className={clsx("mt-2 text-xs leading-5", dark ? "text-gray-400" : "text-slate-500")}>
                The location data is loading in the background. This window will remain open until
                the analysis is ready.
              </p>
            </div>
          )}

          {phase === "ready" && pendingCard && (
            <div data-phase-autofocus tabIndex={-1} className="space-y-3 outline-none">
              <div
                className={clsx(
                  "rounded-2xl border p-4",
                  dark
                    ? "border-teal-900 bg-teal-950/30"
                    : "border-teal-200 bg-teal-50",
                )}
              >
                <div className="flex items-end gap-3">
                  <span className="font-display text-4xl font-semibold leading-none tabular-nums">
                    {pendingCard.fit_score != null ? pendingCard.fit_score.toFixed(0) : "-"}
                  </span>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
                      Fit score
                    </p>
                    <p className="text-sm font-semibold">
                      {fitLabel(pendingCard, currentPersona.label)}
                    </p>
                  </div>
                </div>
                {pendingCard.summary && (
                  <p className="mt-3 text-xs leading-5 opacity-85">{pendingCard.summary}</p>
                )}
              </div>
              <div
                className={clsx(
                  "grid grid-cols-2 gap-2 rounded-xl border px-3 py-3 text-xs",
                  dark
                    ? "border-gray-800 bg-gray-950/50 text-gray-300"
                    : "border-slate-200 bg-slate-50 text-slate-600",
                )}
              >
                <div>
                  <p className="font-semibold text-inherit">Audience</p>
                  <p>{currentPersona.label}</p>
                </div>
                <div>
                  <p className="font-semibold text-inherit">Analysis area</p>
                  <p>{radiusKm} km radius</p>
                </div>
              </div>
              {pdfStatus === "downloaded" && (
                <p className="rounded-lg bg-teal-100 px-3 py-2 text-xs font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-300">
                  PDF downloaded. You can download it again or view the full result on the map.
                </p>
              )}
              {pdfError && (
                <p className="rounded-lg bg-red-100 px-3 py-2 text-xs text-red-800 dark:bg-red-950 dark:text-red-300">
                  PDF could not be generated: {pdfError}
                </p>
              )}
            </div>
          )}

          {phase === "error" && (
            <div data-phase-autofocus tabIndex={-1} className="outline-none">
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
                <p className="font-semibold">The location report was not changed.</p>
                <p className="mt-1 text-xs leading-5">
                  {analysisError ?? "The analysis service did not return a result. Please try again."}
                </p>
              </div>
            </div>
          )}
        </div>

        <div
          className={clsx(
            "flex items-center justify-between gap-3 border-t px-5 py-4",
            dark ? "border-gray-800" : "border-slate-200",
          )}
        >
          {phase === "setup" && (
            <>
              <button
                type="button"
                onClick={onCancel}
                className={clsx(
                  "rounded-xl px-3 py-2 text-sm font-semibold",
                  dark ? "text-gray-300 hover:bg-gray-800" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                Cancel
              </button>
              <div className="flex items-center gap-2">
                {step === 2 && (
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className={clsx(
                      "rounded-xl border px-4 py-2 text-sm font-semibold",
                      dark
                        ? "border-gray-700 hover:bg-gray-800"
                        : "border-slate-200 hover:bg-slate-50",
                    )}
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
            </>
          )}

          {phase === "analysing" && (
            <p className={clsx("w-full text-center text-xs", dark ? "text-gray-400" : "text-slate-500")}>
              Please keep this window open while the report is prepared.
            </p>
          )}

          {phase === "ready" && (
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={onGenerateReport}
                disabled={generatingPdf}
                className={clsx(
                  "rounded-xl border px-4 py-2.5 text-sm font-semibold",
                  dark
                    ? "border-gray-700 text-gray-100 hover:bg-gray-800"
                    : "border-slate-200 text-slate-700 hover:bg-slate-50",
                  generatingPdf && "cursor-wait opacity-60",
                )}
              >
                {generatingPdf
                  ? "Generating PDF..."
                  : pdfStatus === "downloaded"
                    ? "Download again"
                    : "Generate report"}
              </button>
              <button
                type="button"
                onClick={onViewMap}
                disabled={generatingPdf}
                className={clsx(
                  "rounded-xl bg-sky-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800",
                  generatingPdf && "cursor-wait opacity-60",
                )}
              >
                View on map
              </button>
            </div>
          )}

          {phase === "error" && (
            <>
              <button
                type="button"
                onClick={onCancel}
                className={clsx(
                  "rounded-xl px-3 py-2 text-sm font-semibold",
                  dark ? "text-gray-300 hover:bg-gray-800" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onRetry}
                className="rounded-xl bg-sky-700 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-800"
              >
                Retry analysis
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
