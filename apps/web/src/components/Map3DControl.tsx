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
        "relative inline-flex h-10 w-10 items-center justify-center rounded-xl border text-xs font-bold shadow-lg transition",
        enabled
          ? "border-blue-500 bg-blue-600 text-white hover:bg-blue-500"
          : dark
            ? "border-gray-700 bg-gray-900 text-gray-200 hover:border-gray-500 hover:bg-gray-800"
            : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900",
      )}
      style={
        enabled
          ? { backgroundColor: "#2563eb", borderColor: "#3b82f6" }
          : dark
            ? { backgroundColor: "#111827", borderColor: "#374151" }
            : { backgroundColor: "#ffffff", borderColor: "#cbd5e1" }
      }
    >
      3D
      <span
        className={clsx(
          "absolute -bottom-1 -right-1 rounded px-1 text-[7px] font-semibold leading-3 shadow-sm",
          enabled ? "bg-white text-blue-700" : "bg-slate-700 text-white",
        )}
        aria-hidden
      >
        AUTO
      </span>
    </button>
  );
}
