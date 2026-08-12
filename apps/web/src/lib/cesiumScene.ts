import "cesium/Build/Cesium/Widgets/widgets.css";
import * as Cesium from "cesium";
import {
  fetchLandUse,
  fetchProfessionalBuildings,
  fetchProfessionalVegetation,
  type Professional3DFeatureCollection,
  type Scorecard,
} from "../api";
import { AMENITY_MARKER_COLORS, nearbyFromScorecard } from "./amenitiesMap";
import { analysisBufferBounds } from "./analysisBufferMap";
import { LAND_USE_COLORS } from "./landUseMap";
import { mappedProjects } from "./projectsMap";

export type Professional3DMode = "analytical" | "photorealistic";

export type Professional3DFeature = {
  kind: "building" | "vegetation";
  title: string;
  properties: Record<string, unknown>;
};

export type Professional3DLayerStatus = {
  available: boolean;
  featureCount: number;
  totalCount: number;
  truncated: boolean;
  advisory: string;
};

export type Professional3DInput = {
  card: Scorecard;
  lon: number;
  lat: number;
  radiusKm: number;
  placeLabel: string;
  signal?: AbortSignal;
  onFeatureSelect?: (feature: Professional3DFeature | null) => void;
};

export type Professional3DScene = {
  terrainEnabled: boolean;
  terrainLabel: string;
  terrainExaggeration: number;
  buildingsEnabled: boolean;
  vegetationEnabled: boolean;
  photorealisticAvailable: boolean;
  buildingStatus: Professional3DLayerStatus;
  vegetationStatus: Professional3DLayerStatus;
  warnings: string[];
  resetView: () => void;
  setMode: (mode: Professional3DMode) => Promise<{ mode: Professional3DMode; warning?: string }>;
  setLandCoverVisible: (visible: boolean) => void;
  setLandUseVisible: (visible: boolean) => void;
  setEvidenceVisible: (visible: boolean) => void;
  setBuildingsVisible: (visible: boolean) => void;
  setVegetationVisible: (visible: boolean) => void;
  destroy: () => void;
};

const LAND_COVER_BOUNDS = Cesium.Rectangle.fromDegrees(6.77, 8.41, 7.73, 9.42);
const EMPTY_LAYER_STATUS: Professional3DLayerStatus = {
  available: false,
  featureCount: 0,
  totalCount: 0,
  truncated: false,
  advisory: "Layer unavailable.",
};

function siteBounds(input: Professional3DInput): [number, number, number, number] {
  const bounds = analysisBufferBounds(input.lon, input.lat, Math.min(input.radiusKm, 3)) as [
    [number, number],
    [number, number],
  ];
  return [bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]];
}

function colour(value: string, alpha = 1): Cesium.Color {
  return Cesium.Color.fromCssColorString(value).withAlpha(alpha);
}

type TerrainTileJson = {
  tiles?: string[];
  tileSize?: number;
  encoding?: string;
  attribution?: string;
};

const TERRAIN_SAMPLE_SIZE = 65;
const RASTER_TERRAIN_MAX_LEVEL = 12;

async function decodeTerrariumTile(
  url: string,
  sourceTileSize: number,
  childX = 0,
  childY = 0,
  childGridSize = 1,
): Promise<Float32Array> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Terrain tile request failed (${response.status}).`);
  const bitmap = await createImageBitmap(await response.blob());
  const canvas = document.createElement("canvas");
  canvas.width = sourceTileSize;
  canvas.height = sourceTileSize;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    bitmap.close();
    throw new Error("Terrain decoding is unavailable in this browser.");
  }
  context.drawImage(bitmap, 0, 0, sourceTileSize, sourceTileSize);
  bitmap.close();
  const pixels = context.getImageData(0, 0, sourceTileSize, sourceTileSize).data;
  const heights = new Float32Array(TERRAIN_SAMPLE_SIZE * TERRAIN_SAMPLE_SIZE);
  for (let row = 0; row < TERRAIN_SAMPLE_SIZE; row += 1) {
    const sourceV = (childY + row / (TERRAIN_SAMPLE_SIZE - 1)) / childGridSize;
    const sourceRow = Math.round(sourceV * (sourceTileSize - 1));
    for (let column = 0; column < TERRAIN_SAMPLE_SIZE; column += 1) {
      const sourceU = (childX + column / (TERRAIN_SAMPLE_SIZE - 1)) / childGridSize;
      const sourceColumn = Math.round(sourceU * (sourceTileSize - 1));
      const sourceIndex = (sourceRow * sourceTileSize + sourceColumn) * 4;
      heights[row * TERRAIN_SAMPLE_SIZE + column] =
        pixels[sourceIndex] * 256 + pixels[sourceIndex + 1] + pixels[sourceIndex + 2] / 256 - 32_768;
    }
  }
  return heights;
}

async function createRasterTerrainProvider(): Promise<Cesium.CustomHeightmapTerrainProvider> {
  const tileJsonUrl = import.meta.env.VITE_TERRAIN_TILEJSON_URL?.trim()
    || "https://tiles.mapterhorn.com/tilejson.json";
  const response = await fetch(tileJsonUrl);
  if (!response.ok) throw new Error(`Terrain metadata request failed (${response.status}).`);
  const metadata = await response.json() as TerrainTileJson;
  if (metadata.encoding !== "terrarium" || !metadata.tiles?.length) {
    throw new Error("The configured raster terrain source is not Terrarium-compatible.");
  }
  const sourceTileSize = metadata.tileSize ?? 512;
  const template = new URL(metadata.tiles[0], tileJsonUrl).toString();
  const cache = new Map<string, Promise<Float32Array>>();
  return new Cesium.CustomHeightmapTerrainProvider({
    width: TERRAIN_SAMPLE_SIZE,
    height: TERRAIN_SAMPLE_SIZE,
    tilingScheme: new Cesium.WebMercatorTilingScheme(),
    credit: metadata.attribution ?? "Mapterhorn terrain",
    callback: (x, y, level) => {
      const key = `${level}/${x}/${y}`;
      const cached = cache.get(key);
      if (cached) return cached;
      const sourceLevel = Math.min(level, RASTER_TERRAIN_MAX_LEVEL);
      const childGridSize = 2 ** (level - sourceLevel);
      const sourceX = Math.floor(x / childGridSize);
      const sourceY = Math.floor(y / childGridSize);
      const childX = x - sourceX * childGridSize;
      const childY = y - sourceY * childGridSize;
      const url = template
        .replace("{z}", String(sourceLevel))
        .replace("{x}", String(sourceX))
        .replace("{y}", String(sourceY));
      const request = decodeTerrariumTile(url, sourceTileSize, childX, childY, childGridSize)
        .catch((reason) => {
          cache.delete(key);
          throw reason;
        });
      cache.set(key, request);
      if (cache.size > 96) cache.delete(cache.keys().next().value as string);
      return request;
    },
  });
}

function nearestEvidence(card: Scorecard) {
  const amenities = nearbyFromScorecard(card.domains.amenities?.evidence)
    .sort((left, right) => left.distance_m - right.distance_m);
  const nearestByCategory = new Map<string, (typeof amenities)[number]>();
  for (const item of amenities) {
    if (!nearestByCategory.has(item.category)) nearestByCategory.set(item.category, item);
  }
  const selected = [...nearestByCategory.values()].slice(0, 7);
  const police = nearbyFromScorecard(card.domains.security?.evidence)
    .sort((left, right) => left.distance_m - right.distance_m)
    .slice(0, 2);
  return [...selected, ...police];
}

function layerStatus(layer: Professional3DFeatureCollection): Professional3DLayerStatus {
  return {
    available: layer.metadata.status === "published" && layer.features.length > 0,
    featureCount: layer.metadata.feature_count,
    totalCount: layer.metadata.total_count,
    truncated: layer.metadata.truncated,
    advisory: layer.metadata.advisory,
  };
}

type PolygonCoordinates = number[][][];

function featurePolygons(feature: Professional3DFeatureCollection["features"][number]): PolygonCoordinates[] {
  if (feature.geometry.type === "Polygon") {
    return [feature.geometry.coordinates as PolygonCoordinates];
  }
  return feature.geometry.coordinates as PolygonCoordinates[];
}

function polygonCentroid(rings: PolygonCoordinates): Cesium.Cartographic {
  const outer = rings[0] ?? [];
  const usable = outer.length > 1 ? outer.slice(0, -1) : outer;
  const total = usable.reduce(
    (value, coordinate) => ({ lon: value.lon + coordinate[0], lat: value.lat + coordinate[1] }),
    { lon: 0, lat: 0 },
  );
  const divisor = Math.max(usable.length, 1);
  return Cesium.Cartographic.fromDegrees(total.lon / divisor, total.lat / divisor);
}

function polygonHierarchy(rings: PolygonCoordinates): Cesium.PolygonHierarchy {
  const positions = Cesium.Cartesian3.fromDegreesArray(rings[0].flatMap(([lon, lat]) => [lon, lat]));
  const holes = rings.slice(1).map((ring) => new Cesium.PolygonHierarchy(
    Cesium.Cartesian3.fromDegreesArray(ring.flatMap(([lon, lat]) => [lon, lat])),
  ));
  return new Cesium.PolygonHierarchy(positions, holes);
}

async function createExtrudedPrimitive(
  viewer: Cesium.Viewer,
  collection: Professional3DFeatureCollection,
  kind: "building" | "vegetation",
  signal?: AbortSignal,
): Promise<Cesium.Primitive | null> {
  const parts = collection.features.flatMap((feature) =>
    featurePolygons(feature).map((rings) => ({ feature, rings })),
  );
  if (!parts.length) return null;
  const samples = parts.map((part) => polygonCentroid(part.rings));
  await Cesium.sampleTerrain(viewer.terrainProvider, 12, samples);
  if (signal?.aborted) throw new DOMException("Professional 3D request aborted", "AbortError");
  const instances = parts.map(({ feature, rings }, index) => {
    const properties = feature.properties;
    const displayHeight = Number(properties.display_height_m ?? (kind === "vegetation" ? 4 : 6));
    const baseHeight = samples[index].height ?? 0;
    const minHeight = kind === "building" ? Number(properties.min_height_m ?? 0) : 0;
    const heightBasis = String(properties.height_basis ?? "default_visual");
    const instanceColor = kind === "vegetation"
      ? Cesium.Color.FORESTGREEN.withAlpha(0.48)
      : heightBasis === "published_height"
        ? Cesium.Color.STEELBLUE.withAlpha(0.82)
        : heightBasis === "floors_derived"
          ? Cesium.Color.SLATEGRAY.withAlpha(0.78)
          : Cesium.Color.DARKGOLDENROD.withAlpha(0.72);
    const title = kind === "vegetation"
      ? "Observed canopy zone—height illustrative"
      : `${String(properties.building_class ?? "Building").replaceAll("_", " ")} · ${displayHeight.toFixed(1)} m visual height`;
    return new Cesium.GeometryInstance({
      id: { kind, title, properties } satisfies Professional3DFeature,
      geometry: new Cesium.PolygonGeometry({
        polygonHierarchy: polygonHierarchy(rings),
        height: baseHeight + minHeight,
        extrudedHeight: baseHeight + minHeight + Math.max(displayHeight, 0.5),
        vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT,
        closeTop: true,
        closeBottom: true,
      }),
      attributes: {
        color: Cesium.ColorGeometryInstanceAttribute.fromColor(instanceColor),
      },
    });
  });
  return viewer.scene.primitives.add(new Cesium.Primitive({
    geometryInstances: instances,
    appearance: new Cesium.PerInstanceColorAppearance({
      closed: true,
      translucent: true,
      flat: kind === "vegetation",
    }),
    asynchronous: true,
    releaseGeometryInstances: true,
  })) as Cesium.Primitive;
}

function addEvidence(viewer: Cesium.Viewer, input: Professional3DInput): Cesium.Entity[] {
  const entities: Cesium.Entity[] = [];
  for (const item of nearestEvidence(input.card)) {
    const color = colour(AMENITY_MARKER_COLORS[item.category] ?? "#0d9488");
    entities.push(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(item.lon, item.lat),
      point: {
        pixelSize: 10,
        color,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
      label: {
        text: item.name,
        font: "600 12px 'Source Sans 3', sans-serif",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK.withAlpha(0.8),
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -18),
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 28_000),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    }));
  }
  for (const project of mappedProjects(input.card).slice(0, 8)) {
    if (project.geometry?.type !== "Point") continue;
    const [lon, lat] = project.geometry.coordinates;
    if (typeof lon !== "number" || typeof lat !== "number") continue;
    entities.push(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: {
        pixelSize: 11,
        color: Cesium.Color.DARKORANGE,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
      label: {
        text: project.name,
        font: "600 12px 'Source Sans 3', sans-serif",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -18),
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 32_000),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    }));
  }
  return entities;
}

export async function createProfessional3DScene(
  container: HTMLElement,
  input: Professional3DInput,
): Promise<Professional3DScene> {
  const warnings: string[] = [];
  const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN?.trim();
  if (ionToken) Cesium.Ion.defaultAccessToken = ionToken;
  let terrainProvider: Cesium.TerrainProvider | undefined;
  let terrainLabel = "base globe";
  const ionAvailable = Boolean(ionToken);
  if (ionToken) {
    try {
      terrainProvider = await Cesium.createWorldTerrainAsync({ requestVertexNormals: true });
      terrainLabel = "Cesium World Terrain";
    } catch {
      warnings.push("The Cesium ion token could not load World Terrain; raster elevation is active.");
    }
  }
  if (!terrainProvider) {
    try {
      terrainProvider = await createRasterTerrainProvider();
      terrainLabel = "Mapterhorn raster elevation";
    } catch {
      warnings.push("Elevation terrain could not be loaded; this view is using the flat base globe.");
    }
  }
  if (input.signal?.aborted) throw new DOMException("Professional 3D request aborted", "AbortError");

  const baseLayer = new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
    url: "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    credit: "OpenStreetMap contributors / CARTO",
    maximumLevel: 20,
  }));
  const viewer = new Cesium.Viewer(container, {
    baseLayer,
    terrainProvider,
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    sceneModePicker: false,
    geocoder: false,
    homeButton: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    vrButton: false,
    selectionIndicator: false,
    infoBox: false,
    requestRenderMode: true,
    maximumRenderTimeChange: Number.POSITIVE_INFINITY,
  });
  const terrainEnabled = Boolean(terrainProvider);
  const terrainExaggeration = terrainEnabled ? 1.35 : 1;
  viewer.scene.globe.depthTestAgainstTerrain = terrainEnabled;
  viewer.scene.globe.enableLighting = terrainEnabled;
  viewer.scene.verticalExaggeration = terrainExaggeration;
  viewer.scene.fog.enabled = false;
  viewer.scene.highDynamicRange = false;
  viewer.resolutionScale = window.innerWidth < 768 ? 0.72 : 0.9;

  const landCoverLayer = new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
    url: `${window.location.origin}/v1/locations/land-cover/tiles/{z}/{x}/{y}.png`,
    minimumLevel: 6,
    maximumLevel: 12,
    rectangle: LAND_COVER_BOUNDS,
    credit: input.card.location.land_cover?.source ?? "Observed land cover",
  }), { alpha: 0.38, show: true });
  viewer.imageryLayers.add(landCoverLayer);

  const bounds = siteBounds(input);
  const [landUseResult, buildingResult, vegetationResult] = await Promise.allSettled([
    fetchLandUse(bounds),
    fetchProfessionalBuildings(bounds, input.lon, input.lat, input.signal),
    fetchProfessionalVegetation(bounds, input.lon, input.lat, input.signal),
  ]);
  if (input.signal?.aborted) {
    viewer.destroy();
    throw new DOMException("Professional 3D request aborted", "AbortError");
  }

  let landUseSource: Cesium.GeoJsonDataSource | null = null;
  if (landUseResult.status === "fulfilled" && landUseResult.value.features.length) {
    landUseSource = await Cesium.GeoJsonDataSource.load(
      landUseResult.value as GeoJSON.FeatureCollection,
      {
        clampToGround: true,
        stroke: Cesium.Color.WHITE.withAlpha(0.85),
        strokeWidth: 1.5,
        fill: Cesium.Color.SLATEGRAY.withAlpha(0.3),
      },
    );
    const now = Cesium.JulianDate.now();
    for (const entity of landUseSource.entities.values) {
      const properties = entity.properties?.getValue(now) as Record<string, unknown> | undefined;
      const category = typeof properties?.category === "string" ? properties.category : "other";
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(
          colour(LAND_USE_COLORS[category] ?? LAND_USE_COLORS.other, 0.38),
        );
        entity.polygon.outline = new Cesium.ConstantProperty(false);
      }
    }
    await viewer.dataSources.add(landUseSource);
  } else if (landUseResult.status === "rejected") {
    warnings.push("The land-use reference overlay could not be loaded.");
  }

  const buildingCollection = buildingResult.status === "fulfilled" ? buildingResult.value : null;
  const vegetationCollection = vegetationResult.status === "fulfilled" ? vegetationResult.value : null;
  if (buildingResult.status === "rejected") warnings.push("Analytical buildings could not be loaded.");
  if (vegetationResult.status === "rejected") warnings.push("Observed canopy zones could not be loaded.");
  const buildingStatus = buildingCollection ? layerStatus(buildingCollection) : EMPTY_LAYER_STATUS;
  const vegetationStatus = vegetationCollection ? layerStatus(vegetationCollection) : EMPTY_LAYER_STATUS;
  if (buildingStatus.truncated) {
    warnings.push(`Showing the nearest ${buildingStatus.featureCount.toLocaleString()} of ${buildingStatus.totalCount.toLocaleString()} analytical buildings.`);
  }
  if (vegetationStatus.truncated) {
    warnings.push(`Showing ${vegetationStatus.featureCount.toLocaleString()} of ${vegetationStatus.totalCount.toLocaleString()} canopy zones.`);
  }

  const [buildingPrimitive, vegetationPrimitive] = await Promise.all([
    buildingCollection
      ? createExtrudedPrimitive(viewer, buildingCollection, "building", input.signal)
      : Promise.resolve(null),
    vegetationCollection
      ? createExtrudedPrimitive(viewer, vegetationCollection, "vegetation", input.signal)
      : Promise.resolve(null),
  ]);

  const evidenceEntities = addEvidence(viewer, input);
  viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(input.lon, input.lat),
    ellipse: {
      semiMajorAxis: input.radiusKm * 1_000,
      semiMinorAxis: input.radiusKm * 1_000,
      material: Cesium.Color.DEEPSKYBLUE.withAlpha(0.1),
      outline: true,
      outlineColor: Cesium.Color.DEEPSKYBLUE.withAlpha(0.9),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      classificationType: Cesium.ClassificationType.BOTH,
    },
  });
  const siteContext = [
    input.card.location.land_use
      ? `Land-use reference: ${input.card.location.land_use.label}`
      : "Land-use reference: unmapped at point",
    input.card.location.land_cover
      ? `Observed cover: ${input.card.location.land_cover.label}`
      : "Observed cover: unavailable",
  ].join("\n");
  viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(input.lon, input.lat),
    point: {
      pixelSize: 16,
      color: Cesium.Color.DEEPSKYBLUE,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 4,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
    label: {
      text: `${input.placeLabel}\n${siteContext}`,
      font: "600 13px 'Source Sans 3', sans-serif",
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 4,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -36),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  });

  const resetView = () => {
    const siteRadiusKm = Math.min(input.radiusKm, 3);
    const centre = Cesium.Cartesian3.fromDegrees(input.lon, input.lat, 0);
    viewer.camera.flyToBoundingSphere(
      new Cesium.BoundingSphere(centre, siteRadiusKm * 1_000),
      {
        duration: 0.8,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(18),
          Cesium.Math.toRadians(-28),
          Math.max(4_200, siteRadiusKm * 2_250),
        ),
      },
    );
  };

  let currentMode: Professional3DMode = "analytical";
  let landCoverVisible = true;
  let landUseVisible = true;
  let buildingsVisible = true;
  let vegetationVisible = true;
  let photorealisticTileset: Cesium.Cesium3DTileset | null = null;

  const applyAnalyticalVisibility = () => {
    const analytical = currentMode === "analytical";
    viewer.scene.globe.show = analytical;
    baseLayer.show = analytical;
    landCoverLayer.show = analytical && landCoverVisible;
    if (landUseSource) landUseSource.show = analytical && landUseVisible;
    if (buildingPrimitive) buildingPrimitive.show = analytical && buildingsVisible;
    if (vegetationPrimitive) vegetationPrimitive.show = analytical && vegetationVisible;
    if (photorealisticTileset) photorealisticTileset.show = !analytical;
    viewer.scene.requestRender();
  };

  const loadPhotorealistic = async (): Promise<string | undefined> => {
    if (!ionAvailable) return "A valid Cesium ion token is required for photorealistic mode.";
    if (!photorealisticTileset) {
      try {
        const mobile = window.innerWidth < 768;
        photorealisticTileset = await Cesium.createGooglePhotorealistic3DTileset(
          { onlyUsingWithGoogleGeocoder: true },
          {
            showCreditsOnScreen: true,
            maximumScreenSpaceError: mobile ? 24 : 16,
            cacheBytes: (mobile ? 128 : 256) * 1024 * 1024,
            maximumCacheOverflowBytes: (mobile ? 64 : 128) * 1024 * 1024,
          },
        );
        viewer.scene.primitives.add(photorealisticTileset);
      } catch {
        photorealisticTileset = null;
        return "Google Photorealistic 3D Tiles could not be loaded for this account.";
      }
    }
    // Keep the analytical scene visible until photographic detail is confirmed.
    photorealisticTileset.show = true;
    viewer.scene.requestRender();
    resetView();
    const tileset = photorealisticTileset;
    const detailedTileVisible = await new Promise<boolean>((resolve) => {
      let settled = false;
      let removeListener = () => {};
      let timer = 0;
      const finish = (visible: boolean) => {
        if (settled) return;
        settled = true;
        removeListener();
        window.clearTimeout(timer);
        resolve(visible);
      };
      removeListener = tileset.tileVisible.addEventListener((tile) => {
        if (tile.geometricError < 500) finish(true);
      });
      timer = window.setTimeout(() => finish(false), 12_000);
      if (input.signal) input.signal.addEventListener("abort", () => finish(false), { once: true });
    });
    if (!detailedTileVisible) {
      currentMode = "analytical";
      applyAnalyticalVisibility();
      resetView();
      return "Detailed photographic 3D coverage is unavailable at this location; Analytical mode has been restored.";
    }
    currentMode = "photorealistic";
    applyAnalyticalVisibility();
    return undefined;
  };

  const pickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  pickHandler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
    const picked = viewer.scene.pick(movement.position) as { id?: Professional3DFeature } | undefined;
    const feature = picked?.id;
    input.onFeatureSelect?.(
      feature && (feature.kind === "building" || feature.kind === "vegetation") ? feature : null,
    );
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  resetView();
  applyAnalyticalVisibility();
  return {
    terrainEnabled,
    terrainLabel,
    terrainExaggeration,
    buildingsEnabled: Boolean(buildingPrimitive),
    vegetationEnabled: Boolean(vegetationPrimitive),
    photorealisticAvailable: ionAvailable,
    buildingStatus,
    vegetationStatus,
    warnings,
    resetView,
    setMode: async (mode) => {
      if (mode === "analytical") {
        currentMode = "analytical";
        applyAnalyticalVisibility();
        resetView();
        return { mode: "analytical" };
      }
      const warning = await loadPhotorealistic();
      return warning ? { mode: "analytical", warning } : { mode: "photorealistic" };
    },
    setLandCoverVisible: (visible) => {
      landCoverVisible = visible;
      applyAnalyticalVisibility();
    },
    setLandUseVisible: (visible) => {
      landUseVisible = visible;
      applyAnalyticalVisibility();
    },
    setEvidenceVisible: (visible) => {
      evidenceEntities.forEach((entity) => { entity.show = visible; });
      viewer.scene.requestRender();
    },
    setBuildingsVisible: (visible) => {
      buildingsVisible = visible;
      applyAnalyticalVisibility();
    },
    setVegetationVisible: (visible) => {
      vegetationVisible = visible;
      applyAnalyticalVisibility();
    },
    destroy: () => {
      pickHandler.destroy();
      if (!viewer.isDestroyed()) viewer.destroy();
    },
  };
}
