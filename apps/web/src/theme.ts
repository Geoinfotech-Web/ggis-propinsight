/** Light/dark theme helpers (GGIS design template §6). */

export type Theme = "light" | "dark";

export function loadTheme(): Theme {
  const saved = localStorage.getItem("aia-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("aia-theme", theme);
}
