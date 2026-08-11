import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import type { Scorecard } from "../api";
import type { Professional3DScene } from "../lib/cesiumScene";
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
    setLoadState("loading");
    setError(null);

    void import("../lib/cesiumScene")
      .then(({ createProfessional3DScene }) => createProfessional3DScene(mapRef.current!, {
        card,
        lon,
        lat,
        radiusKm,
        placeLabel,
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
        setLoadState("ready");
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "The professional 3D view could not start.");
        setLoadState("error");
      });

    return () => {
      cancelled = true;
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

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex flex-col bg-slate-950"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <header
        className={clsx(
          "relative z-20 flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3 sm:px-5",
          dark ? "border-gray-800 bg-gray-950 text-gray-100" : "border-slate-200 bg-white text-slate-900",
        )}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 id={titleId} className="truncate text-base font-semibold sm:text-lg">
              Professional 3D site view
            </h2>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-800">
              Pilot
            </span>
          </div>
          <p className={clsx("truncate text-[11px] sm:text-xs", dark ? "text-gray-400" : "text-slate-500") }>
            {placeLabel} · {professionalLabel} · {radiusKm} km
          </p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          className={clsx(
            "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition",
            dark
              ? "border-gray-700 text-gray-300 hover:bg-gray-800"
              : "border-slate-200 text-slate-600 hover:bg-slate-100",
          )}
          aria-label="Close professional 3D site view"
        >
          <IconX size={16} />
        </button>
      </header>

      <div className="relative min-h-0 flex-1">
        <div ref={mapRef} className="absolute inset-0 bg-slate-900" aria-label="Interactive professional 3D map" />

        <aside
          className={clsx(
            "absolute left-3 top-3 z-10 w-[min(20rem,calc(100vw-1.5rem))] rounded-2xl border p-3 shadow-2xl backdrop-blur-md sm:left-4 sm:top-4 sm:p-4",
            dark
              ? "border-gray-700 bg-gray-950/90 text-gray-100"
              : "border-white/80 bg-white/92 text-slate-900",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold">Site context layers</p>
              <p className={clsx("mt-0.5 text-[10px] leading-4", dark ? "text-gray-400" : "text-slate-500") }>
                Reference planning and observed surface conditions—not surveyed or statutory evidence.
              </p>
            </div>
            <button
              type="button"
              disabled={loadState !== "ready"}
              onClick={() => scene?.resetView()}
              className={clsx(
                "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border disabled:cursor-not-allowed disabled:opacity-40",
                dark ? "border-gray-700 hover:bg-gray-800" : "border-slate-200 hover:bg-slate-100",
              )}
              aria-label="Reset professional 3D view"
              title="Reset view"
            >
              <IconHome size={14} />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
            {[
              {
                label: "Observed land cover",
                checked: landCoverVisible,
                action: () => toggle(landCoverVisible, setLandCoverVisible, (active, value) => active.setLandCoverVisible(value)),
              },
              {
                label: "Land-use reference",
                checked: landUseVisible,
                action: () => toggle(landUseVisible, setLandUseVisible, (active, value) => active.setLandUseVisible(value)),
              },
              {
                label: "Nearby evidence",
                checked: evidenceVisible,
                action: () => toggle(evidenceVisible, setEvidenceVisible, (active, value) => active.setEvidenceVisible(value)),
              },
              {
                label: "3D buildings",
                checked: buildingsVisible,
                disabled: !scene?.buildingsEnabled,
                action: () => toggle(buildingsVisible, setBuildingsVisible, (active, value) => active.setBuildingsVisible(value)),
              },
            ].map((item) => (
              <label
                key={item.label}
                className={clsx(
                  "flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-2",
                  item.disabled && "cursor-not-allowed opacity-45",
                  dark ? "border-gray-700 bg-gray-900/70" : "border-slate-200 bg-slate-50",
                )}
              >
                <input
                  type="checkbox"
                  checked={item.checked}
                  disabled={loadState !== "ready" || item.disabled}
                  onChange={item.action}
                  className="h-3.5 w-3.5 accent-sky-600"
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>

          {loadState === "loading" && (
            <p className="mt-3 flex items-center gap-2 text-xs text-sky-500" role="status">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-sky-200 border-t-sky-600" />
              Loading the professional 3D scene…
            </p>
          )}
          {loadState === "error" && (
            <div className="mt-3 rounded-lg border border-red-300 bg-red-50 p-2 text-[11px] text-red-800">
              <p>{error}</p>
              <button type="button" onClick={() => setRetryKey((key) => key + 1)} className="mt-1 font-semibold underline">
                Retry
              </button>
            </div>
          )}
          {loadState === "ready" && (
            <div className={clsx("mt-3 border-t pt-2 text-[10px] leading-4", dark ? "border-gray-700 text-gray-400" : "border-slate-200 text-slate-500") }>
              <p>
                Terrain: {scene?.terrainLabel ?? "base globe"}
                {scene?.terrainEnabled && scene.terrainExaggeration > 1
                  ? ` (${scene.terrainExaggeration.toFixed(2)}× relief emphasis)`
                  : ""}
                {" · "}Buildings: {scene?.buildingsEnabled ? "available" : "not configured"}
              </p>
              <p className="mt-1">
                The reset view focuses on the nearest 3 km of site context; zoom out to inspect the full {radiusKm} km analysis radius.
              </p>
              {scene?.warnings.map((warning) => <p key={warning} className="mt-1 text-amber-500">{warning}</p>)}
            </div>
          )}
        </aside>

        <div className="pointer-events-none absolute inset-x-3 bottom-3 z-10 flex justify-center">
          <p className="max-w-2xl rounded-full bg-slate-950/80 px-4 py-2 text-center text-[10px] leading-4 text-slate-200 shadow-lg backdrop-blur">
            Visual decision support only. Confirm terrain, drainage, buildings, planning and site conditions through survey and official records.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
