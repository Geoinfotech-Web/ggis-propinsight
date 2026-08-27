import type { StyleSpecification } from "maplibre-gl";

const OSM_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const ESRI_ATTR =
  "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community";
const ESRI_BASE_ATTR =
  "Tiles &copy; Esri — Source: Esri, TomTom, Garmin, FAO, NOAA, USGS";

export type BasemapId = "voyager" | "positron" | "dark" | "satellite" | "streets";

export type BasemapOption = {
  id: BasemapId;
  label: string;
  style: StyleSpecification;
};

function rasterStyle(
  id: string,
  tiles: string[],
  attribution: string,
  tileSize = 256,
): StyleSpecification {
  return {
    version: 8,
    // Required for symbol text-field (amenity name labels).
    // Avoid demotiles.maplibre.org — it now shows an "API key needed" watermark.
    glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
    sources: {
      [id]: {
        type: "raster",
        tiles,
        tileSize,
        attribution,
      },
    },
    layers: [
      {
        id: `${id}-layer`,
        type: "raster",
        source: id,
        minzoom: 0,
        maxzoom: 22,
      },
    ],
  };
}

/** Esri ArcGIS Online public raster tiles (no CARTO quota / API key). */
const ESRI = {
  street:
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
  light:
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
  dark:
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
  satellite:
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
} as const;

export const BASEMAPS: BasemapOption[] = [
  {
    id: "voyager",
    label: "Streets",
    style: rasterStyle("esri-street", [ESRI.street], ESRI_BASE_ATTR),
  },
  {
    id: "positron",
    label: "Light",
    style: rasterStyle("esri-light", [ESRI.light], ESRI_BASE_ATTR),
  },
  {
    id: "dark",
    label: "Dark",
    style: rasterStyle("esri-dark", [ESRI.dark], ESRI_BASE_ATTR),
  },
  {
    id: "streets",
    label: "OSM",
    style: rasterStyle(
      "osm",
      ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      OSM_ATTR,
    ),
  },
  {
    id: "satellite",
    label: "Satellite",
    style: rasterStyle("esri-sat", [ESRI.satellite], ESRI_ATTR),
  },
];

export const DEFAULT_BASEMAP_ID: BasemapId = "streets";

export function getBasemap(id: BasemapId): BasemapOption {
  return BASEMAPS.find((b) => b.id === id) ?? BASEMAPS[0];
}

/** @deprecated use getBasemap(DEFAULT_BASEMAP_ID).style */
export const PROPSIGHT_BASEMAP = getBasemap(DEFAULT_BASEMAP_ID).style;
