import type { StyleSpecification } from "maplibre-gl";

const OSM_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const CARTO_ATTR = `${OSM_ATTR} &copy; <a href="https://carto.com/attributions">CARTO</a>`;
const ESRI_ATTR =
  "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community";

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

export const BASEMAPS: BasemapOption[] = [
  {
    id: "voyager",
    label: "Voyager",
    style: rasterStyle(
      "carto-voyager",
      ["https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"],
      CARTO_ATTR,
    ),
  },
  {
    id: "positron",
    label: "Light",
    style: rasterStyle(
      "carto-positron",
      ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"],
      CARTO_ATTR,
    ),
  },
  {
    id: "dark",
    label: "Dark",
    style: rasterStyle(
      "carto-dark",
      ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"],
      CARTO_ATTR,
    ),
  },
  {
    id: "streets",
    label: "Streets",
    style: rasterStyle(
      "osm",
      ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      OSM_ATTR,
    ),
  },
  {
    id: "satellite",
    label: "Satellite",
    style: rasterStyle(
      "esri-sat",
      [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      ESRI_ATTR,
    ),
  },
];

export const DEFAULT_BASEMAP_ID: BasemapId = "voyager";

export function getBasemap(id: BasemapId): BasemapOption {
  return BASEMAPS.find((b) => b.id === id) ?? BASEMAPS[0];
}

/** @deprecated use getBasemap(DEFAULT_BASEMAP_ID).style */
export const PROPSIGHT_BASEMAP = getBasemap(DEFAULT_BASEMAP_ID).style;
