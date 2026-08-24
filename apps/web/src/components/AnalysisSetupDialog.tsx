import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";
import type { Scorecard } from "../api";
import { getPersona, PERSONAS, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconChart, IconCheck, IconDownload, IconHome, IconKey, IconMap, IconPlan } from "./Icons";
import { RadiusControl } from "./RadiusControl";
import { ScoreRing } from "./ScoreRing";

export type AnalysisCandidate = { lon: number; lat: number; label?: string };
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
  radiusOnly?: boolean;
};

const PERSONA_GRID: PersonaKey[] = ["tenant", "investor", "developer", "home_buyer"];

function fitLabel(card: Scorecard, personaLabel: string): string {
  if (card.fit_score == null) return `Evidence is limited for ${personaLabel}`;
  if (card.fit_score >= 70) return `Strong match for ${personaLabel}`;
  if (card.fit_score >= 40) return `Mixed match for ${personaLabel}`;
  return `Weak match for ${personaLabel}`;
}

function fitColor(score: number | null): string {
  if (score == null) return "#94a3b8";
  if (score >= 70) return "#10b981";
  if (score >= 40) return "#f5b800";
  return "#ef4444";
}

function PersonaIcon({ persona }: { persona: PersonaKey }) {
  if (persona === "tenant") return <IconHome size={20} />;
  if (persona === "investor") return <IconChart size={20} />;
  if (persona === "developer") return <IconPlan size={20} />;
  return <IconKey size={20} />;
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
  radiusOnly = false,
}: Props) {
  const dark = theme === "dark";
  const [step, setStep] = useState<1 | 2>(radiusOnly ? 2 : 1);
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
    setStep(radiusOnly ? 2 : 1);
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && dismissibleRef.current) {
        event.preventDefault();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ));
      if (!focusable.length) return;
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
  }, [candidate, radiusOnly]);

  useEffect(() => {
    if (!candidate) return;
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("[data-phase-autofocus], [data-autofocus]")?.focus(), 0);
  }, [candidate, phase, step]);

  if (!candidate) return null;
  const currentPersona = getPersona(persona);
  const place = candidate.label ?? `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`;
  const generatingPdf = pdfStatus === "generating";
  const headerTitle = phase === "analysing"
    ? "Analysing location…"
    : phase === "ready"
      ? "Your analysis is ready"
      : phase === "error"
        ? "Analysis could not finish"
        : radiusOnly || step === 2
          ? "Adjust the analysis radius"
          : "Who is this report for?";

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center sm:p-5" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-busy={phase === "analysing" || generatingPdf}>
      {dismissible ? (
        <button type="button" className="absolute inset-0 bg-slate-950/10 backdrop-blur-[2px]" aria-label="Cancel location analysis setup" onClick={onCancel} />
      ) : (
        <div className="absolute inset-0 bg-slate-950/10 backdrop-blur-[2px]" aria-hidden />
      )}
      <div ref={panelRef} className={clsx(
        "glass-dialog relative z-10 flex max-h-[calc(100dvh-1rem)] w-full max-w-xl flex-col overflow-hidden rounded-t-3xl border sm:rounded-[1.75rem]",
        dark ? "border-gray-600/70 bg-gray-900/90 text-gray-100" : "border-white/60 bg-slate-700/75 text-white",
      )}>
        <div className={clsx("shrink-0 px-6 pb-3 pt-6 sm:px-8 sm:pt-8", phase === "analysing" && "hidden")}>
          {phase === "setup" && !radiusOnly && (
            <>
              <div className="mb-2 flex items-center gap-0" aria-label={`Step ${step} of 2`}>
                <span className="h-1 flex-1 rounded-l-full bg-[#1492ff]" />
                <span className={clsx("h-1 flex-1 rounded-r-full", step === 2 ? "bg-[#1492ff]" : "bg-white/90")} />
              </div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-[#1492ff]">Step {step} of 2</p>
            </>
          )}
          {phase === "ready" && <p className="truncate text-xs font-semibold tracking-wide text-white/80" title={place}>{place}</p>}
          {phase === "error" && <p className="text-[11px] font-bold uppercase tracking-wide text-red-300">Action needed</p>}
          <h2 id={titleId} className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">{headerTitle}</h2>
          {phase === "setup" && (
            <p className="mt-1 text-sm text-white/85">
              {step === 1 ? "Select the role that matches your analysis goals." : place}
            </p>
          )}
        </div>

        <div className="min-h-0 space-y-4 overflow-y-auto px-6 pb-5 pt-3 sm:px-8">
          {phase === "setup" && step === 1 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Report audience">
              {PERSONA_GRID.map((key, index) => {
                const item = PERSONAS.find((option) => option.key === key)!;
                const selected = key === persona;
                return (
                  <button key={key} type="button" role="radio" aria-checked={selected} data-autofocus={selected ? true : undefined} onClick={() => onPersonaChange(key)} className={clsx(
                "bento-card relative flex min-h-[5.75rem] items-center gap-4 rounded-2xl border-2 p-4 text-left outline-none transition focus-visible:ring-4 focus-visible:ring-sky-300/60",
                    index < 2 && "sm:col-span-2",
                    selected
                      ? dark ? "border-teal-400 bg-teal-950/70 text-teal-200" : "border-teal-400 bg-emerald-50 text-teal-600"
                      : dark ? "border-gray-700 bg-gray-950/90 text-gray-100 hover:border-gray-500" : "border-white/80 bg-white/95 text-slate-900 hover:border-sky-200",
                  )}>
                    <span className={clsx(
                      "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border",
                      selected ? "border-teal-300 text-teal-500" : dark ? "border-gray-700 text-gray-400" : "border-slate-200 text-slate-500",
                    )}><PersonaIcon persona={key} /></span>
                    <span className="min-w-0">
                      <span className="block text-lg font-bold">{item.label}</span>
                      <span className={clsx("mt-0.5 block text-sm leading-snug", selected ? "opacity-90" : dark ? "text-gray-400" : "text-slate-500")}>{item.blurb}</span>
                    </span>
                    {selected && <IconCheck size={20} className="absolute right-4 top-4" />}
                  </button>
                );
              })}
            </div>
          )}

          {phase === "setup" && step === 2 && (
            <div data-autofocus tabIndex={-1} className="outline-none">
              <RadiusControl theme={theme} value={radiusKm} onChange={onRadiusChange} idPrefix="analysis-setup" />
              <p className={clsx(
                "mt-4 rounded-2xl border px-5 py-4 text-sm leading-relaxed",
                dark ? "border-teal-800 bg-teal-950/60 text-teal-200" : "border-teal-300/80 bg-emerald-50 text-teal-600",
              )}>
                Nearby amenities, transit stops, and market context will use this radius. Flood risks, local zoning, and other plot-specific factors remain anchored to your precise center pin.
              </p>
            </div>
          )}

          {phase === "analysing" && (
            <div data-phase-autofocus tabIndex={-1} className="py-6 text-center outline-none">
              <span className="analysis-progress-ring mx-auto block h-32 w-32 rounded-full" aria-hidden />
              <p className="mt-6 text-2xl font-bold">Analysing location…</p>
              <p className="mx-auto mt-3 max-w-md text-base leading-6 text-white/85">The location data is loading in the background. This window will remain open until the analysis is ready.</p>
            </div>
          )}

          {phase === "ready" && pendingCard && (
            <div data-phase-autofocus tabIndex={-1} className="space-y-4 outline-none">
              {pdfStatus === "downloaded" && <p className="rounded-xl bg-teal-100 px-3 py-2 text-xs font-semibold text-teal-800">PDF downloaded. You can download it again or show the full result on the map.</p>}
              {pdfError && <p className="rounded-xl bg-red-100 px-3 py-2 text-xs text-red-800">PDF could not be generated: {pdfError}</p>}
            <div className={clsx("bento-card flex items-center gap-5 rounded-2xl border p-5", dark ? "border-gray-700 bg-gray-950/90" : "border-white/80 bg-white/95 text-slate-900")}>
                <ScoreRing score={pendingCard.fit_score ?? null} size="lg" color={fitColor(pendingCard.fit_score ?? null)} label={`Fit for ${currentPersona.label}`} />
                <div className="min-w-0">
                  <p className="font-display text-xl font-bold">{fitLabel(pendingCard, currentPersona.label)}</p>
                  <p className={clsx("mt-1 text-sm leading-5", dark ? "text-gray-400" : "text-slate-500")}>
                    {(pendingCard.summary || "Review the supporting evidence before making a property decision.")
                      .replace(/\s*—\s*/g, " - ")
                      .replace(/\s*--\s*/g, " - ")}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[["Audience", currentPersona.label], ["Analysis area", `${radiusKm} km radius`]].map(([label, value]) => (
                <div key={label} className={clsx("bento-card rounded-2xl border p-5", dark ? "border-gray-700 bg-gray-950/90" : "border-white/80 bg-white/95 text-slate-900")}>
                    <p className={clsx("text-[11px] font-semibold uppercase tracking-wide", dark ? "text-gray-500" : "text-slate-400")}>{label}</p>
                    <p className="mt-1 text-lg font-bold">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {phase === "error" && (
            <div data-phase-autofocus tabIndex={-1} className="rounded-2xl border border-red-300 bg-red-50 px-5 py-4 text-sm text-red-800 outline-none">
              <p className="font-bold">The location report was not changed.</p>
              <p className="mt-1 text-xs leading-5">{analysisError ?? "The analysis service did not return a result. Please try again."}</p>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between gap-3 px-6 pb-6 pt-2 sm:px-8">
          {phase === "setup" && (
            <>
              <button type="button" onClick={onCancel} className="rounded-xl px-2 py-2 text-sm font-semibold text-white hover:bg-white/10">Cancel</button>
              <div className="flex items-center gap-3">
                {step === 2 && !radiusOnly && <button type="button" onClick={() => setStep(1)} className={clsx("rounded-xl border px-5 py-3 text-sm font-semibold", dark ? "border-gray-700 bg-gray-950/80" : "border-white/80 bg-white/95 text-slate-600")}>Back</button>}
                {step === 1 ? (
                  <button type="button" onClick={() => setStep(2)} className="rounded-xl bg-[#087df1] px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-sky-600">Continue</button>
                ) : (
                  <button type="button" onClick={onAnalyse} className="rounded-xl bg-[#087df1] px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-sky-600">Analyse Location</button>
                )}
              </div>
            </>
          )}
          {phase === "analysing" && <p className="w-full border-t border-white/60 pt-5 text-center text-xs font-semibold uppercase text-white/75">Please keep this window open while the report is prepared</p>}
          {phase === "ready" && (
            <div className="grid w-full grid-cols-2 gap-3">
              <button type="button" onClick={onViewMap} disabled={generatingPdf} className={clsx(
                "inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold",
                dark ? "border-gray-700 bg-gray-950/80 text-gray-100 hover:bg-gray-800" : "border-white/80 bg-white/95 text-slate-700 hover:bg-slate-50",
                generatingPdf && "cursor-wait opacity-60",
              )}><IconMap size={16} />Show on map</button>
              <button type="button" onClick={onGenerateReport} disabled={generatingPdf} className={clsx(
                "inline-flex items-center justify-center gap-2 rounded-xl bg-[#087df1] px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-sky-600",
                generatingPdf && "cursor-wait opacity-60",
              )}><IconDownload size={16} />{generatingPdf ? "Generating…" : pdfStatus === "downloaded" ? "Download again" : "Generate report"}</button>
            </div>
          )}
          {phase === "error" && (
            <>
              <button type="button" onClick={onCancel} className="rounded-xl px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">Cancel</button>
              <button type="button" onClick={onRetry} className="rounded-xl bg-[#087df1] px-5 py-3 text-sm font-semibold text-white hover:bg-sky-600">Try again</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
