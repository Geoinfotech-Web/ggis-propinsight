import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import type { Scorecard } from "../api";
import type {
  Professional3DFeature,
  Professional3DMode,
  Professional3DScene,
} from "../lib/cesiumScene";
import type { PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconHome, IconX } from "./Icons";

type Props = {
  open: boolean;
  theme: Theme;
  card: Scorecard;
  persona: PersonaKey;
  lon: number;
  lat: number;
  radiusKm: number;
  placeLabel: string;
  onClose: () => void;
};

type LoadState = "loading" | "ready" | "error";

export function Professional3DDialog({
  open,
  theme,
  card,
  persona,
  lon,
  lat,
  radiusKm,
  placeLabel,
  onClose,
}: Props) {
  const dark = theme === "dark";
  const titleId = useId();
  const mapRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<Professional3DScene | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [landCoverVisible, setLandCoverVisible] = useState(true);
  const [landUseVisible, setLandUseVisible] = useState(true);
  const [evidenceVisible, setEvidenceVisible] = useState(true);
  const [buildingsVisible, setBuildingsVisible] = useState(true);
  const [vegetationVisible, setVegetationVisible] = useState(true);
  const [mode, setMode] = useState<Professional3DMode>("analytical");
  const [modeLoading, setModeLoading] = useState(false);
  const [modeWarning, setModeWarning] = useState<string | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<Professional3DFeature | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKeyDown);
      restoreFocusRef.current?.focus();
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !mapRef.current) return;
    let cancelled = false;
    const controller = new AbortController();
    setLoadState("loading");
    setError(null);
    setMode("analytical");
    setModeWarning(null);
    setSelectedFeature(null);

    void import("../lib/cesiumScene")
      .then(({ createProfessional3DScene }) => createProfessional3DScene(mapRef.current!, {
        card,
        lon,
        lat,
        radiusKm,
        placeLabel,
        signal: controller.signal,
        onFeatureSelect: setSelectedFeature,
      }))
      .then((scene) => {
        if (cancelled) {
          scene.destroy();
          return;
        }
        sceneRef.current = scene;
        scene.setLandCoverVisible(landCoverVisible);
        scene.setLandUseVisible(landUseVisible);
        scene.setEvidenceVisible(evidenceVisible);
        scene.setBuildingsVisible(buildingsVisible);
        scene.setVegetationVisible(vegetationVisible);
        setLoadState("ready");
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "The professional 3D view could not start.");
        setLoadState("error");
      });

    return () => {
      cancelled = true;
      controller.abort();
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
  }, [open, retryKey, card, lon, lat, radiusKm, placeLabel]);

  if (!open) return null;
  const scene = sceneRef.current;
  const professionalLabel = persona === "developer" ? "Developer" : "Investor";

  const toggle = (
    value: boolean,
    setValue: (value: boolean) => void,
    apply: (scene: Professional3DScene, value: boolean) => void,
  ) => {
    const next = !value;
    setValue(next);
    if (sceneRef.current) apply(sceneRef.current, next);
  };

  const changeMode = async (nextMode: Professional3DMode) => {
    const active = sceneRef.current;
    if (!active || nextMode === mode || modeLoading) return;
    setModeLoading(true);
    setModeWarning(null);
    setSelectedFeature(null);
    try {
      const result = await active.setMode(nextMode);
      setMode(result.mode);
      setModeWarning(result.warning ?? null);
    } catch (reason: unknown) {
      setMode("analytical");
      setModeWarning(
        reason instanceof Error
          ? reason.message
          : "Photorealistic mode could not be loaded; Analytical mode has been restored.",
      );
    } finally {
      setModeLoading(false);
    }
  };

  return createPortal(
    <div
      className={clsx(
        "fixed inset-0 z-[100] flex flex-col",
        dark ? "bg-gray-950" : "bg-slate-100",
      )}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <header
        className={clsx(
          "relative z-20 flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3 sm:px-5",
          dark
            ? "border-gray-800 bg-gray-950/90 text-gray-100 backdrop-blur-xl"
            : "border-slate-200 bg-white/90 text-slate-900 backdrop-blur-xl",
        )}
      >
        <div className="min-w-0">
          <p className="app-kicker">Professional context</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <h2 id={titleId} className="font-display truncate text-lg font-semibold tracking-tight sm:text-xl">
              3D site view
            </h2>
            <span
              className={clsx(
                "rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                dark
                  ? "border-amber-700/60 bg-amber-950/40 text-amber-300"
                  : "border-amber-200 bg-amber-50 text-amber-800",
              )}
            >
              Pilot
            </span>
          </div>
          <p className={clsx("mt-0.5 truncate text-[11px] sm:text-xs", dark ? "text-gray-400" : "text-slate-500")}>
            {placeLabel} · {professionalLabel} · {radiusKm} km
          </p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          className={clsx(
            "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition",
            dark
              ? "border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white"
              : "border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900",
          )}
          aria-label="Close professional 3D site view"
        >
          <IconX size={16} />
        </button>
      </header>

      <div className="relative min-h-0 flex-1">
        <div ref={mapRef} className={clsx("absolute inset-0", dark ? "bg-gray-900" : "bg-slate-200")} aria-label="Interactive professional 3D map" />

        <aside
          className={clsx(
            "glass-surface absolute left-3 top-3 z-10 max-h-[calc(100%-1.5rem)] w-[min(21rem,calc(100vw-1.5rem))] overflow-y-auto rounded-[1.5rem] border p-3 sm:left-4 sm:top-4 sm:p-4",
            dark
              ? "border-gray-700 bg-gray-950/90 text-gray-100"
              : "border-white/80 bg-white/92 text-slate-900",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="app-kicker">Site context layers</p>
              <p className={clsx("mt-1 text-[11px] leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
                Reference planning and observed surface conditions - not surveyed or statutory evidence.
              </p>
            </div>
            <button
              type="button"
              disabled={loadState !== "ready"}
              onClick={() => scene?.resetView()}
              className={clsx(
                "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-40",
                dark
                  ? "border-gray-700 text-gray-300 hover:bg-gray-800"
                  : "border-slate-200 text-slate-600 hover:bg-slate-100",
              )}
              aria-label="Reset professional 3D view"
              title="Reset view"
            >
              <IconHome size={14} />
            </button>
          </div>

          <div
            className={clsx(
              "mt-3 grid grid-cols-2 gap-1 rounded-2xl border p-1",
              dark ? "border-gray-800 bg-gray-900/80" : "border-slate-200 bg-slate-50",
            )}
          >
            {(["analytical", "photorealistic"] as const).map((value) => (
              <button
                key={value}
                type="button"
                disabled={loadState !== "ready" || modeLoading || (value === "photorealistic" && !scene?.photorealisticAvailable)}
                onClick={() => void changeMode(value)}
                className={clsx(
                  "rounded-xl px-2 py-2 text-[11px] font-semibold capitalize transition disabled:cursor-not-allowed disabled:opacity-40",
                  mode === value
                    ? "bg-sky-700 text-white shadow-sm hover:bg-sky-600"
                    : dark
                      ? "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                      : "text-slate-500 hover:bg-white hover:text-slate-800",
                )}
              >
                {modeLoading && value === "photorealistic" ? "Loading…" : value}
              </button>
            ))}
          </div>

          <p className={clsx("mt-2 text-[10px] leading-relaxed", dark ? "text-gray-400" : "text-slate-500")}>
            {mode === "analytical"
              ? "Evidence-led terrain, Overture buildings and observed canopy zones."
              : "Visual imagery context from Google; coverage and visible conditions may be incomplete or outdated."}
          </p>
          {modeWarning && (
            <p className={clsx("mt-1 text-[10px] leading-relaxed", dark ? "text-amber-300" : "text-amber-700")} role="status">
              {modeWarning}
            </p>
          )}

          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[
              {
                label: "Observed land cover",
                checked: landCoverVisible,
                disabled: mode !== "analytical",
                action: () => toggle(landCoverVisible, setLandCoverVisible, (active, value) => active.setLandCoverVisible(value)),
              },
              {
                label: "Land-use reference",
                checked: landUseVisible,
                disabled: mode !== "analytical",
                action: () => toggle(landUseVisible, setLandUseVisible, (active, value) => active.setLandUseVisible(value)),
              },
              {
                label: "Nearby evidence",
                checked: evidenceVisible,
                action: () => toggle(evidenceVisible, setEvidenceVisible, (active, value) => active.setEvidenceVisible(value)),
              },
              {
                label: "Analytical buildings",
                checked: buildingsVisible,
                disabled: mode !== "analytical" || !scene?.buildingsEnabled,
                action: () => toggle(buildingsVisible, setBuildingsVisible, (active, value) => active.setBuildingsVisible(value)),
              },
              {
                label: "Canopy zones",
                checked: vegetationVisible,
                disabled: mode !== "analytical" || !scene?.vegetationEnabled,
                action: () => toggle(vegetationVisible, setVegetationVisible, (active, value) => active.setVegetationVisible(value)),
              },
            ].map((item) => (
              <label
                key={item.label}
                className={clsx(
                  "flex cursor-pointer items-center gap-2 rounded-2xl border px-2.5 py-2 text-[11px] font-medium transition",
                  item.disabled && "cursor-not-allowed opacity-45",
                  item.checked
                    ? dark
                      ? "border-sky-700/50 bg-sky-950/40 text-sky-100"
                      : "border-sky-200 bg-sky-50 text-sky-900"
                    : dark
                      ? "border-gray-800 bg-gray-900/70 text-gray-200"
                      : "border-slate-200 bg-white text-slate-700",
                )}
              >
                <input
                  type="checkbox"
                  checked={item.checked}
                  disabled={loadState !== "ready" || item.disabled}
                  onChange={item.action}
                  className="h-3.5 w-3.5 accent-sky-600"
                />
                <span className="leading-snug">{item.label}</span>
              </label>
            ))}
          </div>

          {loadState === "loading" && (
            <p className={clsx("mt-3 flex items-center gap-2 text-xs", dark ? "text-sky-300" : "text-sky-700")} role="status">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600" />
              Loading the professional 3D scene…
            </p>
          )}
          {loadState === "error" && (
            <div
              className={clsx(
                "mt-3 rounded-2xl border p-3 text-[11px]",
                dark ? "border-red-800/70 bg-red-950/40 text-red-200" : "border-red-200 bg-red-50 text-red-800",
              )}
            >
              <p>{error}</p>
              <button
                type="button"
                onClick={() => setRetryKey((key) => key + 1)}
                className="mt-2 inline-flex rounded-lg bg-sky-700 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-sky-600"
              >
                Retry
              </button>
            </div>
          )}
          {loadState === "ready" && (
            <div className={clsx("mt-3 border-t pt-3 text-[10px] leading-relaxed", dark ? "border-gray-800 text-gray-400" : "border-slate-200 text-slate-500")}>
              <p>
                Terrain: {scene?.terrainLabel ?? "base globe"}
                {scene?.terrainEnabled && scene.terrainExaggeration > 1
                  ? ` (${scene.terrainExaggeration.toFixed(2)}× relief emphasis)`
                  : ""}
                {" · "}Buildings: {scene?.buildingStatus.featureCount.toLocaleString() ?? "0"}
                {" · "}Canopy zones: {scene?.vegetationStatus.featureCount.toLocaleString() ?? "0"}
              </p>
              <p className="mt-1.5">
                The reset view focuses on the nearest 3 km of site context; zoom out to inspect the full {radiusKm} km analysis radius.
              </p>
              {scene?.warnings.map((warning) => (
                <p key={warning} className={clsx("mt-1", dark ? "text-amber-300" : "text-amber-700")}>
                  {warning}
                </p>
              ))}
              {mode === "analytical" && (
                <>
                  <div
                    className={clsx(
                      "mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 rounded-2xl border p-2.5",
                      dark ? "border-gray-800 bg-gray-900/70" : "border-slate-200 bg-slate-50",
                    )}
                    aria-label="Analytical 3D legend"
                  >
                    <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-sky-600" />Blue: published height</span>
                    <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-slate-500" />Grey: floors-derived</span>
                    <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-amber-600" />Amber: 6 m visual default</span>
                    <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-green-700" />Green: observed canopy</span>
                  </div>
                  <p className="mt-2">
                    Buildings:{" "}
                    <a
                      href="https://www.overturemaps.org/"
                      target="_blank"
                      rel="noreferrer"
                      className={clsx("font-semibold underline underline-offset-2", dark ? "text-sky-300" : "text-sky-700")}
                    >
                      Overture Maps contributors (ODbL)
                    </a>
                    . Canopy polygons are observed zones with illustrative height - not a tree inventory.
                  </p>
                </>
              )}
            </div>
          )}

          {selectedFeature && mode === "analytical" && (
            <div
              className={clsx(
                "bento-card mt-3 rounded-2xl border p-3 text-[11px] leading-relaxed",
                dark ? "border-gray-700 bg-gray-900" : "border-slate-200 bg-white",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="font-display text-sm font-semibold">{selectedFeature.title}</p>
                <button
                  type="button"
                  onClick={() => setSelectedFeature(null)}
                  className={clsx(
                    "inline-flex h-7 w-7 items-center justify-center rounded-full border transition",
                    dark ? "border-gray-700 text-gray-300 hover:bg-gray-800" : "border-slate-200 text-slate-500 hover:bg-slate-50",
                  )}
                  aria-label="Close feature details"
                >
                  <IconX size={12} />
                </button>
              </div>
              {selectedFeature.kind === "building" ? (
                <p className={clsx("mt-1", dark ? "text-gray-400" : "text-slate-500")}>
                  Height basis: {String(selectedFeature.properties.height_basis ?? "unknown").replaceAll("_", " ")}
                  {selectedFeature.properties.num_floors ? ` · ${String(selectedFeature.properties.num_floors)} published floors` : ""}
                  {" · "}Overture release {String(selectedFeature.properties.release ?? "unknown")}
                </p>
              ) : (
                <p className={clsx("mt-1", dark ? "text-gray-400" : "text-slate-500")}>
                  Satellite-observed tree cover, not an individual tree inventory or ecological survey.
                </p>
              )}
            </div>
          )}
        </aside>

        <div className="pointer-events-none absolute inset-x-3 bottom-3 z-10 flex justify-center">
          <p
            className={clsx(
              "glass-surface max-w-2xl rounded-full border px-4 py-2 text-center text-[10px] leading-relaxed",
              dark
                ? "border-gray-700 bg-gray-950/85 text-gray-200"
                : "border-white/80 bg-white/90 text-slate-600",
            )}
          >
            Visual decision support only. Confirm terrain, drainage, buildings, planning and site conditions through survey and official records.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
