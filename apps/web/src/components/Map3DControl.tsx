import clsx from "clsx";
import type { Theme } from "../theme";

type Props = {
  theme: Theme;
  enabled: boolean;
  onToggle: () => void;
};

export function Map3DControl({ theme, enabled, onToggle }: Props) {
  const dark = theme === "dark";
  const action = enabled ? "Switch to 2D" : "Switch to 3D";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={action}
      aria-pressed={enabled}
      title={`${action} · 3D also turns on automatically at street-level zoom`}
      className={clsx(
        "glass-tool liquid-tool-ivory inline-flex h-10 w-10 items-center justify-center rounded-xl border text-xs font-bold transition",
        enabled
          ? "border-blue-500 bg-blue-600 text-white hover:bg-blue-500"
          : dark
            ? "border-gray-700 bg-gray-900/60 text-gray-200 hover:border-gray-500 hover:bg-gray-800/80"
            : "border-white/70 bg-white/60 text-slate-600 hover:border-slate-300 hover:text-slate-900",
      )}
    >
      3D
    </button>
  );
}
