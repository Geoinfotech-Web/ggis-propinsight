import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { DOMAIN_ORDER, type Scorecard } from "../api";
import { buildNextSteps, reportCoverage } from "../lib/reportGuide";
import { getPersona, type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";

type GuideTab = "understand" | "next_steps";

type Props = {
  open: boolean;
  theme: Theme;
  card: Scorecard;
  persona: PersonaKey;
  placeLabel?: string | null;
  onClose: () => void;
};

const DOMAIN_LABELS: Record<string, string> = {
  flood: "Flood hazard",
  security: "Security",
  amenities: "Amenities",
  accessibility: "Accessibility",
  tenure: "Tenure",
  market: "Market",
  livability: "Habitability",
  feasibility: "Feasibility",
};

export function ReportGuideDialog({ open, theme, card, persona, placeLabel, onClose }: Props) {
  const dark = theme === "dark";
  const [tab, setTab] = useState<GuideTab>("understand");
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const tabsId = useId();
  const personaDef = getPersona(persona);
  const professional = persona === "investor" || persona === "developer";
  const coverage = useMemo(() => reportCoverage(card), [card]);
  const nextSteps = useMemo(() => buildNextSteps(card, persona), [card, persona]);
  const orderedDomains = card.domain_priority?.length
    ? card.domain_priority
    : [...DOMAIN_ORDER];

  useEffect(() => {
    if (!open) return undefined;
    setTab("understand");
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      );
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
      document.body.style.overflow = previousOverflow;
      restoreFocusRef.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  const fitLabel =
    card.fit_score == null
      ? "Not enough live evidence for a fit score"
      : card.fit_score >= 70
        ? `A strong match for ${personaDef.label}`
        : card.fit_score >= 40
          ? `A mixed match for ${personaDef.label}`
          : `A weak match for ${personaDef.label}`;

  const selectTab = (nextTab: GuideTab) => {
    setTab(nextTab);
    window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLElement>(`[data-guide-tab="${nextTab}"]`)?.focus();
    }, 0);
  };

  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home" || event.key === "ArrowLeft") selectTab("understand");
    else selectTab("next_steps");
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center sm:items-center sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-[2px]"
        aria-label="Close report guide"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        className={clsx(
          "glass-surface relative z-10 flex max-h-[min(92dvh,46rem)] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border sm:rounded-3xl",
          dark
            ? "border-gray-700 bg-gray-900 text-gray-100"
            : "border-slate-200 bg-white text-slate-900",
        )}
      >
        <header className={clsx("flex items-start justify-between gap-4 border-b px-5 py-4", dark ? "border-gray-800" : "border-slate-200")}>
          <div className="min-w-0">
            <p className={clsx("text-xs font-bold uppercase tracking-wider", dark ? "text-sky-300" : "text-sky-800")}>Decision support</p>
            <h2 id={titleId} className="font-display text-xl font-semibold tracking-tight">Report guide</h2>
            <p className={clsx("mt-1 truncate text-xs", dark ? "text-gray-300" : "text-slate-600")} title={placeLabel ?? undefined}>
              {placeLabel ?? `${personaDef.label} location report`}
            </p>
          </div>
          <button
            type="button"
            data-autofocus
            onClick={onClose}
            className={clsx(
              "rounded-lg border px-3 py-1.5 text-xs font-semibold",
              dark
                ? "border-gray-700 text-gray-200 hover:bg-gray-800"
                : "border-slate-200 text-slate-700 hover:bg-slate-50",
            )}
          >
            Close
          </button>
        </header>

        <div className={clsx("grid grid-cols-2 border-b p-1.5", dark ? "border-gray-800 bg-gray-950/50" : "border-slate-200 bg-slate-50")} role="tablist" aria-label="Report guide sections">
          {([
            ["understand", "Understand"],
            ["next_steps", `Next steps · ${nextSteps.length}`],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              id={`${tabsId}-${key}`}
              data-guide-tab={key}
              aria-selected={tab === key}
              aria-controls={`${tabsId}-${key}-panel`}
              tabIndex={tab === key ? 0 : -1}
              onClick={() => selectTab(key)}
              onKeyDown={onTabKeyDown}
              className={clsx(
                "rounded-lg px-3 py-2.5 text-sm font-semibold transition",
                tab === key
                  ? dark
                    ? "bg-gray-800 text-white shadow-sm"
                    : "bg-white text-sky-900 shadow-sm"
                  : dark
                    ? "text-gray-400 hover:text-gray-200"
                    : "text-slate-500 hover:text-slate-800",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {tab === "understand" ? (
            <div role="tabpanel" id={`${tabsId}-understand-panel`} aria-labelledby={`${tabsId}-understand`} className="space-y-4">
              <section className={clsx("rounded-xl border p-4", dark ? "border-sky-900 bg-sky-950/40" : "border-sky-200 bg-sky-50")}>
                <p className={clsx("text-xs font-bold uppercase tracking-wider", dark ? "text-sky-300" : "text-sky-800")}>Fit score</p>
                <div className="mt-1 flex items-end gap-3">
                  <span className="font-display text-4xl font-semibold leading-none tabular-nums">{card.fit_score != null ? card.fit_score.toFixed(0) : "—"}</span>
                  <span className="pb-0.5 text-sm font-semibold">{fitLabel}</span>
                </div>
                {card.summary && <p className={clsx("mt-3 text-sm leading-6", dark ? "text-gray-200" : "text-slate-700")}>{card.summary}</p>}
              </section>

              <section>
                <h3 className="text-sm font-bold">How the scores work</h3>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <div className={clsx("rounded-xl border p-3 text-sm leading-5", dark ? "border-gray-700 bg-gray-950/50 text-gray-200" : "border-slate-200 bg-slate-50 text-slate-700")}>
                    <p className="font-semibold">Suitability domains</p>
                    <p className="mt-1">Higher scores are better: 70–100 strong, 40–69 mixed, and below 40 weak.</p>
                  </div>
                  <div className={clsx("rounded-xl border p-3 text-sm leading-5", dark ? "border-red-900/70 bg-red-950/30 text-gray-200" : "border-red-200 bg-red-50 text-slate-700")}>
                    <p className="font-semibold">Flood is different</p>
                    <p className="mt-1">Flood uses a hazard index where lower is safer. Higher flood hazard reduces the overall fit score.</p>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-sm font-bold">Evidence coverage</h3>
                <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                  {([
                    ["Used in fit", coverage.included, "teal"],
                    ["Limited", coverage.limited, "amber"],
                    ["Unavailable", coverage.unavailable, "slate"],
                  ] as const).map(([label, value, tone]) => (
                    <div key={label} className={clsx("rounded-xl border px-2 py-3", dark ? "border-gray-700 bg-gray-950/50" : "border-slate-200 bg-slate-50")}>
                      <p className={clsx("text-2xl font-semibold tabular-nums", tone === "teal" ? "text-teal-500" : tone === "amber" ? "text-amber-500" : dark ? "text-gray-300" : "text-slate-500")}>{value}</p>
                      <p className={clsx("text-[11px] font-semibold", dark ? "text-gray-300" : "text-slate-600")}>{label}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {orderedDomains.map((domain) => {
                    const result = card.domains[domain];
                    if (!result) return null;
                    const state = result.score == null
                      ? "Unavailable"
                      : result.included_in_fit
                        ? "Used"
                        : "Context only";
                    return (
                      <span key={domain} className={clsx("rounded-full border px-2 py-1 text-[11px]", dark ? "border-gray-700 bg-gray-950/50 text-gray-300" : "border-slate-200 bg-white text-slate-600")}>
                        <strong>{DOMAIN_LABELS[domain] ?? domain}</strong> · {result.confidence} · {state}
                      </span>
                    );
                  })}
                </div>
              </section>

              <section className={clsx("rounded-xl border p-4 text-sm leading-6", dark ? "border-gray-700 bg-gray-950/50 text-gray-200" : "border-slate-200 bg-slate-50 text-slate-700")}>
                <h3 className="font-bold">What changes with the radius?</h3>
                {professional ? (
                  <>
                    <p className="mt-1">Amenities, police locations, market evidence, population, settlement trends, and verified projects use the selected {card.analysis_radius_m / 1000} km radius.</p>
                    <p className="mt-2">Land use, land cover, flood, tenure, road proximity, ward incidents, and engineering feasibility stay tied to the selected point. Terrain, drainage, heat, and green-cover context use a fixed 1 km neighbourhood.</p>
                  </>
                ) : (
                  <>
                    <p className="mt-1">The selected {card.analysis_radius_m / 1000} km radius controls how far the report looks for nearby services, police locations, and market evidence.</p>
                    <p className="mt-2">Property-specific checks such as flood, land-use and title context, and road proximity stay anchored to the selected place. The environmental picture covers the surrounding 1 km neighbourhood.</p>
                  </>
                )}
              </section>

              {professional && (
                <section className={clsx("rounded-xl border p-4 text-sm leading-6", dark ? "border-amber-800/70 bg-amber-950/30 text-gray-200" : "border-amber-200 bg-amber-50 text-slate-700")}>
                  <h3 className="font-bold">Professional interpretation</h3>
                  <p className="mt-1">Population and settlement projections indicate possible demand pressure, not observed migration. Modelled drainage is not surveyed drainage, utility proximity does not confirm capacity, and announced projects are not guaranteed delivery.</p>
                </section>
              )}
            </div>
          ) : (
            <div role="tabpanel" id={`${tabsId}-next_steps-panel`} aria-labelledby={`${tabsId}-next_steps`}>
              <div className={clsx("rounded-xl border px-4 py-3 text-sm leading-6", dark ? "border-gray-700 bg-gray-950/50 text-gray-200" : "border-slate-200 bg-slate-50 text-slate-700")}>
                These are prioritized checks for a {personaDef.label}. They are guidance, not proof that a property or project is suitable or approved.
              </div>
              <ol className="mt-4 space-y-3">
                {nextSteps.map((step, index) => (
                  <li key={step.id} className={clsx("flex gap-3 rounded-xl border p-4", dark ? "border-gray-700 bg-gray-950/40" : "border-slate-200 bg-white")}>
                    <span className={clsx("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold", step.urgency === "important" ? "bg-red-600 text-white" : step.urgency === "recommended" ? "bg-amber-500 text-slate-950" : "bg-sky-600 text-white")}>
                      {index + 1}
                    </span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-bold">{step.title}</h3>
                        <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide", step.urgency === "important" ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300" : step.urgency === "recommended" ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" : "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300")}>{step.urgency}</span>
                      </div>
                      <p className={clsx("mt-1 text-sm leading-6", dark ? "text-gray-300" : "text-slate-600")}>{step.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        <footer className={clsx("border-t px-5 py-3 text-xs leading-5", dark ? "border-gray-800 bg-gray-950/60 text-gray-400" : "border-slate-200 bg-slate-50 text-slate-500")}>
          Advisory location intelligence only. Confirm legal, planning, engineering, market, and site conditions with the relevant authorities and qualified professionals.
        </footer>
      </div>
    </div>,
    document.body,
  );
}
