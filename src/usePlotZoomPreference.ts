import { useEffect, useState } from "react";
import type { ZoomMode } from "./usePlotNavigation";

/** Remember the navigation tool independently of a plot's current axis range. */
export function usePlotZoomPreference(
  plot: "pattern" | "cake" | "map-pattern" | "cake-profile",
) {
  const key = `dioptas-plot-zoom-v1:${plot}`;
  const [mode, setMode] = useState<ZoomMode>(() => {
    try {
      if (plot === "cake-profile")
        return localStorage.getItem(key) === "vertical"
          ? "vertical"
          : "rectangle";
      return localStorage.getItem(key) === "horizontal"
        ? "horizontal"
        : "rectangle";
    } catch {
      return "rectangle";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, mode);
    } catch {
      /* Keep the session choice when local storage is unavailable. */
    }
  }, [key, mode]);
  return [mode, setMode] as const;
}
