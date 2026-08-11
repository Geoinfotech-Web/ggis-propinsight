import "cesium/Build/Cesium/Widgets/widgets.css";
import * as Cesium from "cesium";
import { fetchLandUse, type Scorecard } from "../api";
import { AMENITY_MARKER_COLORS, nearbyFromScorecard } from "./amenitiesMap";
import { analysisBufferBounds } from "./analysisBufferMap";
import { LAND_USE_COLORS } from "./landUseMap";
import { mappedProjects } from "./projectsMap";

export type Professional3DInput = {
  card: Scorecard;
  lon: number;
  lat: number;
  radiusKm: number;
  placeLabel: string;
};

export type Professional3DScene = {
  terrainEnabled: boolean;
  terrainLabel: string;
  terrainExaggeration: number;
  buildingsEnabled: boolean;
  warnings: string[];
  resetView: () => void;
  setLandCoverVisible: (visible: boolean) => void;
  setLandUseVisible: (visible: boolean) => void;
  setEvidenceVisible: (visible: boolean) => void;
  setBuildingsVisible: (visible: boolean) => void;
  destroy: () => void;
};

const LAND_COVER_BOUNDS = Cesium.Rectangle.fromDegrees(6.77, 8.41, 7.73, 9.42);
function reportBounds(input: Professional3DInput): [number, number, number, number] {
  const bounds = analysisBufferBounds(input.lon, input.lat, input.radiusKm) as [
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
      const request = decodeTerrariumTile(
        url,
        sourceTileSize,
        childX,
        childY,
        childGridSize,
      ).catch((reason) => {
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

export async function createProfessional3DScene(
  container: HTMLElement,
  input: Professional3DInput,
): Promise<Professional3DScene> {
  const warnings: string[] = [];
  const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN?.trim();
  if (ionToken) Cesium.Ion.defaultAccessToken = ionToken;

  let terrainProvider: Cesium.TerrainProvider | undefined;
  let terrainLabel = "base globe";
  let ionAvailable = false;
  if (ionToken) {
    try {
      terrainProvider = await Cesium.createWorldTerrainAsync({ requestVertexNormals: true });
      terrainLabel = "Cesium World Terrain";
      ionAvailable = true;
    } catch {
      warnings.push("The configured Cesium ion token was rejected, so raster elevation terrain is being used instead.");
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

  const baseLayer = new Cesium.ImageryLayer(
    new Cesium.UrlTemplateImageryProvider({
      url: "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      credit: "OpenStreetMap contributors / CARTO",
      maximumLevel: 20,
    }),
  );

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

  if (!ionAvailable) {
    warnings.push("Add a valid VITE_CESIUM_ION_TOKEN to enable Cesium World Terrain and OSM 3D buildings.");
  }

  const landCoverLayer = new Cesium.ImageryLayer(
    new Cesium.UrlTemplateImageryProvider({
      url: `${window.location.origin}/v1/locations/land-cover/tiles/{z}/{x}/{y}.png`,
      minimumLevel: 6,
      maximumLevel: 12,
      rectangle: LAND_COVER_BOUNDS,
      credit: input.card.location.land_cover?.source ?? "Observed land cover",
    }),
    { alpha: 0.38, show: true },
  );
  viewer.imageryLayers.add(landCoverLayer);

  let landUseSource: Cesium.GeoJsonDataSource | null = null;
  try {
    const landUse = await fetchLandUse(reportBounds(input));
    if (landUse.features.length) {
      landUseSource = await Cesium.GeoJsonDataSource.load(landUse as GeoJSON.FeatureCollection, {
        clampToGround: true,
        stroke: Cesium.Color.WHITE.withAlpha(0.85),
        strokeWidth: 1.5,
        fill: Cesium.Color.SLATEGRAY.withAlpha(0.3),
      });
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
    } else {
      warnings.push("No mapped land-use reference polygons were returned for this analysis area.");
    }
  } catch {
    warnings.push("The land-use reference overlay could not be loaded.");
  }

  const evidenceEntities: Cesium.Entity[] = [];
  for (const item of nearestEvidence(input.card)) {
    const color = colour(AMENITY_MARKER_COLORS[item.category] ?? "#0d9488");
    evidenceEntities.push(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(item.lon, item.lat),
      point: {
        pixelSize: 10,
        color,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: 35_000,
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
        disableDepthTestDistance: 35_000,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    }));
  }

  for (const project of mappedProjects(input.card).slice(0, 8)) {
    if (project.geometry?.type !== "Point") continue;
    const [lon, lat] = project.geometry.coordinates;
    if (typeof lon !== "number" || typeof lat !== "number") continue;
    evidenceEntities.push(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: {
        pixelSize: 11,
        color: Cesium.Color.DARKORANGE,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
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
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    }));
  }

  viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(input.lon, input.lat),
    ellipse: {
      semiMajorAxis: input.radiusKm * 1_000,
      semiMinorAxis: input.radiusKm * 1_000,
      material: Cesium.Color.DEEPSKYBLUE.withAlpha(0.1),
      outline: true,
      outlineColor: Cesium.Color.DEEPSKYBLUE.withAlpha(0.9),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
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

  let buildings: Cesium.Cesium3DTileset | null = null;
  if (ionAvailable) {
    try {
      buildings = await Cesium.createOsmBuildingsAsync();
      viewer.scene.primitives.add(buildings);
    } catch {
      warnings.push("Cesium OSM buildings are unavailable for this view or token.");
    }
  }

  const resetView = () => {
    const siteRadiusKm = Math.min(input.radiusKm, 3);
    const centre = Cesium.Cartesian3.fromDegrees(input.lon, input.lat, 0);
    const range = Math.max(4_200, siteRadiusKm * 2_250);
    viewer.camera.flyToBoundingSphere(
      new Cesium.BoundingSphere(centre, siteRadiusKm * 1_000),
      {
        duration: 0.8,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(18),
          Cesium.Math.toRadians(-28),
          range,
        ),
      },
    );
  };
  resetView();
  viewer.scene.requestRender();

  return {
    terrainEnabled,
    terrainLabel,
    terrainExaggeration,
    buildingsEnabled: Boolean(buildings),
    warnings,
    resetView,
    setLandCoverVisible: (visible) => {
      landCoverLayer.show = visible;
      viewer.scene.requestRender();
    },
    setLandUseVisible: (visible) => {
      if (landUseSource) landUseSource.show = visible;
      viewer.scene.requestRender();
    },
    setEvidenceVisible: (visible) => {
      evidenceEntities.forEach((entity) => { entity.show = visible; });
      viewer.scene.requestRender();
    },
    setBuildingsVisible: (visible) => {
      if (buildings) buildings.show = visible;
      viewer.scene.requestRender();
    },
    destroy: () => {
      if (!viewer.isDestroyed()) viewer.destroy();
    },
  };
}
