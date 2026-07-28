import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import maplibregl from "maplibre-gl";
import { analyzePoint, type Scorecard } from "./api";
import { AppHeader } from "./components/AppHeader";
import { BasemapSwitcher } from "./components/BasemapSwitcher";
import {
  LayersLegendPanel,
  type OverlayLayer,
  type OverlayLayerId,
} from "./components/LayersLegendPanel";
import { ScorecardConsole } from "./components/ScorecardConsole";
import {
  DEFAULT_BASEMAP_ID,
  getBasemap,
  type BasemapId,
} from "./lib/basemap";
import { applyTheme, loadTheme, type Theme } from "./theme";

const FCT_CENTER: [number, number] = [7.4913, 9.0579];

const DEFAULT_LAYERS: OverlayLayer[] = [
  {
    id: "score_marker",
    label: "Analysis pin",
    description: "Selected location marker",
    swatch: "#0369a1",
    enabled: true,
  },
  {
    id: "flood_context",
    label: "Flood context",
    description: "GGIS hazard context (tiles soon)",
    swatch: "#0284c7",
    enabled: true,
  },
  {
    id: "amenities_poi",
    label: "Amenity context",
    description: "Nearby services in score evidence",
    swatch: "#0d9488",
    enabled: true,
  },
];

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const basemapIdRef = useRef<BasemapId>(DEFAULT_BASEMAP_ID);
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    return loadTheme();
  });
  const [basemapId, setBasemapId] = useState<BasemapId>(DEFAULT_BASEMAP_ID);
  const [layers, setLayers] = useState<OverlayLayer[]>(DEFAULT_LAYERS);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [placeLabel, setPlaceLabel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(true);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const layerEnabled = useCallback(
    (id: OverlayLayerId) => layers.find((l) => l.id === id)?.enabled ?? true,
    [layers],
  );

  const runAnalyse = useCallback(
    async (lng: number, lat: number, label?: string) => {
      const map = mapRef.current;
      if (!map) return;

      if (layerEnabled("score_marker")) {
        markerRef.current?.remove();
        markerRef.current = new maplibregl.Marker({ color: "#0369a1" })
          .setLngLat([lng, lat])
          .addTo(map);
      } else {
        markerRef.current?.remove();
        markerRef.current = null;
      }

      setPlaceLabel(label ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
      setSheetOpen(true);
      setLoading(true);
      setError(null);
      try {
        setCard(await analyzePoint(lng, lat));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [layerEnabled],
  );

  useEffect(() => {
    const container = mapContainer.current;
    if (!container) return;

    let cancelled = false;
    setMapError(null);

    const map = new maplibregl.Map({
      container,
      style: getBasemap(basemapIdRef.current).style,
      center: FCT_CENTER,
      zoom: 11,
    });
    mapRef.current = map;

    // Keep zoom clear of left-side layers / basemap chrome.
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const resize = () => {
      if (!cancelled && mapRef.current) map.resize();
    };
    map.on("load", resize);
    map.on("error", (e) => {
      const msg = e.error?.message || "Map failed to load tiles";
      if (/style|source|Failed to fetch|NetworkError/i.test(msg)) {
        setMapError(msg);
      }
    });
    window.addEventListener("resize", resize);
    requestAnimationFrame(() => {
      requestAnimationFrame(resize);
    });

    const ro = new ResizeObserver(() => resize());
    ro.observe(container);

    return () => {
      cancelled = true;
      ro.disconnect();
      window.removeEventListener("resize", resize);
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep click handler current without remounting the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const onClick = (e: maplibregl.MapMouseEvent) => {
      void runAnalyse(e.lngLat.lng, e.lngLat.lat);
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [runAnalyse]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (basemapId === basemapIdRef.current) return;

    const center = map.getCenter();
    const zoom = map.getZoom();
    const bearing = map.getBearing();
    const pitch = map.getPitch();
    const markerLngLat = markerRef.current?.getLngLat();

    basemapIdRef.current = basemapId;
    setMapError(null);
    map.setStyle(getBasemap(basemapId).style);
    map.once("style.load", () => {
      map.jumpTo({ center, zoom, bearing, pitch });
      if (markerLngLat && layerEnabled("score_marker")) {
        markerRef.current?.remove();
        markerRef.current = new maplibregl.Marker({ color: "#0369a1" })
          .setLngLat(markerLngLat)
          .addTo(map);
      }
      map.resize();
    });
  }, [basemapId, layerEnabled]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!layerEnabled("score_marker")) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    // Re-show marker at last analysed place if we have one.
    if (!markerRef.current && card?.location.geohash8) {
      // no coords stored — leave until next analyse
    }
  }, [layers, card, layerEnabled]);

  const flyAndAnalyse = (lon: number, lat: number, label?: string) => {
    const map = mapRef.current;
    if (map) {
      map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 13), duration: 1200 });
    }
    void runAnalyse(lon, lat, label);
  };

  const toggleLayer = (id: OverlayLayerId) => {
    setLayers((prev) => prev.map((l) => (l.id === id ? { ...l, enabled: !l.enabled } : l)));
  };

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  const dark = theme === "dark";

  return (
    <div
      className={clsx(
        "app-shell font-sans flex h-[100dvh] flex-col overflow-hidden",
        dark
          ? "bg-gradient-to-br from-gray-950 via-slate-950 to-sky-950/40"
          : "bg-gradient-to-br from-sky-50 via-slate-100 to-cyan-50/60",
      )}
    >
      <AppHeader
        theme={theme}
        onToggleTheme={toggleTheme}
        onSelectPlace={flyAndAnalyse}
        locating={loading}
      />

      <div className="relative flex min-h-0 flex-1 flex-row">
        <div className="hidden h-full w-[22rem] shrink-0 lg:block xl:w-96">
          <ScorecardConsole
            theme={theme}
            card={card}
            loading={loading}
            error={error}
            placeLabel={placeLabel}
          />
        </div>

        <main className="relative h-full min-h-0 min-w-0 flex-1">
          <div ref={mapContainer} className="h-full w-full bg-slate-200" />

          {/* Zoom stays top-right; overlays live bottom-left */}
          <LayersLegendPanel theme={theme} layers={layers} onToggle={toggleLayer} />
          <BasemapSwitcher theme={theme} activeId={basemapId} onChange={setBasemapId} />

          {mapError && (
            <div className="absolute inset-x-4 top-3 z-[2] rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 sm:left-auto sm:right-14 sm:w-72">
              Map error: {mapError}
            </div>
          )}
        </main>

        <div
          className={clsx(
            "absolute inset-x-0 bottom-0 z-10 max-h-[min(48vh,26rem)] overflow-hidden rounded-t-2xl border shadow-lg transition-transform duration-300 lg:hidden",
            dark ? "border-gray-800" : "border-slate-200",
            sheetOpen ? "translate-y-0" : "translate-y-[calc(100%-2.75rem)]",
          )}
        >
          <button
            type="button"
            className={clsx(
              "flex w-full items-center justify-center border-b py-2",
              dark ? "border-gray-800 bg-gray-900 text-gray-400" : "border-slate-200 bg-white text-slate-500",
            )}
            onClick={() => setSheetOpen((o) => !o)}
            aria-label={sheetOpen ? "Collapse scorecard" : "Expand scorecard"}
          >
            <span className="h-1 w-10 rounded-full bg-slate-300" />
          </button>
          <div className="h-[min(44vh,24rem)]">
            <ScorecardConsole
              theme={theme}
              card={card}
              loading={loading}
              error={error}
              placeLabel={placeLabel}
              onClose={() => setSheetOpen(false)}
            />
          </div>
        </div>
      </div>

      <footer
        className={clsx(
          "shrink-0 border-t px-4 py-1.5 text-center text-[10px]",
          dark ? "border-gray-800 text-gray-500" : "border-slate-200 text-slate-400",
        )}
      >
        Advisory property intelligence — not a legal or engineering sign-off · Geoinfotech / GGIS
      </footer>
    </div>
  );
}
