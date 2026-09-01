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
  theme: _theme,
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
  const [step, setStep] = useState<1 | 2>(radiusOnly ? 2 : 1);
  const [analysisProgress, setAnalysisProgress] = useState(12);
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

  useEffect(() => {
    if (phase !== "analysing") {
      setAnalysisProgress(12);
      return undefined;
    }
    setAnalysisProgress(12);
    const interval = window.setInterval(() => {
      setAnalysisProgress((value) => {
        if (value >= 92) return value;
        if (value >= 80) return value + 1;
        if (value >= 60) return value + 2;
        return value + 3;
      });
    }, 650);
    return () => window.clearInterval(interval);
  }, [phase]);

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
        <button type="button" className="absolute inset-0 bg-slate-950/16 backdrop-blur-md" aria-label="Cancel location analysis setup" onClick={onCancel} />
      ) : (
        <div className="absolute inset-0 bg-slate-950/16 backdrop-blur-md" aria-hidden />
      )}
      <div
        ref={panelRef}
        className="glass-dialog relative z-10 flex max-h-[calc(100dvh-1rem)] w-[min(26rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-t-[1.5rem] border border-white/30 text-white sm:w-[26rem] sm:rounded-[1.5rem]"
      >
        <div className={clsx("shrink-0 px-5 pb-2 pt-5", phase === "analysing" && "hidden")}>
          {phase === "setup" && !radiusOnly && (
            <>
              <div className="mb-2.5 flex items-center gap-0" aria-label={`Step ${step} of 2`}>
                <span className="h-1 flex-1 rounded-l-full bg-[#1492ff]" />
                <span className={clsx("h-1 flex-1 rounded-r-full", step === 2 ? "bg-[#1492ff]" : "bg-white/90")} />
              </div>
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#1492ff]">Step {step} of 2</p>
            </>
          )}
          {phase === "ready" && <p className="truncate text-xs font-semibold tracking-wide text-white/80" title={place}>{place}</p>}
          {phase === "error" && <p className="text-[11px] font-bold uppercase tracking-wide text-red-300">Action needed</p>}
          <h2 id={titleId} className="mt-2 text-[1.15rem] font-bold tracking-tight text-white sm:text-[1.2rem]">
            {headerTitle}
          </h2>
          {phase === "setup" && (
            <p className="mt-1 text-[10px] leading-relaxed text-white/75">
              {step === 1 ? "Select the role that matches your analysis goals." : place}
            </p>
          )}
        </div>

        <div className="min-h-0 space-y-3 overflow-y-auto px-5 pb-5 pt-3">
          {phase === "setup" && step === 1 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Report audience">
              {PERSONA_GRID.map((key, index) => {
                const item = PERSONAS.find((option) => option.key === key)!;
                const selected = key === persona;
                return (
                  <button
                    key={key}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    data-autofocus={selected ? true : undefined}
                    onClick={() => onPersonaChange(key)}
                    className={clsx(
                      "relative flex min-h-[3.1rem] items-center gap-3 rounded-[0.9rem] border bg-white px-3 py-2.5 text-left text-slate-900 shadow-sm outline-none transition focus-visible:ring-4 focus-visible:ring-sky-300/60",
                      index < 2 && "sm:col-span-2",
                      selected
                        ? "border-emerald-500 bg-emerald-50 shadow-[0_0_0_2px_rgba(16,185,129,0.2)]"
                        : "border-slate-200 hover:border-sky-200",
                    )}
                  >
                    <span
                      className={clsx(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border bg-white",
                        selected ? "border-emerald-300 bg-emerald-50 text-emerald-600" : "border-slate-200 text-slate-500",
                      )}
                    >
                      <PersonaIcon persona={key} />
                    </span>
                    <span className="min-w-0">
                      <span className={clsx("block text-sm font-bold", selected ? "text-emerald-700" : "text-slate-900")}>{item.label}</span>
                      <span className={clsx("mt-0.5 block text-[10px] leading-snug", selected ? "text-emerald-700/80" : "text-slate-500")}>{item.blurb}</span>
                    </span>
                    {selected && <IconCheck size={14} className="absolute right-3 top-3 text-emerald-600" />}
                  </button>
                );
              })}
            </div>
          )}

          {phase === "setup" && step === 2 && (
            <div data-autofocus tabIndex={-1} className="outline-none">
              <RadiusControl theme="light" value={radiusKm} onChange={onRadiusChange} idPrefix="analysis-setup" />
              <p className="mt-3 rounded-2xl border border-emerald-100 bg-emerald-50/95 px-4 py-3 text-[10px] leading-relaxed text-teal-700">
                Nearby amenities, transit stops, and market context will use this radius. Flood risks, local zoning, and other plot-specific factors remain anchored to your precise center pin.
              </p>
            </div>
          )}

          {phase === "analysing" && (
            <div data-phase-autofocus tabIndex={-1} className="py-5 text-center outline-none">
              <span
                className="analysis-progress-ring mx-auto flex h-24 w-24 items-center justify-center rounded-full"
                style={{ background: `conic-gradient(from 0deg, #16e0ae 0deg ${analysisProgress * 3.6}deg, rgba(255, 255, 255, 0.35) ${analysisProgress * 3.6}deg 360deg)` }}
                aria-hidden
              >
                <span className="flex h-[4.3rem] w-[4.3rem] items-center justify-center rounded-full bg-slate-500/75 text-[11px] font-bold text-emerald-300">
                  {analysisProgress}%
                </span>
              </span>
              <p className="mt-5 text-[1.05rem] font-bold text-white">Analysing location…</p>
              <p className="mx-auto mt-2 max-w-[15rem] text-[10px] leading-5 text-white/80">
                The location data is loading in the background. This window will remain open until the analysis is ready.
              </p>
            </div>
          )}

          {phase === "ready" && pendingCard && (
            <div data-phase-autofocus tabIndex={-1} className="space-y-4 outline-none">
              {pdfStatus === "downloaded" && (
                <p className="rounded-xl bg-teal-100 px-3 py-2 text-xs font-semibold text-teal-800">
                  PDF downloaded. You can download it again or show the full result on the map.
                </p>
              )}
              {pdfError && (
                <p className="rounded-xl bg-red-100 px-3 py-2 text-xs text-red-800">
                  PDF could not be generated: {pdfError}
                </p>
              )}
              <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
                <ScoreRing
                  score={pendingCard.fit_score ?? null}
                  size="lg"
                  color={fitColor(pendingCard.fit_score ?? null)}
                  label={`Fit for ${currentPersona.label}`}
                />
                <div className="min-w-0">
                  <p className="text-base font-bold text-slate-900">
                    {fitLabel(pendingCard, currentPersona.label)}
                  </p>
                  <p className="mt-1 text-[10px] leading-4 text-slate-500">
                    {(pendingCard.summary || "Review the supporting evidence before making a property decision.")
                      .replace(/\s*—\s*/g, " - ")
                      .replace(/\s*--\s*/g, " - ")}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                {[["Audience", currentPersona.label], ["Analysis area", `${radiusKm} km radius`]].map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-slate-200 bg-white p-3 text-slate-900 shadow-sm">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
                    <p className="mt-1 text-base font-bold">{value}</p>
                  </div>
                ))}
              </div>
              {pendingCard.domains.flood && (
                <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
                  <ScoreRing
                    score={pendingCard.domains.flood.score ?? null}
                    size="md"
                    color={
                      (pendingCard.domains.flood.rating ?? "").toLowerCase().includes("high")
                        ? "#dc2626"
                        : (pendingCard.domains.flood.rating ?? "").toLowerCase().includes("moderate")
                          ? "#ca8a04"
                          : "#0d9488"
                    }
                    label="Flood hazard"
                  />
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Flood hazard</p>
                    <p className="text-base font-bold text-slate-900">
                      {pendingCard.domains.flood.rating ?? "Risk unavailable"}
                    </p>
                    {pendingCard.domains.flood.score != null && (
                      <p className="mt-1 text-[10px] text-slate-500">
                        PropInsight hazard index · {Math.round(pendingCard.domains.flood.score)} / 100
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {phase === "error" && (
            <div data-phase-autofocus tabIndex={-1} className="rounded-2xl border border-red-300 bg-red-50 px-5 py-4 text-sm text-red-800 outline-none">
              <p className="font-bold">The location report was not changed.</p>
              <p className="mt-1 text-xs leading-5">
                {analysisError ?? "The analysis service did not return a result. Please try again."}
              </p>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between gap-3 px-5 pb-5 pt-1">
          {phase === "setup" && (
            <>
              <button type="button" onClick={onCancel} className="rounded-xl px-0 py-2 text-sm font-semibold text-white hover:text-white/85">
                Cancel
              </button>
              <div className="flex items-center gap-3">
                {step === 2 && !radiusOnly && (
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="rounded-xl border border-white/80 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Back
                  </button>
                )}
                {step === 1 ? (
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="rounded-xl bg-[#087df1] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-600"
                  >
                    Continue
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={onAnalyse}
                    className="rounded-xl bg-[#087df1] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-600"
                  >
                    Analyse Location
                  </button>
                )}
              </div>
            </>
          )}
          {phase === "analysing" && (
            <p className="w-full border-t border-white/45 pt-5 text-center text-[9px] font-semibold uppercase tracking-wide text-white/70">
              Please keep this window open while the report is prepared
            </p>
          )}
          {phase === "ready" && (
            <div className="grid w-full grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={onViewMap}
                disabled={generatingPdf}
                className={clsx(
                  "inline-flex items-center justify-center gap-2 rounded-xl border border-white/80 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50",
                  generatingPdf && "cursor-wait opacity-60",
                )}
              >
                <IconMap size={16} />
                Show on map
              </button>
              <button
                type="button"
                onClick={onGenerateReport}
                disabled={generatingPdf}
                className={clsx(
                  "inline-flex items-center justify-center gap-2 rounded-xl bg-[#087df1] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-600",
                  generatingPdf && "cursor-wait opacity-60",
                )}
              >
                <IconDownload size={16} />
                {generatingPdf ? "Preparing…" : pdfStatus === "downloaded" ? "Download again" : "Download report"}
              </button>
            </div>
          )}
          {phase === "error" && (
            <>
              <button
                type="button"
                onClick={onCancel}
                className="rounded-xl px-3 py-2 text-sm font-semibold text-white hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onRetry}
                className="rounded-xl bg-[#087df1] px-5 py-3 text-sm font-semibold text-white hover:bg-sky-600"
              >
                Try again
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
