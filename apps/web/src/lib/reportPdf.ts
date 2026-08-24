import maplibregl from "maplibre-gl";
import type { jsPDF } from "jspdf";
import { DOMAIN_ORDER, fetchLandUse, type Scorecard } from "../api";
import { AMENITY_MARKER_COLORS, nearbyFromScorecard } from "./amenitiesMap";
import { analysisBufferBounds, showAnalysisBuffer } from "./analysisBufferMap";
import { getBasemap } from "./basemap";
import { showLandCoverLayer } from "./landCoverMap";
import { LAND_USE_COLORS, showLandUseLayer } from "./landUseMap";
import { getPersona, type PersonaKey } from "./personas";
import { mappedProjects } from "./projectsMap";
import { buildNextSteps } from "./reportGuide";

export type LocationReportInput = {
  card: Scorecard;
  persona: PersonaKey;
  lon: number;
  lat: number;
  radiusKm: number;
  placeLabel: string;
  reportTitle?: string;
  signal?: AbortSignal;
};

export type GeneratedLocationReport = {
  blob: Blob;
  filename: string;
};

type ReportMapPoint = {
  category: string;
  label: string;
  lon: number;
  lat: number;
  color: string;
  priority: number;
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

const CATEGORY_LABELS: Record<string, string> = {
  school: "School",
  hospital: "Health",
  market: "Market",
  bank: "Bank",
  power: "Power",
  fuel: "Fuel",
  police: "Police",
  project: "Public project",
};

const LAND_COVER_COLORS: Record<string, string> = {
  tree_cover: "#006400",
  shrubland: "#ffbb22",
  grassland: "#ffff4c",
  cropland: "#f096ff",
  built_up: "#fa0000",
  bare_sparse_vegetation: "#b4b4b4",
  permanent_water: "#0064c8",
  herbaceous_wetland: "#0096a0",
};

function cleanText(value: string): string {
  return value
    .replace(/[–—]/g, "-")
    .replace(/·/g, "-")
    .replace(/°/g, " deg")
    .replace(/₦/g, "NGN ")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[^\x20-\x7E\n]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function truncate(value: string, max: number): string {
  const text = cleanText(value);
  return text.length <= max ? text : `${text.slice(0, Math.max(0, max - 3)).trim()}...`;
}

function safeFilename(value: string): string {
  return cleanText(value)
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 70) || "Location";
}

function abortError(): DOMException {
  return new DOMException("Report generation was cancelled.", "AbortError");
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw abortError();
}

function waitForMapIdle(
  map: maplibregl.Map,
  signal?: AbortSignal,
  timeoutMs = 20_000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("Map tiles did not finish loading. Check your connection and try again."));
    }, timeoutMs);
    const onIdle = () => {
      cleanup();
      resolve();
    };
    const onAbort = () => {
      cleanup();
      reject(abortError());
    };
    const cleanup = () => {
      window.clearTimeout(timeout);
      map.off("idle", onIdle);
      signal?.removeEventListener("abort", onAbort);
    };
    map.on("idle", onIdle);
    signal?.addEventListener("abort", onAbort, { once: true });
    if (signal?.aborted) onAbort();
  });
}

function selectMapPoints(card: Scorecard, professional: boolean): ReportMapPoint[] {
  const amenities = nearbyFromScorecard(card.domains.amenities?.evidence)
    .sort((left, right) => left.distance_m - right.distance_m);
  const nearestByCategory = new Map<string, (typeof amenities)[number]>();
  for (const amenity of amenities) {
    if (!nearestByCategory.has(amenity.category)) nearestByCategory.set(amenity.category, amenity);
  }
  const selected: ReportMapPoint[] = [...nearestByCategory.values()]
    .slice(0, 7)
    .map((amenity, index) => ({
      category: amenity.category,
      label: truncate(amenity.name, 26),
      lon: amenity.lon,
      lat: amenity.lat,
      color: AMENITY_MARKER_COLORS[amenity.category] ?? "#0d9488",
      priority: 10 + index,
    }));

  const police = nearbyFromScorecard(card.domains.security?.evidence)
    .sort((left, right) => left.distance_m - right.distance_m)
    .slice(0, 2);
  selected.push(
    ...police.map((item, index) => ({
      category: "police",
      label: truncate(item.name, 26),
      lon: item.lon,
      lat: item.lat,
      color: AMENITY_MARKER_COLORS.police,
      priority: 2 + index,
    })),
  );

  if (professional) {
    selected.push(
      ...mappedProjects(card)
        .slice(0, 3)
        .flatMap((project, index): ReportMapPoint[] => {
          if (project.geometry?.type !== "Point") return [];
          const [lon, lat] = project.geometry.coordinates;
          if (typeof lon !== "number" || typeof lat !== "number") return [];
          return [{
            category: "project",
            label: truncate(project.name, 28),
            lon,
            lat,
            color: "#d97706",
            priority: 5 + index,
          }];
        }),
    );
  }
  return selected;
}

function pointsToGeoJson(points: ReportMapPoint[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: points.map((point, index) => ({
      type: "Feature",
      id: index,
      properties: {
        category: point.category,
        label: point.label,
        marker: String(index + 1),
        color: point.color,
        priority: point.priority,
      },
      geometry: { type: "Point", coordinates: [point.lon, point.lat] },
    })),
  };
}

function drawMapCaption(
  canvas: HTMLCanvasElement,
  container: HTMLDivElement,
  input: LocationReportInput,
  points: ReportMapPoint[],
): string {
  const output = document.createElement("canvas");
  output.width = 1200;
  output.height = 675;
  const context = output.getContext("2d");
  if (!context) throw new Error("The browser could not prepare the report image.");
  context.drawImage(canvas, 0, 0, output.width, output.height);

  context.fillStyle = "rgba(255,255,255,0.95)";
  context.fillRect(20, 18, 690, 112);
  context.fillStyle = "#0f172a";
  context.font = "bold 23px Arial";
  context.fillText(truncate(input.placeLabel, 51), 36, 46);
  context.fillStyle = "#475569";
  context.font = "17px Arial";
  context.fillText(`${input.radiusKm} km analysis area - planning, land cover and nearby evidence`, 36, 69);

  const landUse = input.card.location.land_use;
  const landCover = input.card.location.land_cover;
  context.fillStyle = landUse ? LAND_USE_COLORS[landUse.category] ?? LAND_USE_COLORS.other : "#94a3b8";
  context.fillRect(36, 83, 14, 14);
  context.fillStyle = "#0f172a";
  context.font = "bold 14px Arial";
  context.fillText(
    truncate(`Land-use reference: ${landUse?.label ?? "No mapped class at selected point"}`, 70),
    58,
    95,
  );
  context.fillStyle = landCover ? LAND_COVER_COLORS[landCover.category] ?? "#94a3b8" : "#94a3b8";
  context.fillRect(36, 105, 14, 14);
  context.fillStyle = "#0f172a";
  context.font = "bold 14px Arial";
  context.fillText(
    truncate(`Observed land cover: ${landCover?.label ?? "Unavailable at selected point"}`, 70),
    58,
    117,
  );

  const labelledPoints = points.slice(0, 12);
  if (labelledPoints.length) {
    const rows = Math.ceil(labelledPoints.length / 2);
    const panelHeight = 31 + rows * 24;
    const panelX = 826;
    context.fillStyle = "rgba(255,255,255,0.95)";
    context.fillRect(panelX, 18, 354, panelHeight);
    context.fillStyle = "#0f172a";
    context.font = "bold 16px Arial";
    context.fillText("Nearby evidence", panelX + 16, 42);
    labelledPoints.forEach((point, index) => {
      const column = index % 2;
      const row = Math.floor(index / 2);
      const x = panelX + 18 + column * 168;
      const y = 68 + row * 24;
      context.fillStyle = point.color;
      context.beginPath();
      context.arc(x, y - 5, 8, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = "#ffffff";
      context.font = "bold 11px Arial";
      context.textAlign = "center";
      context.fillText(String(index + 1), x, y - 1);
      context.textAlign = "left";
      context.fillStyle = "#334155";
      context.font = "13px Arial";
      const category = CATEGORY_LABELS[point.category] ?? point.category;
      context.fillText(truncate(`${category}: ${point.label}`, 22), x + 13, y);
    });
  }

  const scaleElement = container.querySelector<HTMLElement>(".maplibregl-ctrl-scale");
  const scaleWidth = Math.max(80, Math.min(260, scaleElement?.offsetWidth ?? 140));
  const scaleLabel = cleanText(scaleElement?.textContent ?? "Map scale");
  const scaleX = 28;
  const scaleY = output.height - 42;
  context.fillStyle = "rgba(255,255,255,0.95)";
  context.fillRect(scaleX - 8, scaleY - 30, scaleWidth + 16, 44);
  context.strokeStyle = "#0f172a";
  context.lineWidth = 3;
  context.beginPath();
  context.moveTo(scaleX, scaleY);
  context.lineTo(scaleX + scaleWidth, scaleY);
  context.moveTo(scaleX, scaleY - 8);
  context.lineTo(scaleX, scaleY + 2);
  context.moveTo(scaleX + scaleWidth, scaleY - 8);
  context.lineTo(scaleX + scaleWidth, scaleY + 2);
  context.stroke();
  context.fillStyle = "#0f172a";
  context.font = "bold 16px Arial";
  context.fillText(scaleLabel, scaleX, scaleY - 11);

  const coverSource = truncate(input.card.location.land_cover?.source ?? "observed-cover source unavailable", 28);
  const attribution = `Map (c) OpenStreetMap/CARTO - cover: ${coverSource} - land use: reference only`;
  context.font = "14px Arial";
  const attributionWidth = context.measureText(attribution).width;
  context.fillStyle = "rgba(255,255,255,0.95)";
  context.fillRect(
    output.width - attributionWidth - 28,
    output.height - 34,
    attributionWidth + 18,
    24,
  );
  context.fillStyle = "#334155";
  context.fillText(attribution, output.width - attributionWidth - 19, output.height - 17);
  return output.toDataURL("image/png", 1);
}

async function captureStandardMap(input: LocationReportInput): Promise<string> {
  throwIfAborted(input.signal);
  const professional = input.persona === "investor" || input.persona === "developer";
  const points = selectMapPoints(input.card, professional);
  const reportBounds = analysisBufferBounds(input.lon, input.lat, input.radiusKm) as [
    [number, number],
    [number, number],
  ];
  const landUseRequest = fetchLandUse([
    reportBounds[0][0],
    reportBounds[0][1],
    reportBounds[1][0],
    reportBounds[1][1],
  ]).catch(() => null);
  const container = document.createElement("div");
  Object.assign(container.style, {
    position: "fixed",
    left: "-10000px",
    top: "0",
    width: "1200px",
    height: "675px",
    pointerEvents: "none",
    background: "#e2e8f0",
  });
  document.body.appendChild(container);

  const map = new maplibregl.Map({
    container,
    style: getBasemap("positron").style,
    center: [input.lon, input.lat],
    zoom: 10,
    bearing: 0,
    pitch: 0,
    interactive: false,
    attributionControl: false,
    preserveDrawingBuffer: true,
  });
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 220, unit: "metric" }), "bottom-left");

  try {
    await new Promise<void>((resolve, reject) => {
      const cleanup = () => {
        window.clearTimeout(timeout);
        input.signal?.removeEventListener("abort", onAbort);
        map.off("load", onLoad);
      };
      const onLoad = () => {
        cleanup();
        resolve();
      };
      const onAbort = () => {
        cleanup();
        reject(abortError());
      };
      const timeout = window.setTimeout(() => {
        cleanup();
        reject(new Error("The export map could not start. Please try again."));
      }, 12_000);
      map.on("load", onLoad);
      input.signal?.addEventListener("abort", onAbort, { once: true });
      if (input.signal?.aborted) onAbort();
    });
    throwIfAborted(input.signal);
    map.fitBounds(reportBounds, {
      padding: 72,
      duration: 0,
      bearing: 0,
      pitch: 0,
    });
    showLandCoverLayer(map);
    const landUseData = await landUseRequest;
    if (landUseData?.features.length) showLandUseLayer(map, landUseData);
    showAnalysisBuffer(map, input.lon, input.lat, input.radiusKm, false);

    if (points.length) {
      map.addSource("report-context", { type: "geojson", data: pointsToGeoJson(points) });
      map.addLayer({
        id: "report-context-points",
        type: "circle",
        source: "report-context",
        paint: {
          "circle-radius": 7,
          "circle-color": ["get", "color"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "report-context-labels",
        type: "symbol",
        source: "report-context",
        layout: {
          "text-field": ["get", "marker"],
          "text-size": 10,
          "text-allow-overlap": true,
          "text-ignore-placement": true,
          "symbol-sort-key": ["get", "priority"],
        },
        paint: {
          "text-color": "#ffffff",
          "text-halo-color": "rgba(15,23,42,0.5)",
          "text-halo-width": 0.5,
        },
      });
    }

    map.addSource("report-location", {
      type: "geojson",
      data: {
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [input.lon, input.lat] },
      },
    });
    map.addLayer({
      id: "report-location-ring",
      type: "circle",
      source: "report-location",
      paint: {
        "circle-radius": 12,
        "circle-color": "#ffffff",
        "circle-stroke-color": "#075985",
        "circle-stroke-width": 4,
      },
    });
    map.addLayer({
      id: "report-location-dot",
      type: "circle",
      source: "report-location",
      paint: { "circle-radius": 5, "circle-color": "#0369a1" },
    });
    map.triggerRepaint();
    try {
      await waitForMapIdle(map, input.signal, 12_000);
    } catch (error) {
      if ((error as Error).name === "AbortError") throw error;
      await new Promise<void>((resolve) => window.setTimeout(resolve, 750));
    }
    throwIfAborted(input.signal);
    return drawMapCaption(map.getCanvas(), container, input, points);
  } finally {
    map.remove();
    container.remove();
  }
}

function drawWrappedText(
  doc: jsPDF,
  text: string,
  x: number,
  y: number,
  width: number,
  lineHeight = 4,
  maxLines = 4,
): number {
  const lines = doc.splitTextToSize(cleanText(text), width).slice(0, maxLines) as string[];
  doc.text(lines, x, y);
  return y + Math.max(1, lines.length) * lineHeight;
}

function personaFitOpening(input: LocationReportInput): string {
  const score = input.card.fit_score == null ? "an unscored result" : `a ${input.card.fit_score.toFixed(0)}/100 fit score`;
  if (input.persona === "tenant") {
    return `For a tenant, ${score} reflects the likely day-to-day experience: rent burden, access to essentials, safety, travel, environmental comfort and local hazards.`;
  }
  if (input.persona === "home_buyer") {
    return `For a home buyer, ${score} balances long-term liveability, purchase cost, safety, access, environmental comfort and property-specific risk.`;
  }
  if (input.persona === "investor") {
    return `For an investor, ${score} weighs market evidence, demand access, planning context, infrastructure, environmental risk and the conditions that could affect income or exit value.`;
  }
  return `For a developer, ${score} combines planning context, buildable terrain, drainage and flood evidence, servicing, access, market demand and delivery risk at this site.`;
}

function landUseMeaning(input: LocationReportInput): string {
  const landUse = input.card.location.land_use;
  const status = landUse?.designation === "official_masterplan" ? "official planning class" : "mapped reference only";
  if (!landUse) {
    if (input.persona === "tenant") return "No mapped land-use class intersects the point, so confirm that the building is approved for residential occupation and inspect surrounding activity and noise.";
    if (input.persona === "home_buyer") return "No mapped land-use class intersects the point; verify permitted use, title, building approval and the current AGIS/FCTA record before purchase.";
    if (input.persona === "investor") return "No mapped land-use class intersects the point, so do not assume a rental or redevelopment use is permitted; obtain the current official planning and title record.";
    return "No mapped land-use class intersects the point; treat permitted use, density, setbacks, title and development controls as unresolved until AGIS/FCTA verification.";
  }
  if (input.persona === "tenant") return `The point is mapped as ${landUse.label} (${status}); consider whether that use supports quiet residential occupation, suitable access and the services you need.`;
  if (input.persona === "home_buyer") return `The point is mapped as ${landUse.label} (${status}); confirm that the home, title and intended long-term use align with the current official plan.`;
  if (input.persona === "investor") return `The point is mapped as ${landUse.label} (${status}); test whether the intended letting, resale or redevelopment strategy is permitted and commercially aligned with that use.`;
  return `The point is mapped as ${landUse.label} (${status}); verify permitted use, density, setbacks, access and title before site design or acquisition.`;
}

function landCoverMeaning(input: LocationReportInput): string {
  const cover = input.card.location.land_cover;
  if (!cover) return "Observed land cover is unavailable at the selected point, so current surface conditions require site inspection.";
  const category = cover.category;
  if (input.persona === "tenant") {
    if (category === "tree_cover") return `Satellite imagery observes ${cover.label}, which may support shade and comfort; inspect lighting, dampness, access and maintenance in person.`;
    if (category === "built_up") return `Satellite imagery observes ${cover.label}; check heat, noise, ventilation, drainage and open-space access during a viewing.`;
    return `Satellite imagery observes ${cover.label}; use it as environmental context and inspect shade, heat, drainage, dust and access in person.`;
  }
  if (input.persona === "home_buyer") {
    if (category === "tree_cover") return `Satellite imagery observes ${cover.label}, potentially improving shade and neighbourhood comfort; confirm drainage, tree condition and building access.`;
    if (category === "built_up") return `Satellite imagery observes ${cover.label}; assess heat, drainage capacity, privacy, open space and future alteration constraints.`;
    return `Satellite imagery observes ${cover.label}; assess what that means for drainage, heat, access, maintenance and long-term liveability.`;
  }
  if (["permanent_water", "herbaceous_wetland"].includes(category)) {
    return `Satellite imagery observes ${cover.label}; this is not zoning, but it raises the priority of surveyed drainage, flood, ground-condition and buildability checks.`;
  }
  if (category === "tree_cover") return `Satellite imagery observes ${cover.label}; quantify clearance, ecological constraints, access, drainage and the genuinely buildable footprint before underwriting.`;
  if (category === "built_up") return `Satellite imagery observes ${cover.label}; verify existing structures, demolition or retrofit cost, servicing capacity, access and redevelopment constraints.`;
  return `Satellite imagery observes ${cover.label}; translate this into clearance, earthworks, drainage, access, servicing and buildable-area assumptions before underwriting.`;
}

function detailedOverview(input: LocationReportInput): string {
  const positive = (input.card.highlights ?? []).filter((item) => item.tone === "positive")[0];
  const caution = (input.card.highlights ?? []).find((item) => item.tone !== "positive");
  const evidence = [
    positive ? `A key advantage is ${positive.title.toLowerCase()}: ${positive.text}` : null,
    caution ? `The main caution is ${caution.title.toLowerCase()}: ${caution.text}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  return truncate(
    `${personaFitOpening(input)} ${evidence} ${landUseMeaning(input)} ${landCoverMeaning(input)} Nearby services use the selected ${input.radiusKm} km radius; land use and observed cover stay tied to the selected point.`,
    1_050,
  );
}

function domainLine(card: Scorecard, domain: string): { title: string; detail: string } | null {
  const result = card.domains[domain];
  if (!result) return null;
  const score = result.score == null
    ? "Unavailable"
    : domain === "flood"
      ? `${result.score.toFixed(0)} hazard index`
      : `${result.score.toFixed(0)}`;
  const limited = result.status === "demo" || result.status === "degraded"
    ? "limited evidence"
    : result.included_in_fit
      ? "used in fit"
      : "context only";
  return {
    title: DOMAIN_LABELS[domain] ?? cleanText(domain),
    detail: `${score} - ${result.rating ?? limited} - ${result.confidence} confidence`,
  };
}

function drawSinglePage(doc: jsPDF, input: LocationReportInput, mapImage: string): void {
  const persona = getPersona(input.persona);
  const pageWidth = 297;
  doc.setFillColor(3, 105, 161);
  doc.rect(0, 0, pageWidth, 18, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.text("PropInsight", 12, 8);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.text("FCT location intelligence", 12, 13);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text(truncate(input.reportTitle || `${persona.label} location report`, 78), 285, 8, { align: "right" });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.text(new Date().toLocaleDateString("en-GB"), 285, 13, { align: "right" });

  doc.setTextColor(15, 23, 42);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.text(truncate(input.reportTitle || input.placeLabel, 90), 12, 27);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(71, 85, 105);
  doc.text(
    `${truncate(input.placeLabel, 48)} - ${persona.label} - ${input.radiusKm} km radius - ${input.lat.toFixed(5)}, ${input.lon.toFixed(5)}`,
    12,
    33,
  );

  doc.setFillColor(240, 249, 255);
  doc.roundedRect(12, 38, 273, 42, 3, 3, "F");
  doc.setTextColor(3, 105, 161);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(25);
  doc.text(input.card.fit_score != null ? input.card.fit_score.toFixed(0) : "-", 20, 57);
  doc.setFontSize(7.5);
  doc.text("FIT / 100", 20, 65);
  doc.setTextColor(15, 23, 42);
  doc.setFontSize(10.5);
  doc.text(`What this means for ${persona.label}`, 48, 47);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.2);
  drawWrappedText(doc, detailedOverview(input), 48, 53, 229, 4.1, 6);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10.5);
  doc.text("Location, planning and nearby evidence", 12, 86);
  doc.addImage(mapImage, "PNG", 12, 90, 174, 97.875, undefined, "FAST");

  const columnX = 193;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10.5);
  doc.text("Scorecard at a glance", columnX, 86);
  const domains = input.card.domain_priority?.length
    ? input.card.domain_priority
    : [...DOMAIN_ORDER];
  let y = 92;
  for (const domain of domains.slice(0, 6)) {
    const line = domainLine(input.card, domain);
    if (!line) continue;
    doc.setFillColor(248, 250, 252);
    doc.setDrawColor(226, 232, 240);
    doc.roundedRect(columnX, y, 92, 9.2, 1.5, 1.5, "FD");
    doc.setTextColor(15, 23, 42);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(7.7);
    doc.text(line.title, columnX + 3, y + 4);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(6.6);
    doc.setTextColor(71, 85, 105);
    doc.text(truncate(line.detail, 62), columnX + 3, y + 7.4);
    y += 10.5;
  }

  y += 2;
  doc.setTextColor(15, 23, 42);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10.5);
  doc.text("Priority checks", columnX, y);
  y += 6;
  const steps = buildNextSteps(input.card, input.persona).slice(0, 3);
  steps.forEach((step, index) => {
    doc.setFillColor(step.urgency === "important" ? 220 : 3, step.urgency === "important" ? 38 : 105, step.urgency === "important" ? 38 : 161);
    doc.circle(columnX + 3, y - 1.2, 2.2, "F");
    doc.setTextColor(255, 255, 255);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(6.6);
    doc.text(String(index + 1), columnX + 3, y - 0.5, { align: "center" });
    doc.setTextColor(15, 23, 42);
    doc.setFontSize(7.5);
    doc.text(truncate(step.title, 56), columnX + 8, y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(6.5);
    doc.setTextColor(71, 85, 105);
    y = drawWrappedText(doc, truncate(step.detail, 120), columnX + 8, y + 3.5, 83, 3.2, 2) + 2.5;
  });

  doc.setDrawColor(203, 213, 225);
  doc.line(12, 196, 285, 196);
  doc.setTextColor(71, 85, 105);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(6.5);
  const versions = Object.entries(input.card.layer_versions)
    .slice(0, 6)
    .map(([key, value]) => `${key} ${value}`)
    .join("; ");
  doc.text(truncate(`Data: ${versions || "See the interactive report for source versions."}`, 185), 12, 201);
  doc.text(
    "Advisory location intelligence only - not legal, planning, engineering, valuation, or commercial approval.",
    285,
    201,
    { align: "right" },
  );
}

export async function buildLocationReport(input: LocationReportInput): Promise<GeneratedLocationReport> {
  throwIfAborted(input.signal);
  const mapImage = await captureStandardMap(input);
  throwIfAborted(input.signal);
  const { jsPDF: JsPdf } = await import("jspdf");
  throwIfAborted(input.signal);
  const doc = new JsPdf({ orientation: "landscape", unit: "mm", format: "a4", compress: true });
  drawSinglePage(doc, input, mapImage);
  const date = new Date().toISOString().slice(0, 10);
  const filename = `PropInsight-${safeFilename(input.reportTitle || input.placeLabel)}-${safeFilename(getPersona(input.persona).label)}-${date}.pdf`;
  throwIfAborted(input.signal);
  return { blob: doc.output("blob"), filename };
}

export function downloadLocationReport(report: GeneratedLocationReport): void {
  const url = URL.createObjectURL(report.blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = report.filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

export async function generateLocationReport(input: LocationReportInput): Promise<GeneratedLocationReport> {
  const report = await buildLocationReport(input);
  downloadLocationReport(report);
  return report;
}
