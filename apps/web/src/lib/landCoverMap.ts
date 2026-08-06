import maplibregl from "maplibre-gl";

export const LAND_COVER_SOURCE_ID = "aia-observed-land-cover";
export const LAND_COVER_LAYER_ID = "aia-observed-land-cover-raster";

export const LAND_COVER_LEGEND = [
  ["#006400", "Tree cover"],
  ["#ffbb22", "Shrubland"],
  ["#ffff4c", "Grassland"],
  ["#f096ff", "Cropland"],
  ["#fa0000", "Built-up"],
  ["#b4b4b4", "Bare / sparse vegetation"],
  ["#0064c8", "Permanent water"],
  ["#0096a0", "Herbaceous wetland"],
] as const;

export function showLandCoverLayer(map: maplibregl.Map): void {
  if (!map.getSource(LAND_COVER_SOURCE_ID)) {
    map.addSource(LAND_COVER_SOURCE_ID, {
      type: "raster",
      tiles: ["/v1/locations/land-cover/tiles/{z}/{x}/{y}.png"],
      tileSize: 256,
      minzoom: 6,
      // 30 m source pixels are already matched around z12. Let MapLibre
      // overzoom those cached tiles instead of asking the API to reproject
      // dozens of increasingly detailed tiles during close-up navigation.
      maxzoom: 12,
      bounds: [6.77, 8.41, 7.73, 9.42],
      attribution: "Observed cover: ESA WorldCover / Google Dynamic World",
    });
  }
  if (!map.getLayer(LAND_COVER_LAYER_ID)) {
    map.addLayer({
      id: LAND_COVER_LAYER_ID,
      type: "raster",
      source: LAND_COVER_SOURCE_ID,
      paint: {
        "raster-opacity": 0.58,
        "raster-resampling": "nearest",
        "raster-fade-duration": 0,
      },
    });
  } else {
    map.setLayoutProperty(LAND_COVER_LAYER_ID, "visibility", "visible");
  }
}

export function hideLandCoverLayer(map: maplibregl.Map): void {
  if (map.getLayer(LAND_COVER_LAYER_ID)) {
    try {
      map.setLayoutProperty(LAND_COVER_LAYER_ID, "visibility", "none");
    } catch {
      // A basemap style swap can remove the layer between lookup and mutation.
    }
  }
}
