import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { analyzePoint, DOMAIN_ORDER, type Scorecard } from "./api";

// FCT / Abuja pilot centre.
const FCT_CENTER: [number, number] = [7.4913, 9.0579];

// Free demo raster basemap (OSM). Swapped for Geoinfotech UAV/vector tiles in Phase 1.
const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const STATUS_STYLE: Record<string, string> = {
  ok: "bg-teal text-white",
  degraded: "bg-amber-500 text-white",
  pending: "bg-gray-300 text-gray-700",
};

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: FCT_CENTER,
      zoom: 11,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("click", async (e) => {
      const { lng, lat } = e.lngLat;
      markerRef.current?.remove();
      markerRef.current = new maplibregl.Marker({ color: "#1F8A70" })
        .setLngLat([lng, lat])
        .addTo(map);
      setLoading(true);
      setError(null);
      try {
        setCard(await analyzePoint(lng, lat));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    });
    mapRef.current = map;
  }, []);

  return (
    <div className="flex h-full w-full">
      <div ref={mapContainer} className="flex-1" />
      <aside className="w-[380px] overflow-y-auto border-l border-gray-200 bg-white">
        <header className="bg-navy px-5 py-4 text-white">
          <h1 className="text-lg font-bold">GGIS PropInsight</h1>
          <p className="text-xs text-gray-300">Location Intelligence — FCT (Abuja) pilot</p>
        </header>

        <div className="p-5">
          {!card && !loading && (
            <p className="text-sm text-gray-500">
              Click anywhere on the map to generate a Location Intelligence Report.
            </p>
          )}
          {loading && <p className="text-sm text-brandblue">Analysing location…</p>}
          {error && <p className="text-sm text-red-600">Error: {error}</p>}

          {card && (
            <>
              <div className="mb-3 text-xs text-gray-500">
                geohash: {card.location.geohash8} · profile: {card.scoring_profile}
              </div>
              <div className="space-y-2">
                {DOMAIN_ORDER.map((d) => {
                  const r = card.domains[d];
                  if (!r) return null;
                  return (
                    <div key={d} className="rounded border border-gray-200 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold capitalize">{d}</span>
                        <span
                          className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[r.status] ?? ""}`}
                        >
                          {r.score !== null ? r.score : r.status}
                        </span>
                      </div>
                      {r.note && <p className="mt-1 text-xs text-gray-500">{r.note}</p>}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
