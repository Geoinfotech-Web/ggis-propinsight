import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import maplibregl from "maplibre-gl";
import { analyzePoint, type Scorecard } from "./api";
import { AppHeader } from "./components/AppHeader";
import { BasemapSwitcher } from "./components/BasemapSwitcher";
import { IconHome } from "./components/Icons";
import { LayersPanel, type OverlayLayer, type OverlayLayerId } from "./components/LayersPanel";
import { MapLegend } from "./components/MapLegend";
import { NearbyAmenitiesList, type NearbyPoiItem } from "./components/NearbyAmenitiesList";
import { ScorecardConsole } from "./components/ScorecardConsole";
import {
  DEFAULT_BASEMAP_ID,
  getBasemap,
  type BasemapId,
} from "./lib/basemap";
import {
  AMENITY_CIRCLE_LAYER,
  AMENITY_LABEL_LAYER,
  AMENITY_SOURCE_ID,
  nearbyFromScorecard,
  nearbyToGeoJSON,
} from "./lib/amenitiesMap";
import { loadPersona, savePersona, type PersonaKey } from "./lib/personas";
import { applyTheme, loadTheme, type Theme } from "./theme";

const FCT_CENTER: [number, number] = [7.4913, 9.0579];
const FCT_HOME_ZOOM = 11;

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
    description: "Named schools, hospitals, markets, banks (5 km)",
    swatch: "#0d9488",
    enabled: true,
  },
];

function syncAmenityOverlay(
  map: maplibregl.Map,
  card: Scorecard | null,
  visible: boolean,
) {
  const pois = visible ? nearbyFromScorecard(card?.domains.amenities?.evidence) : [];
  const data = nearbyToGeoJSON(pois);

  if (map.getSource(AMENITY_SOURCE_ID)) {
    (map.getSource(AMENITY_SOURCE_ID) as maplibregl.GeoJSONSource).setData(data);
  } else {
    map.addSource(AMENITY_SOURCE_ID, { type: "geojson", data });
  }

  if (!map.getLayer(AMENITY_CIRCLE_LAYER)) {
    map.addLayer({
      id: AMENITY_CIRCLE_LAYER,
      type: "circle",
      source: AMENITY_SOURCE_ID,
      paint: {
        "circle-radius": 6,
        "circle-color": ["get", "color"],
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "#ffffff",
        "circle-opacity": 0.95,
      },
    });
  }
  if (!map.getLayer(AMENITY_LABEL_LAYER)) {
    map.addLayer({
      id: AMENITY_LABEL_LAYER,
      type: "symbol",
      source: AMENITY_SOURCE_ID,
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Regular"],
        "text-size": 11,
        "text-offset": [0, 1.15],
        "text-anchor": "top",
        "text-max-width": 10,
        "text-optional": true,
      },
      paint: {
        "text-color": "#0f172a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.25,
      },
    });
  }

  const vis = visible && pois.length > 0 ? "visible" : "none";
  if (map.getLayer(AMENITY_CIRCLE_LAYER)) map.setLayoutProperty(AMENITY_CIRCLE_LAYER, "visibility", vis);
  if (map.getLayer(AMENITY_LABEL_LAYER)) map.setLayoutProperty(AMENITY_LABEL_LAYER, "visibility", vis);
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const basemapIdRef = useRef<BasemapId>(DEFAULT_BASEMAP_ID);
  const lastPointRef = useRef<{ lon: number; lat: number; label?: string } | null>(null);
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    return loadTheme();
  });
  const [persona, setPersona] = useState<PersonaKey>(() => loadPersona());
  const [basemapId, setBasemapId] = useState<BasemapId>(DEFAULT_BASEMAP_ID);
  const [layers, setLayers] = useState<OverlayLayer[]>(DEFAULT_LAYERS);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [placeLabel, setPlaceLabel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(true);
  const [amenitiesListOpen, setAmenitiesListOpen] = useState(false);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const layerEnabled = useCallback(
    (id: OverlayLayerId) => layers.find((l) => l.id === id)?.enabled ?? true,
    [layers],
  );

  const runAnalyse = useCallback(
    async (lng: number, lat: number, label?: string, profile: PersonaKey = persona) => {
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

      lastPointRef.current = { lon: lng, lat, label };
      setPlaceLabel(label ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
      setSheetOpen(true);
      setLoading(true);
      setError(null);
      try {
        setCard(await analyzePoint(lng, lat, profile));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [layerEnabled, persona],
  );

  const onPersonaChange = (key: PersonaKey) => {
    setPersona(key);
    savePersona(key);
    const last = lastPointRef.current;
    if (last) {
      void runAnalyse(last.lon, last.lat, last.label, key);
    }
  };

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
      syncAmenityOverlay(map, card, layerEnabled("amenities_poi"));
      map.resize();
    });
  }, [basemapId, layerEnabled, card]);

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

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => syncAmenityOverlay(map, card, layerEnabled("amenities_poi"));
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [card, layers, layerEnabled]);

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
  const nearbyAmenities = nearbyFromScorecard(card?.domains.amenities?.evidence);

  const focusNearby = (item: NearbyPoiItem) => {
    if (item.lon == null || item.lat == null) return;
    mapRef.current?.flyTo({
      center: [item.lon, item.lat],
      zoom: Math.max(mapRef.current.getZoom(), 15),
      duration: 900,
    });
    setAmenitiesListOpen(false);
  };

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
        persona={persona}
        onPersonaChange={onPersonaChange}
      />

      <div className="relative flex min-h-0 flex-1 flex-row">
        <div className="hidden h-full w-[22rem] shrink-0 lg:block xl:w-96">
          <ScorecardConsole
            theme={theme}
            card={card}
            loading={loading}
            error={error}
            placeLabel={placeLabel}
            persona={persona}
            onViewNearbyList={() => setAmenitiesListOpen(true)}
          />
        </div>

        <main className="relative h-full min-h-0 min-w-0 flex-1">
          <div ref={mapContainer} className="h-full w-full bg-slate-200" />

          {/* Flood Watch MapPanel layout: Legend bottom-left · Home+Basemap+Layers under zoom */}
          <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-[calc(100vw-5.5rem)] space-y-2 sm:max-w-none">
            {nearbyAmenities.length > 0 && layerEnabled("amenities_poi") && (
              <div className="pointer-events-auto">
                <button
                  type="button"
                  onClick={() => setAmenitiesListOpen(true)}
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[11px] font-semibold shadow-lg",
                    dark
                      ? "border-gray-700 bg-gray-900 text-sky-300 hover:bg-gray-800"
                      : "border-slate-200 bg-white text-sky-800 hover:border-slate-300",
                  )}
                >
                  View amenities · {nearbyAmenities.length}
                </button>
              </div>
            )}
          </div>

          <div className="pointer-events-none absolute top-[5.5rem] right-3 z-10 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => {
                mapRef.current?.flyTo({ center: FCT_CENTER, zoom: FCT_HOME_ZOOM, duration: 1000 });
              }}
              className={clsx(
                "pointer-events-auto inline-flex h-10 w-10 items-center justify-center rounded-xl border shadow-lg transition",
                dark
                  ? "border-gray-700 bg-gray-900 text-gray-200 hover:border-gray-500 hover:bg-gray-800 hover:text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900",
              )}
              style={
                dark
                  ? { backgroundColor: "#111827", borderColor: "#374151" }
                  : { backgroundColor: "#ffffff", borderColor: "#cbd5e1" }
              }
              aria-label="Reset map to FCT"
              title="Home"
            >
              <IconHome size={15} />
            </button>
            <div className="pointer-events-auto">
              <BasemapSwitcher theme={theme} activeId={basemapId} onChange={setBasemapId} />
            </div>
            <div className="pointer-events-auto">
              <LayersPanel theme={theme} layers={layers} onToggle={toggleLayer} />
            </div>
          </div>

          <div
            className={clsx(
              "pointer-events-none absolute left-3 z-10 hidden sm:block",
              sheetOpen
                ? "bottom-[calc(min(48vh,26rem)+0.75rem)] lg:bottom-10"
                : "bottom-10",
            )}
          >
            <div className="pointer-events-auto">
              <MapLegend theme={theme} layers={layers} />
            </div>
          </div>

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
              persona={persona}
              onClose={() => setSheetOpen(false)}
              onViewNearbyList={() => setAmenitiesListOpen(true)}
            />
          </div>
        </div>
      </div>

      <NearbyAmenitiesList
        theme={theme}
        items={nearbyAmenities}
        open={amenitiesListOpen}
        onClose={() => setAmenitiesListOpen(false)}
        onSelect={focusNearby}
      />

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
