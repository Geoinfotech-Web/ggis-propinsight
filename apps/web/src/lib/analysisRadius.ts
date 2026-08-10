export const MIN_ANALYSIS_RADIUS_KM = 5;
export const MAX_ANALYSIS_RADIUS_KM = 20;
export const DEFAULT_ANALYSIS_RADIUS_KM = 5;

const STORAGE_KEY = "propinsight-analysis-radius-km";

export function clampAnalysisRadius(radiusKm: number): number {
  if (!Number.isFinite(radiusKm)) return DEFAULT_ANALYSIS_RADIUS_KM;
  return Math.min(
    MAX_ANALYSIS_RADIUS_KM,
    Math.max(MIN_ANALYSIS_RADIUS_KM, Math.round(radiusKm)),
  );
}

export function loadAnalysisRadius(): number {
  if (typeof window === "undefined") return DEFAULT_ANALYSIS_RADIUS_KM;
  return clampAnalysisRadius(Number(localStorage.getItem(STORAGE_KEY)));
}

export function saveAnalysisRadius(radiusKm: number): void {
  localStorage.setItem(STORAGE_KEY, String(clampAnalysisRadius(radiusKm)));
}
