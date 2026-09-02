/** Theme helpers. PropInsight currently runs in the light interface only. */

export type Theme = "light" | "dark";

export function loadTheme(): Theme {
  return "light";
}

export function applyTheme(_theme: Theme): void {
  document.documentElement.dataset.theme = "light";
  localStorage.setItem("aia-theme", "light");
}
