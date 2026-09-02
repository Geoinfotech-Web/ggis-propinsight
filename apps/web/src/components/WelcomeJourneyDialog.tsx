import { useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";
import type { StateOption } from "../api";
import { getCurrentPosition } from "../lib/geocode";
import type { PersonaKey } from "../lib/personas";
import brandLogo from "../assets/propinsight-logo.png";
import {
  IconChart,
  IconHome,
  IconKey,
  IconLocate,
  IconMap,
  IconPlan,
} from "./Icons";
import { SearchBar } from "./SearchBar";

export type WelcomeLocation = {
  lon: number;
  lat: number;
  label?: string;
};

type WelcomeStep = "state" | "welcome" | "interest" | "location" | "confirm";
type InterestKey = "rent" | "buy" | "invest" | "develop";

type Props = {
  open: boolean;
  candidate: WelcomeLocation | null;
  states: StateOption[];
  selectedStateCode: string;
  statesLoading?: boolean;
  onStateChange: (stateCode: string) => void;
  onCandidateChange: (candidate: WelcomeLocation | null) => void;
  onConfirm: (candidate: WelcomeLocation, suggestedPersona: PersonaKey) => void;
};

const INTERESTS: Array<{
  key: InterestKey;
  title: string;
  description: string;
  persona: PersonaKey;
  icon: typeof IconHome;
}> = [
  {
    key: "rent",
    title: "I want to rent a home",
    description: "I care most about everyday convenience, safety, access and rent conditions.",
    persona: "tenant",
    icon: IconHome,
  },
  {
    key: "buy",
    title: "I want to buy a home",
    description: "I need to understand long-term suitability, title context, flood and services.",
    persona: "home_buyer",
    icon: IconKey,
  },
  {
    key: "invest",
    title: "I want to invest in property",
    description: "I want to compare return potential, demand, risks and future growth signals.",
    persona: "investor",
    icon: IconChart,
  },
  {
    key: "develop",
    title: "I want to develop land or an estate",
    description: "I need terrain, drainage, servicing, planning and development evidence.",
    persona: "developer",
    icon: IconPlan,
  },
];

const STEP_NUMBER: Record<WelcomeStep, number> = {
  state: 1,
  welcome: 2,
  interest: 3,
  location: 4,
  confirm: 5,
};

function parseCoordinate(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : null;
}

export function WelcomeJourneyDialog({
  open,
  candidate,
  states,
  selectedStateCode,
  statesLoading = false,
  onStateChange,
  onCandidateChange,
  onConfirm,
}: Props) {
  const [step, setStep] = useState<WelcomeStep>("state");
  const [interest, setInterest] = useState<InterestKey>("buy");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [coordinateError, setCoordinateError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    setStep("state");
    setInterest("buy");
    setLatitude("");
    setLongitude("");
    setCoordinateError(null);
    setLocationError(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    window.setTimeout(
      () => panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus(),
      0,
    );
  }, [open, step]);

  useEffect(() => {
    if (!open || step === "confirm") return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
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
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, step]);

  if (!open) return null;

  const selectedState =
    states.find((state) => state.code === selectedStateCode) ??
    states.find((state) => state.code === "FC") ??
    states[0];
  const selectedInterest = INTERESTS.find((item) => item.key === interest) ?? INTERESTS[1];
  const stepNumber = STEP_NUMBER[step];
  const selectedBbox = selectedState?.bbox;
  const isInsideSelectedState = (lon: number, lat: number) => {
    if (!selectedBbox) return true;
    return lon >= selectedBbox[0] && lon <= selectedBbox[2] && lat >= selectedBbox[1] && lat <= selectedBbox[3];
  };
  const previewLocation = (next: WelcomeLocation) => {
    if (!isInsideSelectedState(next.lon, next.lat)) {
      setLocationError(`That point is outside ${selectedState?.name ?? "the selected state"}. Choose the matching state or adjust the coordinates.`);
      return;
    }
    onCandidateChange(next);
    setLatitude(next.lat.toFixed(6));
    setLongitude(next.lon.toFixed(6));
    setCoordinateError(null);
    setLocationError(null);
    setStep("confirm");
  };
  const previewCoordinates = () => {
    const lat = parseCoordinate(latitude);
    const lon = parseCoordinate(longitude);
    if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setCoordinateError("Enter a valid latitude from −90 to 90 and longitude from −180 to 180.");
      return;
    }
    previewLocation({ lon, lat, label: `Coordinates ${lat.toFixed(5)}, ${lon.toFixed(5)}` });
  };
  const useMyLocation = async () => {
    setLocating(true);
    setLocationError(null);
    try {
      const position = await getCurrentPosition();
      previewLocation({
        lon: position.coords.longitude,
        lat: position.coords.latitude,
        label: "Current location",
      });
    } catch (error) {
      setLocationError((error as Error).message || "Your current location could not be read.");
    } finally {
      setLocating(false);
    }
  };

  if (step === "confirm") {
    return (
      <div className="pointer-events-none fixed inset-0 z-[68]" aria-live="polite">
        <section
          ref={panelRef}
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          className="glass-dialog pointer-events-auto absolute inset-x-3 bottom-4 rounded-[1.5rem] border border-white/30 p-5 text-white shadow-2xl sm:inset-x-auto sm:bottom-auto sm:right-5 sm:top-24 sm:w-[23rem]"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sky-600">
              Step 5 of 5 · Confirm location
            </p>
            <span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-800">
              Pin adjustable
            </span>
          </div>
          <h2 id={titleId} className="mt-2 text-xl font-bold tracking-tight">
            Is this the right location?
          </h2>
          <p className="mt-1 text-sm leading-5 text-white/75">
            Drag the amber pin on the map to fine-tune the exact point, then confirm it.
          </p>
          <div className="mt-4 rounded-[0.9rem] border border-slate-200 bg-white p-3 text-slate-900 shadow-sm">
            <p className="truncate text-sm font-bold">
              {candidate?.label ?? "Selected coordinates"}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-500">
              {candidate ? `${candidate.lat.toFixed(6)}, ${candidate.lon.toFixed(6)}` : "Select a location to continue"}
            </p>
          </div>
          {locationError && <p className="mt-2 text-xs font-semibold text-red-200">{locationError}</p>}
          <div className="mt-4 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => {
                onCandidateChange(null);
                setStep("location");
              }}
              className="rounded-xl px-3 py-2 text-sm font-semibold text-white hover:bg-white/10"
            >
              Back
            </button>
            <button
              type="button"
              data-autofocus
              disabled={!candidate}
              onClick={() => {
                if (!candidate) return;
                if (!isInsideSelectedState(candidate.lon, candidate.lat)) {
                  setLocationError(`That point is outside ${selectedState?.name ?? "the selected state"}. Adjust the pin or choose the matching state.`);
                  return;
                }
                onConfirm(candidate, selectedInterest.persona);
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-[#087df1] px-5 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <IconMap size={16} />
              Confirm location
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-[68] flex items-end justify-center p-0 sm:items-center sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="absolute inset-0 bg-slate-950/16 backdrop-blur-md" aria-hidden />
      <section
        ref={panelRef}
        className="glass-dialog relative z-10 flex max-h-[calc(100dvh-1rem)] w-full flex-col overflow-hidden rounded-t-[1.5rem] border border-white/30 text-white shadow-2xl sm:w-[min(38rem,calc(100vw-2rem))] sm:rounded-[1.5rem]"
      >
        <div className="px-6 pb-3 pt-6 sm:px-8 sm:pt-8">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center">
              <img
                src={brandLogo}
                alt=""
                className="h-12 w-12 object-contain"
                draggable={false}
              />
            </span>
            <div>
              <p className="font-bold tracking-tight">PropInsight</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-white/65">
                Nigeria location intelligence
              </p>
            </div>
          </div>
          <div className="mt-6 grid grid-cols-5 gap-2" aria-label={`Step ${stepNumber} of 5`}>
            {[1, 2, 3, 4, 5].map((number) => (
              <span
                key={number}
                className={clsx(
                  "h-1.5 rounded-full",
                  number <= stepNumber ? "bg-[#1492ff]" : "bg-white/80",
                )}
              />
            ))}
          </div>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.16em] text-sky-600">
            Step {stepNumber} of 5
          </p>
        </div>

        <div className="min-h-0 overflow-y-auto px-6 pb-5 sm:px-8">
          {step === "state" && (
            <div>
              <h1 id={titleId} className="text-2xl font-bold tracking-tight sm:text-3xl">Select a Nigerian state.</h1>
              <p className="mt-2 text-sm leading-5 text-white/75">
                FCT is ready today. Other states are available for setup and become score-ready as admin layers are published.
              </p>
              <div className="mt-5 max-h-[42vh] overflow-y-auto pr-1">
                <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Nigerian state">
                  {statesLoading && (
                    <div className="col-span-full rounded-2xl border border-white/30 bg-white/12 p-4 text-sm text-white/80">
                      Loading state readiness…
                    </div>
                  )}
                  {!statesLoading && states.map((state) => {
                    const selected = state.code === selectedStateCode;
                    const readyTone =
                      state.readiness === "ready"
                        ? "bg-emerald-100 text-emerald-700"
                        : state.readiness === "partial"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-100 text-slate-600";
                    return (
                      <button
                        key={state.code}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        data-autofocus={selected ? true : undefined}
                        onClick={() => onStateChange(state.code)}
                        className={clsx(
                          "rounded-2xl border bg-white p-3 text-left text-slate-900 shadow-sm outline-none transition focus-visible:ring-4 focus-visible:ring-sky-300/60",
                          selected ? "border-emerald-500 bg-emerald-50 shadow-[0_0_0_2px_rgba(16,185,129,0.2)]" : "border-slate-200 hover:border-sky-200",
                        )}
                      >
                        <span className="flex items-start justify-between gap-3">
                          <span>
                            <span className="block text-sm font-bold">{state.name}</span>
                            <span className="mt-1 block text-[11px] text-slate-500">
                              {state.capital ? `Capital: ${state.capital}` : state.code}
                            </span>
                          </span>
                          <span className={clsx("shrink-0 rounded-full px-2 py-1 text-[10px] font-bold", readyTone)}>
                            {state.readiness_label}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {step === "welcome" && (
            <div>
              <h1 id={titleId} className="max-w-lg text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                Make a more informed property decision.
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-6 text-white/80 sm:text-base">
                PropInsight brings planning context, flood exposure, amenities, access, market signals and site evidence together for Nigerian locations as state layers come online.
              </p>
              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {[
                  ["Choose your goal", "Tell us what kind of property decision you are making."],
                  ["Confirm a location", "Search, enter coordinates or use your current position."],
                  ["Receive your report", "Set the audience and radius, then analyse the location."],
                ].map(([title, description], index) => (
                  <div key={title} className="rounded-[0.9rem] border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
                    <span className="text-xs font-bold text-sky-600">0{index + 1}</span>
                    <p className="mt-2 text-sm font-bold">{title}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-[11px] leading-5 text-white/60">
                PropInsight provides advisory evidence and does not replace legal, planning, engineering or valuation advice.
              </p>
            </div>
          )}

          {step === "interest" && (
            <div>
              <h1 id={titleId} className="text-2xl font-bold tracking-tight sm:text-3xl">What are you hoping to do at this location?</h1>
              <p className="mt-2 text-sm leading-5 text-white/75">
                Choose the answer that best matches your goal. We will use it to suggest a report persona later, but you remain in control.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Property interest">
                {INTERESTS.map((item) => {
                  const selected = item.key === interest;
                  const InterestIcon = item.icon;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      data-autofocus={selected ? true : undefined}
                      onClick={() => setInterest(item.key)}
                      className={clsx(
                        "relative flex items-start gap-3 rounded-[0.9rem] border bg-white p-4 text-left text-slate-900 shadow-sm outline-none transition focus-visible:ring-4 focus-visible:ring-sky-300/60",
                        selected
                          ? "border-emerald-500 bg-emerald-50 shadow-[0_0_0_2px_rgba(16,185,129,0.2)]"
                          : "border-slate-200 hover:border-sky-200",
                      )}
                    >
                      <span className={clsx("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border", selected ? "border-emerald-300 bg-emerald-50 text-emerald-600" : "border-slate-200 bg-white text-slate-500") }>
                        <InterestIcon size={18} />
                      </span>
                      <span>
                        <span className={clsx("block text-sm font-bold", selected ? "text-emerald-700" : "text-slate-900")}>{item.title}</span>
                        <span className={clsx("mt-1 block text-xs leading-5", selected ? "text-emerald-700/80" : "text-slate-500")}>{item.description}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {step === "location" && (
            <div>
              <h1 id={titleId} className="text-2xl font-bold tracking-tight sm:text-3xl">Where should we analyse?</h1>
              <p className="mt-2 text-sm text-white/75">
                Search for an address or place, enter coordinates, or use your current location.
              </p>
              <div className="mt-5">
                <label className="mb-2 block text-xs font-bold uppercase tracking-wide">Search an address or place</label>
                <SearchBar
                  theme="light"
                  size="lg"
                  viewbox={selectedBbox}
                  placeholder="Search an address, district or landmark…"
                  onResult={(hit) => previewLocation({ lon: hit.lon, lat: hit.lat, label: hit.label })}
                />
              </div>
              <div className="my-5 flex items-center gap-3">
                <span className="h-px flex-1 bg-white/35" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-white/65">or use coordinates</span>
                <span className="h-px flex-1 bg-white/35" />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold">
                  Latitude
                  <input
                    type="number"
                    inputMode="decimal"
                    value={latitude}
                    onChange={(event) => setLatitude(event.target.value)}
                    placeholder="9.0579"
                    min={-90}
                    max={90}
                    step="any"
                    className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 font-mono text-sm text-slate-900 outline-none focus:border-sky-500"
                  />
                </label>
                <label className="text-xs font-semibold">
                  Longitude
                  <input
                    type="number"
                    inputMode="decimal"
                    value={longitude}
                    onChange={(event) => setLongitude(event.target.value)}
                    placeholder="7.4913"
                    min={-180}
                    max={180}
                    step="any"
                    className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 font-mono text-sm text-slate-900 outline-none focus:border-sky-500"
                  />
                </label>
              </div>
              {coordinateError && <p className="mt-2 text-xs text-red-500">{coordinateError}</p>}
              {locationError && <p className="mt-2 text-xs text-red-500">{locationError}</p>}
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={previewCoordinates}
                  className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-semibold text-sky-800 hover:bg-sky-100"
                >
                  Show coordinates on map
                </button>
                <button
                  type="button"
                  onClick={() => void useMyLocation()}
                  disabled={locating}
                  className={clsx("inline-flex items-center justify-center gap-2 rounded-xl border border-white/80 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50", locating && "cursor-wait opacity-60")}
                >
                  <IconLocate size={17} />
                  {locating ? "Finding location…" : "Use my current location"}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-white/30 px-6 py-5 sm:px-8">
          {step === "state" ? <span /> : (
            <button
              type="button"
              onClick={() => setStep(step === "welcome" ? "state" : step === "interest" ? "welcome" : "interest")}
              className="rounded-xl px-3 py-2 text-sm font-semibold text-white hover:bg-white/10"
            >
              Back
            </button>
          )}
          {step !== "location" && (
            <button
              type="button"
              data-autofocus={step === "state" ? true : undefined}
              onClick={() => setStep(step === "state" ? "welcome" : step === "welcome" ? "interest" : "location")}
              className="rounded-xl bg-[#087df1] px-5 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-sky-600"
            >
              {step === "state" ? "Continue" : step === "welcome" ? "Get started" : "Continue"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
