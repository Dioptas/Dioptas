import { useState } from "react";
import type { Palette } from "./types";
import type { CrystalImageKind } from "./singleCrystalDomain";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
type Display = {
  limits: [number, number];
  log: boolean;
  palette: Palette;
  autoLevels: boolean;
};
const initial = (): Display => ({
  limits: [0, 1],
  log: false,
  palette: "gray",
  autoLevels: true,
});
/** Original, background and subtracted images retain independent display choices. */
export function useCrystalDisplay(kind: CrystalImageKind) {
  const [views, setViews] = useState<Record<CrystalImageKind, Display>>(() => ({
    raw: initial(),
    background: initial(),
    corrected: initial(),
  }));
  const raw = useImageDisplayPreferences("scxrd:raw", "vertical"),
    background = useImageDisplayPreferences("scxrd:background", "vertical"),
    corrected = useImageDisplayPreferences("scxrd:corrected", "vertical");
  const [preferences, setPreferences] = { raw, background, corrected }[kind];
  const update = <K extends keyof Display>(key: K, value: Display[K]) =>
    setViews((old) => ({ ...old, [kind]: { ...old[kind], [key]: value } }));
  return {
    ...views[kind],
    preferences,
    setPreferences,
    setLimits: (value: [number, number]) => update("limits", value),
    setLog: (value: boolean) => update("log", value),
    setPalette: (value: Palette) => update("palette", value),
    setAutoLevels: (value: boolean) => update("autoLevels", value),
  };
}
