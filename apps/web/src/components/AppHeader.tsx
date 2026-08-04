import { useState } from "react";
import clsx from "clsx";
import { getCurrentPosition } from "../lib/geocode";
import { type PersonaKey } from "../lib/personas";
import type { Theme } from "../theme";
import { IconBrandMark, IconLocate, IconMoon, IconSun } from "./Icons";
import { PersonaSelect } from "./PersonaSelect";
import { SearchBar } from "./SearchBar";

type Props = {
  theme: Theme;
  onToggleTheme: () => void;
  onSelectPlace: (lon: number, lat: number, label?: string) => void;
  locating?: boolean;
  persona: PersonaKey;
  onPersonaChange: (key: PersonaKey) => void;
};

/**
 * Flood Watch PublicHeader layout adapted for PropInsight:
 * Desktop (sm+): brand | Search max-w-md [locate] | Live | persona tabs | theme
 * Phone: brand … personas theme · search+locate on second row only
 */
export function AppHeader({
  theme,
  onToggleTheme,
  onSelectPlace,
  locating,
  persona,
  onPersonaChange,
}: Props) {
  const dark = theme === "dark";
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const busy = geoBusy || Boolean(locating);

  const useMyLocation = async () => {
    setGeoError(null);
    setGeoBusy(true);
    try {
      const pos = await getCurrentPosition();
      onSelectPlace(pos.coords.longitude, pos.coords.latitude, "Current location");
    } catch (err) {
      setGeoError((err as GeolocationPositionError).message || "Could not get location");
    } finally {
      setGeoBusy(false);
    }
  };

  const locateButton = () => (
    <button
      type="button"
      onClick={() => void useMyLocation()}
      disabled={busy}
      className={clsx(
        "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border shadow-sm transition",
        busy && "opacity-70",
        dark
          ? "border-gray-700 bg-gray-900 text-sky-300 hover:bg-gray-800"
          : "border-slate-200 bg-white text-sky-700 hover:border-slate-300",
      )}
      aria-label="Use my location"
      title="Use my location"
    >
      {busy ? (
        <span
          className={clsx(
            "h-4 w-4 animate-spin rounded-full border-2",
            dark ? "border-gray-600 border-t-sky-400" : "border-slate-300 border-t-sky-600",
          )}
        />
      ) : (
        <IconLocate size={16} />
      )}
    </button>
  );

  return (
    <header
      className={clsx(
        "relative z-20 shrink-0 border-b pt-[env(safe-area-inset-top)] backdrop-blur-md",
        dark ? "border-gray-800 bg-gray-950/90" : "border-slate-200/80 bg-white/90",
      )}
    >
      <div
        className={clsx(
          "pointer-events-none absolute inset-x-0 top-0 h-16 opacity-80",
          dark
            ? "bg-gradient-to-b from-sky-950/50 to-transparent"
            : "bg-gradient-to-b from-sky-100/70 via-cyan-50/40 to-transparent",
        )}
      />

      <div className="relative flex w-full flex-col gap-2 px-3 py-2.5 sm:gap-0 sm:px-4 sm:py-2.5">
        <div className="flex w-full items-center gap-2 sm:gap-4">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none sm:shrink-0 sm:gap-3">
            <div
              className={clsx(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border sm:h-10 sm:w-10",
                dark
                  ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                  : "border-sky-200 bg-sky-50 text-sky-700",
              )}
            >
              <IconBrandMark size={18} />
            </div>
            <div className="min-w-0">
              <h1 className="font-display truncate text-sm font-semibold tracking-tight sm:text-lg">
                PropInsight
              </h1>
              <p
                className={clsx(
                  "hidden truncate text-[11px] lg:block",
                  dark ? "text-gray-400" : "text-slate-500",
                )}
              >
                FCT pilot · location scorecard
              </p>
            </div>
          </div>

          <div className="mx-auto hidden min-w-0 w-full max-w-xl flex-1 items-center gap-2 sm:flex">
            <PersonaSelect theme={theme} persona={persona} onPersonaChange={onPersonaChange} />
            <div className="min-w-0 flex-1">
              <SearchBar
                theme={theme}
                size="md"
                placeholder="Search a place, district, or landmark…"
                onResult={(hit) => onSelectPlace(hit.lon, hit.lat, hit.label)}
              />
            </div>
            {locateButton()}
          </div>

          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <div
              className={clsx(
                "hidden items-center gap-1.5 rounded-full border px-2.5 py-1 md:inline-flex",
                dark
                  ? "border-teal-800/60 bg-teal-950/50 text-teal-300"
                  : "border-teal-200 bg-teal-50 text-teal-800",
              )}
            >
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-teal-500" />
              <span className="text-[11px] font-medium">Live</span>
            </div>

            <button
              type="button"
              onClick={onToggleTheme}
              className={clsx(
                "inline-flex h-9 w-9 items-center justify-center rounded-lg border transition sm:h-8 sm:w-8",
                dark
                  ? "border-gray-700 text-gray-300 hover:bg-gray-800"
                  : "border-slate-200 text-slate-600 hover:bg-white",
              )}
              aria-label="Toggle theme"
              title="Toggle theme"
            >
              {dark ? <IconSun size={14} /> : <IconMoon size={14} />}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:hidden">
          <PersonaSelect theme={theme} persona={persona} onPersonaChange={onPersonaChange} />
          <div className="min-w-0 flex-1">
            <SearchBar
              theme={theme}
              size="md"
              placeholder="Search place or district…"
              onResult={(hit) => onSelectPlace(hit.lon, hit.lat, hit.label)}
            />
          </div>
          {locateButton()}
        </div>

        {geoError && (
          <p className={clsx("text-[11px]", dark ? "text-amber-300/90" : "text-amber-800")}>
            {geoError}
          </p>
        )}
      </div>
    </header>
  );
}
