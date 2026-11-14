/** Local window layout preferences, separate from scientific project contents. */
export const layoutKeys = {
  cakeProfileWidth: "dioptas-layout:cake-profile-width",
  imageShare: "dioptas-layout:image-share",
  spottinessShare: "dioptas-layout:spottiness-main-share",
  controlsShare: "dioptas-layout:controls-share",
  scxrdPanelWidth: "dioptas-layout:scxrd-panel-width",
  configurationControls: "dioptas-layout:configuration-controls",
  batchOpen: "dioptas-batch:open",
  batchDocked: "dioptas-batch:docked",
  batchHeight: "dioptas-batch:dock-height",
  batchCollapsed: "dioptas-batch:collapsed",
} as const;
export function readLayoutNumber(
  key: string,
  fallback: number,
  min: number,
  max: number,
) {
  try {
    const raw = localStorage.getItem(key);
    const value = raw?.trim() ? Number(raw) : NaN;
    return Number.isFinite(value)
      ? Math.max(min, Math.min(max, value))
      : fallback;
  } catch {
    return fallback;
  }
}
export function readLayoutFlag(key: string, fallback = false) {
  try {
    const value = localStorage.getItem(key);
    return value === "true" ? true : value === "false" ? false : fallback;
  } catch {
    return fallback;
  }
}
export function saveLayoutValue(key: string, value: number | boolean) {
  if (typeof value === "number" && !Number.isFinite(value)) return;
  try {
    localStorage.setItem(key, String(value));
  } catch {
    /* Session layout still works. */
  }
}
