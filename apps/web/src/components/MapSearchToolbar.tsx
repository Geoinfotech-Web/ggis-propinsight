import { useState } from "react";
import clsx from "clsx";
import { getCurrentPosition } from "../lib/geocode";
import type { PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconLocate } from "./Icons";
import { PersonaSelect } from "./PersonaSelect";
import { SearchBar } from "./SearchBar";

type Props = {
  theme: Theme;
  persona: PersonaKey;
  onPersonaChange: (key: PersonaKey) => void;
  onSelectPlace: (lon: number, lat: number, label?: string) => void;
  resetKey?: number;
  locating?: boolean;
  compact?: boolean;
  selectedStateName?: string;
  viewbox?: [number, number, number, number];
};

export function MapSearchToolbar({
  theme,
  persona,
  onPersonaChange,
  onSelectPlace,
  resetKey,
  locating = false,
  compact = false,
  selectedStateName,
  viewbox,
}: Props) {
  const dark = theme === "dark";
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const busy = geoBusy || locating;

  const useMyLocation = async () => {
    setGeoError(null);
    setGeoBusy(true);
    try {
      const position = await getCurrentPosition();
      onSelectPlace(position.coords.longitude, position.coords.latitude, "Current location");
    } catch (error) {
      setGeoError((error as GeolocationPositionError).message || "Could not get location");
    } finally {
      setGeoBusy(false);
    }
  };

  return (
    <div className={clsx("min-w-0", compact ? "w-full" : "w-[min(36rem,calc(100vw-30rem))]") }>
      <div className="flex min-w-0 items-center gap-2">
        <PersonaSelect theme={theme} persona={persona} onPersonaChange={onPersonaChange} />
        <div className="min-w-0 flex-1">
          <SearchBar
            theme={theme}
            size="md"
            resetKey={resetKey}
            viewbox={viewbox}
            placeholder={
              selectedStateName
                ? `Search within ${selectedStateName}…`
                : compact
                ? "Search place or district…"
                : "Search a place, district, or landmark…"
            }
            onResult={(hit) => onSelectPlace(hit.lon, hit.lat, hit.label)}
          />
        </div>
        <button
          type="button"
          onClick={() => void useMyLocation()}
          disabled={busy}
          className={clsx(
            "glass-tool liquid-tool-ivory inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition",
            dark
              ? "border-gray-700 bg-gray-900/60 text-teal-300 hover:bg-gray-800/80"
              : "border-white/70 bg-white/60 text-teal-600 hover:border-teal-300",
            busy && "cursor-wait opacity-70",
          )}
          aria-label="Use my location"
          title="Use my location"
        >
          {busy ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-teal-500" />
          ) : (
            <IconLocate size={18} />
          )}
        </button>
      </div>
      {geoError && (
        <p className={clsx("mt-1 rounded-lg px-2 py-1 text-[11px] shadow", dark ? "bg-gray-900 text-amber-300" : "bg-white text-amber-800") }>
          {geoError}
        </p>
      )}
    </div>
  );
}
