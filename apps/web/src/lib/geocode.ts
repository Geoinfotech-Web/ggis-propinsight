/** Shared place-search helpers (Nominatim, Nigeria/state-biased). */

export type PlaceHit = {
  id: string;
  label: string;
  lon: number;
  lat: number;
};

const NIGERIA_VIEWBOX = "2.65,4.25,14.7,13.95"; // lon_min,lat_min,lon_max,lat_max

export async function searchPlaces(
  query: string,
  signal?: AbortSignal,
  viewbox?: [number, number, number, number],
): Promise<PlaceHit[]> {
  const q = query.trim();
  if (q.length < 2) return [];

  const params = new URLSearchParams({
    format: "jsonv2",
    q,
    limit: "6",
    addressdetails: "0",
    countrycodes: "ng",
    viewbox: viewbox?.join(",") ?? NIGERIA_VIEWBOX,
    bounded: "0",
  });

  const res = await fetch(`/geocode/search?${params}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Place search failed (${res.status})`);
  const rows = (await res.json()) as Array<{
    place_id: number;
    display_name: string;
    lon: string;
    lat: string;
  }>;

  return rows.map((r) => ({
    id: String(r.place_id),
    label: r.display_name,
    lon: Number(r.lon),
    lat: Number(r.lat),
  }));
}

export function getCurrentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported in this browser."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 12_000,
      maximumAge: 30_000,
    });
  });
}
