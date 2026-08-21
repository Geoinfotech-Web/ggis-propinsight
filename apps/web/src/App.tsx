import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import maplibregl from "maplibre-gl";
import {
  analyzePoint,
  fetchLandUse,
  type Scorecard,
} from "./api";
import { AppHeader } from "./components/AppHeader";
import {
  AnalysisSetupDialog,
  type AnalysisCandidate,
  type AnalysisFlowPhase,
  type PdfGenerationStatus,
} from "./components/AnalysisSetupDialog";
import { BasemapSwitcher } from "./components/BasemapSwitcher";
import { IconHome } from "./components/Icons";
import { LayersPanel, type OverlayLayer, type OverlayLayerId } from "./components/LayersPanel";
import { MapLegend } from "./components/MapLegend";
import { Map3DControl } from "./components/Map3DControl";
import { NearbyAmenitiesList, type NearbyPoiItem } from "./components/NearbyAmenitiesList";
import { Professional3DDialog } from "./components/Professional3DDialog";
import { ReportGuideDialog } from "./components/ReportGuideDialog";
import { ScorecardConsole } from "./components/ScorecardConsole";
import {
  DEFAULT_BASEMAP_ID,
  getBasemap,
  type BasemapId,
} from "./lib/basemap";
import {
  AMENITY_MARKER_COLORS,
  createPoiSymbolElement,
  nearbyFromScorecard,
} from "./lib/amenitiesMap";
import { getPersona, loadPersona, savePersona, type PersonaKey } from "./lib/personas";
import { hideLandUseLayer, showLandUseLayer } from "./lib/landUseMap";
import { hideLandCoverLayer, showLandCoverLayer } from "./lib/landCoverMap";
import { mappedProjects } from "./lib/projectsMap";
import {
  analysisBufferBounds,
  hideAnalysisBuffer,
  showAnalysisBuffer,
} from "./lib/analysisBufferMap";
import {
  loadAnalysisRadius,
  saveAnalysisRadius,
} from "./lib/analysisRadius";
import {
  AUTO_3D_ENTER_ZOOM,
  AUTO_3D_EXIT_ZOOM,
  syncMap3DStyle,
  transitionMapDimension,
} from "./lib/map3d";
import { applyTheme, loadTheme, type Theme } from "./theme";

const FCT_CENTER: [number, number] = [7.4913, 9.0579];
const FCT_HOME_ZOOM = 11;

const POI_LAYER_BY_CATEGORY: Record<string, OverlayLayerId> = {
  school: "school_poi",
  hospital: "hospital_poi",
  bank: "bank_poi",
  market: "market_poi",
  power: "power_poi",
  fuel: "fuel_poi",
  police: "security_poi",
};

const AMENITY_LAYER_IDS: OverlayLayerId[] = [
  "school_poi",
  "hospital_poi",
  "bank_poi",
  "market_poi",
  "power_poi",
  "fuel_poi",
];

function poiMarkerSizeForZoom(zoom: number): number {
  return Math.round(Math.min(38, Math.max(18, 18 + (zoom - 9) * 2.5)));
}

function resizePoiMarkers(map: maplibregl.Map, markers: maplibregl.Marker[]) {
  const markerSize = poiMarkerSizeForZoom(map.getZoom());
  const symbolSize = Math.max(11, Math.round(markerSize * 0.58));
  for (const marker of markers) {
    const element = marker.getElement();
    element.style.width = `${markerSize}px`;
    element.style.height = `${markerSize}px`;
    const symbol = element.querySelector("svg");
    symbol?.setAttribute("width", String(symbolSize));
    symbol?.setAttribute("height", String(symbolSize));
  }
}

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
    id: "government_projects",
    label: "Verified public projects",
    description: "Official projects within the selected professional analysis radius",
    swatch: "#d97706",
    enabled: true,
  },
  {
    id: "land_cover",
    label: "Observed land cover · entire FCT",
    description: "Wall-to-wall satellite classification; not zoning",
    swatch: "#397d49",
    enabled: false,
  },
  {
    id: "land_use",
    label: "Mapped / official land use",
    description: "Detailed mapped uses; official plans take precedence",
    swatch: "#8b5cf6",
    enabled: true,
  },
  {
    id: "school_poi",
    label: "Schools",
    description: "Schools within the selected location's buffer",
    swatch: AMENITY_MARKER_COLORS.school,
    symbol: "school",
    enabled: true,
  },
  {
    id: "hospital_poi",
    label: "Hospitals",
    description: "Hospitals and clinics within the buffer",
    swatch: AMENITY_MARKER_COLORS.hospital,
    symbol: "hospital",
    enabled: true,
  },
  {
    id: "bank_poi",
    label: "Banks",
    description: "Banks within the selected location's buffer",
    swatch: AMENITY_MARKER_COLORS.bank,
    symbol: "bank",
    enabled: true,
  },
  {
    id: "market_poi",
    label: "Markets",
    description: "Markets within the selected location's buffer",
    swatch: AMENITY_MARKER_COLORS.market,
    symbol: "market",
    enabled: true,
  },
  {
    id: "power_poi",
    label: "Power",
    description: "Power infrastructure within the buffer",
    swatch: AMENITY_MARKER_COLORS.power,
    symbol: "power",
    enabled: true,
  },
  {
    id: "fuel_poi",
    label: "Fuel stations",
    description: "Fuel stations within the selected location's buffer",
    swatch: AMENITY_MARKER_COLORS.fuel,
    symbol: "fuel",
    enabled: true,
  },
  {
    id: "security_poi",
    label: "Security",
    description: "Police stations within the selected location's buffer",
    swatch: AMENITY_MARKER_COLORS.police,
    symbol: "police",
    enabled: true,
  },
];

function nearbyTotalFromScorecard(card: Scorecard | null): number {
  const counts = card?.domains.amenities?.evidence.nearby_counts;
  if (!counts || typeof counts !== "object" || Array.isArray(counts)) return 0;
  return Object.values(counts).reduce<number>(
    (total, count) => total + (typeof count === "number" ? count : 0),
    0,
  );
}

function nearbyCountsFromScorecard(card: Scorecard | null): Record<string, number> | undefined {
  const counts = card?.domains.amenities?.evidence.nearby_counts;
  if (!counts || typeof counts !== "object" || Array.isArray(counts)) return undefined;
  return Object.fromEntries(
    Object.entries(counts).filter((entry): entry is [string, number] =>
      typeof entry[1] === "number",
    ),
  );
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const candidateMarkerRef = useRef<maplibregl.Marker | null>(null);
  const poiMarkersRef = useRef<maplibregl.Marker[]>([]);
  const projectMarkersRef = useRef<maplibregl.Marker[]>([]);
  const basemapIdRef = useRef<BasemapId>(DEFAULT_BASEMAP_ID);
  const view3DRef = useRef(false);
  const suppressAuto3DRef = useRef(false);
  const lastPointRef = useRef<{ lon: number; lat: number; label?: string } | null>(null);
  const analysisRequestRef = useRef(0);
  const analysisAbortRef = useRef<AbortController | null>(null);
  const pdfAbortRef = useRef<AbortController | null>(null);
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    return loadTheme();
  });
  const [persona, setPersona] = useState<PersonaKey>(() => loadPersona());
  const [analysisRadiusKm, setAnalysisRadiusKm] = useState(() => loadAnalysisRadius());
  const [setupPersona, setSetupPersona] = useState<PersonaKey>(() => loadPersona());
  const [setupRadiusKm, setSetupRadiusKm] = useState(() => loadAnalysisRadius());
  const [candidate, setCandidate] = useState<AnalysisCandidate | null>(null);
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisFlowPhase>("setup");
  const [pendingCard, setPendingCard] = useState<Scorecard | null>(null);
  const [analysisFlowError, setAnalysisFlowError] = useState<string | null>(null);
  const [pdfStatus, setPdfStatus] = useState<PdfGenerationStatus>("idle");
  const [committedPdfStatus, setCommittedPdfStatus] = useState<PdfGenerationStatus>("idle");
  const [committedPdfError, setCommittedPdfError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [basemapId, setBasemapId] = useState<BasemapId>(DEFAULT_BASEMAP_ID);
  const [view3D, setView3D] = useState(false);
  const [layers, setLayers] = useState<OverlayLayer[]>(DEFAULT_LAYERS);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [placeLabel, setPlaceLabel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [updatingMessage, setUpdatingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [desktopReportOpen, setDesktopReportOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(true);
  const [amenitiesListOpen, setAmenitiesListOpen] = useState(false);
  const [amenitiesListCategory, setAmenitiesListCategory] = useState<string | null>(null);
  const [reportGuideOpen, setReportGuideOpen] = useState(false);
  const [professional3DOpen, setProfessional3DOpen] = useState(false);
  const [searchResetKey, setSearchResetKey] = useState(0);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const closeReportGuide = useCallback(() => setReportGuideOpen(false), []);

  const layerEnabled = useCallback(
    (id: OverlayLayerId) => layers.find((l) => l.id === id)?.enabled ?? true,
    [layers],
  );

  const changeMapDimension = useCallback((enabled: boolean, animate = true) => {
    view3DRef.current = enabled;
    setView3D(enabled);

    const map = mapRef.current;
    if (!map) return;
    try {
      syncMap3DStyle(map, enabled);
      if (animate) transitionMapDimension(map, enabled);
    } catch (err) {
      setMapError(`3D map unavailable: ${(err as Error).message}`);
    }
  }, []);

  const runAnalyse = useCallback(
    async (
      lng: number,
      lat: number,
      label?: string,
      profile: PersonaKey = persona,
      radiusKm: number = analysisRadiusKm,
      preserveCard = false,
      updateLabel?: string,
    ) => {
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
      setDesktopReportOpen(true);
      setSheetOpen(true);
      if (preserveCard) {
        setUpdatingMessage(updateLabel ?? "Updating report…");
      } else {
        setCard(null);
        setLoading(true);
        setUpdatingMessage(null);
      }
      setError(null);
      const requestId = ++analysisRequestRef.current;
      analysisAbortRef.current?.abort();
      const controller = new AbortController();
      analysisAbortRef.current = controller;
      try {
        const result = await analyzePoint(
          lng,
          lat,
          profile,
          radiusKm * 1_000,
          controller.signal,
        );
        if (requestId === analysisRequestRef.current) setCard(result);
      } catch (err) {
        if (
          requestId === analysisRequestRef.current &&
          (err as Error).name !== "AbortError"
        ) {
          setError((err as Error).message);
        }
      } finally {
        if (requestId === analysisRequestRef.current) {
          setLoading(false);
          setUpdatingMessage(null);
          analysisAbortRef.current = null;
        }
      }
    },
    [analysisRadiusKm, layerEnabled, persona],
  );

  const onPersonaChange = (key: PersonaKey) => {
    setReportGuideOpen(false);
    setProfessional3DOpen(false);
    setPersona(key);
    savePersona(key);
    const last = lastPointRef.current;
    if (last) {
      void runAnalyse(
        last.lon,
        last.lat,
        last.label,
        key,
        analysisRadiusKm,
        true,
        `Updating report for ${getPersona(key).label}…`,
      );
    }
  };

  const beginAnalysisSetup = useCallback(
    (lon: number, lat: number, label?: string) => {
      analysisAbortRef.current?.abort();
      analysisRequestRef.current += 1;
      setLoading(false);
      setUpdatingMessage(null);
      setAnalysisPhase("setup");
      setPendingCard(null);
      setAnalysisFlowError(null);
      setPdfStatus("idle");
      setPdfError(null);
      setReportGuideOpen(false);
      setProfessional3DOpen(false);
      setSetupPersona(persona);
      setSetupRadiusKm(analysisRadiusKm);
      setCandidate({ lon, lat, label });
      mapRef.current?.fitBounds(analysisBufferBounds(lon, lat, analysisRadiusKm), {
        padding: 72,
        duration: 900,
        maxZoom: 13,
      });
    },
    [analysisRadiusKm, persona],
  );

  const cancelAnalysisSetup = useCallback(() => {
    analysisAbortRef.current?.abort();
    analysisRequestRef.current += 1;
    pdfAbortRef.current?.abort();
    pdfAbortRef.current = null;
    setCandidate(null);
    setAnalysisPhase("setup");
    setPendingCard(null);
    setAnalysisFlowError(null);
    setPdfStatus("idle");
    setPdfError(null);
    setLoading(false);
    const last = lastPointRef.current;
    if (last) {
      mapRef.current?.fitBounds(
        analysisBufferBounds(last.lon, last.lat, analysisRadiusKm),
        { padding: 72, duration: 600, maxZoom: 13 },
      );
    }
  }, [analysisRadiusKm]);

  const changeSetupRadius = (radiusKm: number) => {
    setSetupRadiusKm(radiusKm);
    if (candidate) {
      mapRef.current?.fitBounds(
        analysisBufferBounds(candidate.lon, candidate.lat, radiusKm),
        { padding: 72, duration: 250, maxZoom: 13 },
      );
    }
  };

  const analyseCandidate = useCallback(async () => {
    if (!candidate) return;
    const selected = candidate;
    setAnalysisPhase("analysing");
    setPendingCard(null);
    setAnalysisFlowError(null);
    setPdfStatus("idle");
    setPdfError(null);
    setLoading(true);
    setError(null);

    const requestId = ++analysisRequestRef.current;
    analysisAbortRef.current?.abort();
    const controller = new AbortController();
    analysisAbortRef.current = controller;
    try {
      const result = await analyzePoint(
        selected.lon,
        selected.lat,
        setupPersona,
        setupRadiusKm * 1_000,
        controller.signal,
      );
      if (requestId !== analysisRequestRef.current) return;
      setPendingCard(result);
      setAnalysisPhase("ready");
    } catch (err) {
      if (requestId !== analysisRequestRef.current || (err as Error).name === "AbortError") return;
      setAnalysisFlowError((err as Error).message || "The analysis service did not return a result.");
      setAnalysisPhase("error");
    } finally {
      if (requestId === analysisRequestRef.current) {
        setLoading(false);
        analysisAbortRef.current = null;
      }
    }
  }, [candidate, setupPersona, setupRadiusKm]);

  const confirmAnalysisSetup = () => {
    if (!candidate) return;
    void analyseCandidate();
  };

  const viewCandidateOnMap = useCallback(() => {
    if (!candidate || !pendingCard) return;
    const map = mapRef.current;
    if (map && layerEnabled("score_marker")) {
      markerRef.current?.remove();
      markerRef.current = new maplibregl.Marker({ color: "#0369a1" })
        .setLngLat([candidate.lon, candidate.lat])
        .addTo(map);
    } else {
      markerRef.current?.remove();
      markerRef.current = null;
    }
    setPersona(setupPersona);
    savePersona(setupPersona);
    setAnalysisRadiusKm(setupRadiusKm);
    saveAnalysisRadius(setupRadiusKm);
    lastPointRef.current = candidate;
    setPlaceLabel(candidate.label ?? `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`);
    setCard(pendingCard);
    setError(null);
    setDesktopReportOpen(true);
    setSheetOpen(true);
    setReportGuideOpen(false);
    setProfessional3DOpen(false);
    setCandidate(null);
    setPendingCard(null);
    setAnalysisPhase("setup");
    setPdfStatus("idle");
    setPdfError(null);
    setCommittedPdfStatus("idle");
    setCommittedPdfError(null);
  }, [candidate, layerEnabled, pendingCard, setupPersona, setupRadiusKm]);

  const generatePendingReport = useCallback(async () => {
    if (!candidate || !pendingCard) return;
    pdfAbortRef.current?.abort();
    const controller = new AbortController();
    pdfAbortRef.current = controller;
    setPdfStatus("generating");
    setPdfError(null);
    try {
      const { generateLocationReport } = await import("./lib/reportPdf");
      await generateLocationReport({
        card: pendingCard,
        persona: setupPersona,
        lon: candidate.lon,
        lat: candidate.lat,
        radiusKm: setupRadiusKm,
        placeLabel: candidate.label ?? `${candidate.lat.toFixed(5)}, ${candidate.lon.toFixed(5)}`,
        signal: controller.signal,
      });
      if (!controller.signal.aborted) setPdfStatus("downloaded");
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setPdfStatus("error");
      setPdfError((err as Error).message || "The PDF exporter could not finish.");
    } finally {
      if (pdfAbortRef.current === controller) pdfAbortRef.current = null;
    }
  }, [candidate, pendingCard, setupPersona, setupRadiusKm]);

  const generateCommittedReport = useCallback(async () => {
    const selected = lastPointRef.current;
    if (!selected || !card) return;
    pdfAbortRef.current?.abort();
    const controller = new AbortController();
    pdfAbortRef.current = controller;
    setCommittedPdfStatus("generating");
    setCommittedPdfError(null);
    try {
      const { generateLocationReport } = await import("./lib/reportPdf");
      const committedPersona = (
        ["home_buyer", "tenant", "investor", "developer"] as string[]
      ).includes(card.persona?.key ?? "")
        ? (card.persona?.key as PersonaKey)
        : persona;
      await generateLocationReport({
        card,
        persona: committedPersona,
        lon: selected.lon,
        lat: selected.lat,
        radiusKm: analysisRadiusKm,
        placeLabel: placeLabel ?? `${selected.lat.toFixed(5)}, ${selected.lon.toFixed(5)}`,
        signal: controller.signal,
      });
      if (!controller.signal.aborted) setCommittedPdfStatus("downloaded");
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setCommittedPdfStatus("error");
      setCommittedPdfError((err as Error).message || "The PDF exporter could not finish.");
    } finally {
      if (pdfAbortRef.current === controller) pdfAbortRef.current = null;
    }
  }, [analysisRadiusKm, card, persona, placeLabel]);

  const changeAnalysisRadius = (radiusKm: number) => {
    analysisAbortRef.current?.abort();
    analysisRequestRef.current += 1;
    setUpdatingMessage(null);
    setAnalysisRadiusKm(radiusKm);
    saveAnalysisRadius(radiusKm);
  };

  const editCurrentAnalysis = () => {
    const last = lastPointRef.current;
    if (last) beginAnalysisSetup(last.lon, last.lat, last.label);
  };

  useEffect(() => {
    const last = lastPointRef.current;
    if (!last || !card || candidate) return;
    if (card.analysis_radius_m === analysisRadiusKm * 1_000) return;
    const timeout = window.setTimeout(() => {
      void runAnalyse(
        last.lon,
        last.lat,
        last.label,
        persona,
        analysisRadiusKm,
        true,
        `Updating results for ${analysisRadiusKm} km…`,
      );
    }, 600);
    return () => window.clearTimeout(timeout);
  }, [analysisRadiusKm, card, candidate, persona, runAnalyse]);

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
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
      "top-right",
    );

    const syncAutomatic3D = () => {
      const zoom = map.getZoom();
      if (zoom < AUTO_3D_EXIT_ZOOM) {
        suppressAuto3DRef.current = false;
        if (view3DRef.current) changeMapDimension(false);
      } else if (
        zoom >= AUTO_3D_ENTER_ZOOM &&
        !suppressAuto3DRef.current &&
        !view3DRef.current
      ) {
        changeMapDimension(true);
      }
    };
    map.on("zoomend", syncAutomatic3D);

    const resize = () => {
      if (!cancelled && mapRef.current) map.resize();
    };
    const resizeMarkers = () => resizePoiMarkers(map, poiMarkersRef.current);
    map.on("load", resize);
    map.on("zoom", resizeMarkers);
    map.on("error", (e) => {
      const msg = e.error?.message || "Map failed to load tiles";
      if (/Cannot style non-existing layer/i.test(msg)) return;
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
      map.off("zoomend", syncAutomatic3D);
      map.off("zoom", resizeMarkers);
      markerRef.current?.remove();
      markerRef.current = null;
      candidateMarkerRef.current?.remove();
      candidateMarkerRef.current = null;
      poiMarkersRef.current.forEach((marker) => marker.remove());
      poiMarkersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [changeMapDimension]);

  useEffect(() => {
    const map = mapRef.current;
    candidateMarkerRef.current?.remove();
    candidateMarkerRef.current = null;
    if (!map || !candidate) return;
    candidateMarkerRef.current = new maplibregl.Marker({ color: "#d97706" })
      .setLngLat([candidate.lon, candidate.lat])
      .addTo(map);
    return () => {
      candidateMarkerRef.current?.remove();
      candidateMarkerRef.current = null;
    };
  }, [candidate]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const syncBuffer = () => {
      if (!map.isStyleLoaded()) return;
      const point = candidate ?? lastPointRef.current;
      if (!point) {
        hideAnalysisBuffer(map);
        return;
      }
      showAnalysisBuffer(
        map,
        point.lon,
        point.lat,
        candidate ? setupRadiusKm : analysisRadiusKm,
        theme === "dark",
      );
    };
    syncBuffer();
    map.on("style.load", syncBuffer);
    return () => {
      map.off("style.load", syncBuffer);
    };
  }, [analysisRadiusKm, candidate, card, setupRadiusKm, theme]);

  // Keep click handler current without remounting the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const onClick = (e: maplibregl.MapMouseEvent) => {
      beginAnalysisSetup(e.lngLat.lng, e.lngLat.lat);
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [beginAnalysisSetup]);

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
      try {
        syncMap3DStyle(map, view3DRef.current);
      } catch (err) {
        setMapError(`3D map unavailable: ${(err as Error).message}`);
      }
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
    const syncLandCover = () => {
      if (!map.isStyleLoaded()) return;
      if (layerEnabled("land_cover")) showLandCoverLayer(map);
      else hideLandCoverLayer(map);
    };
    syncLandCover();
    map.on("style.load", syncLandCover);
    return () => {
      map.off("style.load", syncLandCover);
    };
  }, [basemapId, layers, layerEnabled]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const restore3D = () => {
      try {
        syncMap3DStyle(map, view3DRef.current);
      } catch (err) {
        setMapError(`3D map unavailable: ${(err as Error).message}`);
      }
    };
    if (map.isStyleLoaded()) restore3D();
    map.on("style.load", restore3D);
    return () => {
      map.off("style.load", restore3D);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let active = true;
    let requestId = 0;
    const enabled = layerEnabled("land_use");

    const syncLandUse = async () => {
      if (!active || !map.isStyleLoaded()) return;
      if (!enabled) {
        hideLandUseLayer(map);
        return;
      }
      const currentRequest = ++requestId;
      try {
        const bounds = map.getBounds();
        const data = await fetchLandUse([
          bounds.getWest(),
          bounds.getSouth(),
          bounds.getEast(),
          bounds.getNorth(),
        ]);
        if (
          !active ||
          currentRequest !== requestId ||
          mapRef.current !== map ||
          !map.isStyleLoaded()
        ) {
          return;
        }
        showLandUseLayer(map, data);
      } catch (err) {
        if (active) setMapError((err as Error).message);
      }
    };

    void syncLandUse();
    map.on("style.load", syncLandUse);
    map.on("moveend", syncLandUse);
    return () => {
      active = false;
      map.off("style.load", syncLandUse);
      map.off("moveend", syncLandUse);
    };
  }, [basemapId, layers, layerEnabled]);

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

    poiMarkersRef.current.forEach((marker) => marker.remove());
    poiMarkersRef.current = [];

    const amenityPois = nearbyFromScorecard(card?.domains.amenities?.evidence).filter((poi) => {
      const layerId = POI_LAYER_BY_CATEGORY[poi.category];
      return layerId ? layerEnabled(layerId) : false;
    });
    const securityPois = layerEnabled("security_poi")
      ? nearbyFromScorecard(card?.domains.security?.evidence)
      : [];

    for (const poi of [...amenityPois, ...securityPois]) {
      const element = document.createElement("button");
      element.type = "button";
      element.title = `${poi.name} · ${(poi.distance_m / 1000).toFixed(1)} km away`;
      element.setAttribute("aria-label", element.title);
      Object.assign(element.style, {
        width: "26px",
        height: "26px",
        borderRadius: "9999px",
        border: "2px solid white",
        backgroundColor: AMENITY_MARKER_COLORS[poi.category] ?? "#0d9488",
        boxShadow: "0 1px 5px rgba(15, 23, 42, 0.65)",
        cursor: "pointer",
        color: "white",
        display: "grid",
        placeItems: "center",
        padding: "0",
      });
      element.appendChild(createPoiSymbolElement(poi.category, 15));

      const popupContent = document.createElement("div");
      const popupName = document.createElement("strong");
      popupName.textContent = poi.name;
      const popupMeta = document.createElement("div");
      popupMeta.textContent = `${poi.category.replaceAll("_", " ")} · ${(poi.distance_m / 1000).toFixed(1)} km away`;
      popupContent.append(popupName, popupMeta);

      const marker = new maplibregl.Marker({ element, anchor: "center" })
        .setLngLat([poi.lon, poi.lat])
        .setPopup(new maplibregl.Popup({ offset: 12 }).setDOMContent(popupContent))
        .addTo(map);
      poiMarkersRef.current.push(marker);
    }
    resizePoiMarkers(map, poiMarkersRef.current);

    return () => {
      poiMarkersRef.current.forEach((marker) => marker.remove());
      poiMarkersRef.current = [];
    };
  }, [card, layers, layerEnabled]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    projectMarkersRef.current.forEach((marker) => marker.remove());
    projectMarkersRef.current = [];
    if (!layerEnabled("government_projects")) return;

    for (const project of mappedProjects(card)) {
      if (!project.geometry || project.geometry.type !== "Point") continue;
      const coordinates = project.geometry.coordinates as [number, number];
      const element = document.createElement("button");
      element.type = "button";
      element.title = `${project.name} · ${project.lifecycle_stage}`;
      element.setAttribute("aria-label", element.title);
      Object.assign(element.style, {
        width: "24px", height: "24px", borderRadius: "6px", border: "2px solid white",
        backgroundColor: "#d97706", boxShadow: "0 1px 5px rgba(15,23,42,.6)",
        cursor: "pointer", color: "white", fontSize: "13px", fontWeight: "700",
      });
      element.textContent = "P";
      const content = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = project.name;
      const meta = document.createElement("div");
      meta.textContent = `${project.lifecycle_stage} · ${project.sector}${project.distance_m != null ? ` · ${(project.distance_m / 1000).toFixed(1)} km` : ""}`;
      const source = document.createElement("a");
      source.href = project.source_url;
      source.target = "_blank";
      source.rel = "noreferrer";
      source.textContent = "Official source";
      content.append(title, meta, source);
      projectMarkersRef.current.push(
        new maplibregl.Marker({ element, anchor: "center" })
          .setLngLat(coordinates)
          .setPopup(new maplibregl.Popup({ offset: 12 }).setDOMContent(content))
          .addTo(map),
      );
    }
    return () => {
      projectMarkersRef.current.forEach((marker) => marker.remove());
      projectMarkersRef.current = [];
    };
  }, [card, layers, layerEnabled]);

  const toggleLayer = (id: OverlayLayerId) => {
    setLayers((prev) => prev.map((l) => (l.id === id ? { ...l, enabled: !l.enabled } : l)));
  };

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  const toggle3D = () => {
    const enabled = !view3DRef.current;
    suppressAuto3DRef.current = !enabled;
    changeMapDimension(enabled);
  };
  const dark = theme === "dark";
  const displayRadiusKm = candidate ? setupRadiusKm : analysisRadiusKm;
  const amenitiesSourceCard = candidate && pendingCard ? pendingCard : card;
  const nearbyAmenities = nearbyFromScorecard(amenitiesSourceCard?.domains.amenities?.evidence);
  const nearbyAmenityTotal =
    nearbyTotalFromScorecard(amenitiesSourceCard) || nearbyAmenities.length;
  const amenityCounts = nearbyCountsFromScorecard(amenitiesSourceCard);
  const legendCountsAreCurrent =
    !candidate && card?.analysis_radius_m === analysisRadiusKm * 1_000;
  const legendAmenityCounts = legendCountsAreCurrent
    ? amenityCounts
    : undefined;
  const amenitiesListTotal = amenitiesListCategory
    ? amenityCounts?.[amenitiesListCategory] ??
      nearbyAmenities.filter((item) => item.category === amenitiesListCategory).length
    : nearbyAmenityTotal;
  const securityCountValue = card?.domains.security?.evidence.nearby_count;
  const legendSecurityCount =
    legendCountsAreCurrent && typeof securityCountValue === "number"
      ? securityCountValue
      : undefined;
  const anyAmenityLayerEnabled = AMENITY_LAYER_IDS.some((id) => layerEnabled(id));
  const professionalReport = persona === "investor" || persona === "developer";
  const committedPoint = lastPointRef.current;
  const reportGuidePersona = (["home_buyer", "tenant", "investor", "developer"] as string[]).includes(
    card?.persona?.key ?? "",
  )
    ? (card?.persona?.key as PersonaKey)
    : persona;
  const visibleLayers = professionalReport
    ? layers
    : layers.filter((layer) => layer.id !== "government_projects");

  const openAmenitiesList = (category?: string) => {
    setAmenitiesListCategory(category ?? null);
    setAmenitiesListOpen(true);
  };

  const closeAmenitiesList = () => {
    setAmenitiesListOpen(false);
    setAmenitiesListCategory(null);
  };

  const focusNearby = (item: NearbyPoiItem) => {
    if (item.lon == null || item.lat == null) return;
    mapRef.current?.flyTo({
      center: [item.lon, item.lat],
      zoom: Math.max(mapRef.current.getZoom(), 15),
      duration: 900,
    });
    closeAmenitiesList();
  };

  const resetLocationAnalysis = () => {
    analysisAbortRef.current?.abort();
    analysisRequestRef.current += 1;
    pdfAbortRef.current?.abort();
    pdfAbortRef.current = null;
    lastPointRef.current = null;
    setCandidate(null);
    setAnalysisPhase("setup");
    setPendingCard(null);
    setAnalysisFlowError(null);
    setPdfStatus("idle");
    setPdfError(null);
    setCommittedPdfStatus("idle");
    setCommittedPdfError(null);
    markerRef.current?.remove();
    markerRef.current = null;
    candidateMarkerRef.current?.remove();
    candidateMarkerRef.current = null;
    poiMarkersRef.current.forEach((marker) => marker.remove());
    poiMarkersRef.current = [];
    projectMarkersRef.current.forEach((marker) => marker.remove());
    projectMarkersRef.current = [];

    setCard(null);
    setPlaceLabel(null);
    setLoading(false);
    setUpdatingMessage(null);
    setError(null);
    setAmenitiesListOpen(false);
    setAmenitiesListCategory(null);
    setReportGuideOpen(false);
    setProfessional3DOpen(false);
    setSearchResetKey((key) => key + 1);
    if (mapRef.current?.isStyleLoaded()) hideAnalysisBuffer(mapRef.current);

    suppressAuto3DRef.current = false;
    changeMapDimension(false, false);
    mapRef.current?.flyTo({
      center: FCT_CENTER,
      zoom: FCT_HOME_ZOOM,
      pitch: 0,
      bearing: 0,
      duration: 1000,
    });
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
        onSelectPlace={beginAnalysisSetup}
        locating={loading}
        persona={persona}
        onPersonaChange={onPersonaChange}
        searchResetKey={searchResetKey}
        reportGuideAvailable={Boolean(card)}
        onOpenReportGuide={() => setReportGuideOpen(true)}
        reportAvailable={Boolean(card && committedPoint && !candidate)}
        reportGenerating={committedPdfStatus === "generating"}
        onGenerateReport={() => void generateCommittedReport()}
      />

      {committedPdfError && (
        <div className="absolute right-4 top-20 z-50 max-w-sm rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 shadow-lg">
          Report export failed: {committedPdfError}
        </div>
      )}

      <div className="relative flex min-h-0 flex-1 flex-row">
        {desktopReportOpen && (
          <div className="hidden h-full w-[22rem] shrink-0 lg:block xl:w-96">
            <ScorecardConsole
              theme={theme}
              card={card}
              loading={loading}
              error={error}
              placeLabel={placeLabel}
              persona={persona}
              onClose={() => setDesktopReportOpen(false)}
              onReset={resetLocationAnalysis}
              onViewNearbyList={openAmenitiesList}
              radiusKm={analysisRadiusKm}
              radiusControlIdPrefix="desktop-scorecard"
              updatingMessage={updatingMessage}
              onRadiusChange={changeAnalysisRadius}
              onEditAnalysis={editCurrentAnalysis}
              onOpenProfessional3D={
                professionalReport && committedPoint
                  ? () => setProfessional3DOpen(true)
                  : undefined
              }
            />
          </div>
        )}

        <main className="relative h-full min-h-0 min-w-0 flex-1">
          <div ref={mapContainer} className="h-full w-full bg-slate-200" />

          {/* Flood Watch MapPanel layout: Legend bottom-left · Home+Basemap+Layers under zoom */}
          <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-[calc(100vw-5.5rem)] space-y-2 sm:max-w-none">
            {!desktopReportOpen && (
              <div className="pointer-events-auto hidden lg:block">
                <button
                  type="button"
                  onClick={() => setDesktopReportOpen(true)}
                  className={clsx(
                    "inline-flex items-center rounded-xl border px-3 py-2 text-[11px] font-semibold shadow-lg transition",
                    dark
                      ? "border-gray-700 bg-gray-900 text-sky-300 hover:bg-gray-800"
                      : "border-slate-200 bg-white text-sky-800 hover:border-slate-300",
                  )}
                  aria-label="Open location report"
                >
                  Open report
                </button>
              </div>
            )}
            {nearbyAmenities.length > 0 && anyAmenityLayerEnabled && (
              <div className="pointer-events-auto">
                <button
                  type="button"
                  onClick={() => openAmenitiesList()}
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[11px] font-semibold shadow-lg",
                    dark
                      ? "border-gray-700 bg-gray-900 text-sky-300 hover:bg-gray-800"
                      : "border-slate-200 bg-white text-sky-800 hover:border-slate-300",
                  )}
                >
                  View amenities · {nearbyAmenityTotal}
                </button>
              </div>
            )}
          </div>

          <div className="pointer-events-none absolute top-[7rem] right-3 z-10 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => {
                suppressAuto3DRef.current = false;
                changeMapDimension(false, false);
                mapRef.current?.flyTo({
                  center: FCT_CENTER,
                  zoom: FCT_HOME_ZOOM,
                  pitch: 0,
                  bearing: 0,
                  duration: 1000,
                });
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
              <Map3DControl theme={theme} enabled={view3D} onToggle={toggle3D} />
            </div>
            <div className="pointer-events-auto">
              <BasemapSwitcher theme={theme} activeId={basemapId} onChange={setBasemapId} />
            </div>
            <div className="pointer-events-auto">
              <LayersPanel
                theme={theme}
                layers={visibleLayers}
                onToggle={toggleLayer}
                radiusKm={displayRadiusKm}
              />
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
              <MapLegend
                theme={theme}
                layers={visibleLayers}
                radiusKm={displayRadiusKm}
                amenityCounts={legendAmenityCounts}
                securityCount={legendSecurityCount}
                analysisVisible={Boolean(card && committedPoint && !candidate)}
              />
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
              onReset={resetLocationAnalysis}
              onViewNearbyList={openAmenitiesList}
              radiusKm={analysisRadiusKm}
              radiusControlIdPrefix="mobile-scorecard"
              updatingMessage={updatingMessage}
              onRadiusChange={changeAnalysisRadius}
              onEditAnalysis={editCurrentAnalysis}
              onOpenProfessional3D={
                professionalReport && committedPoint
                  ? () => setProfessional3DOpen(true)
                  : undefined
              }
            />
          </div>
        </div>
      </div>

      <NearbyAmenitiesList
        theme={theme}
        items={nearbyAmenities}
        open={amenitiesListOpen}
        category={amenitiesListCategory}
        elevated={Boolean(candidate && pendingCard)}
        radiusKm={candidate && pendingCard ? setupRadiusKm : analysisRadiusKm}
        totalCount={amenitiesListTotal}
        onClose={closeAmenitiesList}
        onSelect={focusNearby}
      />

      <AnalysisSetupDialog
        theme={theme}
        candidate={candidate}
        persona={setupPersona}
        radiusKm={setupRadiusKm}
        phase={analysisPhase}
        pendingCard={pendingCard}
        analysisError={analysisFlowError}
        pdfStatus={pdfStatus}
        pdfError={pdfError}
        onPersonaChange={setSetupPersona}
        onRadiusChange={changeSetupRadius}
        onCancel={cancelAnalysisSetup}
        onAnalyse={confirmAnalysisSetup}
        onRetry={() => void analyseCandidate()}
        onGenerateReport={() => void generatePendingReport()}
        onViewMap={viewCandidateOnMap}
        onViewNearbyList={openAmenitiesList}
      />

      {card && (
        <ReportGuideDialog
          open={reportGuideOpen}
          theme={theme}
          card={card}
          persona={reportGuidePersona}
          placeLabel={placeLabel}
          onClose={closeReportGuide}
        />
      )}

      {card && committedPoint && professionalReport && (
        <Professional3DDialog
          open={professional3DOpen}
          theme={theme}
          card={card}
          persona={persona}
          lon={committedPoint.lon}
          lat={committedPoint.lat}
          radiusKm={analysisRadiusKm}
          placeLabel={placeLabel ?? `${committedPoint.lat.toFixed(5)}, ${committedPoint.lon.toFixed(5)}`}
          onClose={() => setProfessional3DOpen(false)}
        />
      )}

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
