/** Local window layout preferences, separate from scientific project contents. */
export const layoutKeys = {
  imageShare: "dioptas-layout:image-share",
  controlsShare: "dioptas-layout:controls-share",
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
