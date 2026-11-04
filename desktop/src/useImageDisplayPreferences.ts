import { useEffect, useState } from "react";
import type { AutoLevels, ImageDisplayPreferences } from "./types";

export function readImageAutoLevels(
  display: string,
  filterGaps = true,
): AutoLevels {
  const key = `dioptas-auto-levels-v1:${display}`;
  const auto: AutoLevels = {
    mode: "percentile",
    percentile: 2.5,
    filter_gaps: filterGaps,
  };
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? "null");
    if (saved && typeof saved === "object") {
      if (["percentile", "minmax", "mean3std"].includes(saved.mode))
        auto.mode = saved.mode;
      if (
        typeof saved.percentile === "number" &&
        Number.isFinite(saved.percentile) &&
        saved.percentile >= 0.01 &&
        saved.percentile <= 25
      )
        auto.percentile = saved.percentile;
      if (typeof saved.filter_gaps === "boolean")
        auto.filter_gaps = saved.filter_gaps;
    }
  } catch {
    /* Use defaults if saved preferences cannot be read. */
  }
  return auto;
}

export function useImageDisplayPreferences(
  display: string,
  orientation: ImageDisplayPreferences["orientation"],
  filterGaps = true,
) {
  const key = `dioptas-auto-levels-v1:${display}`;
  const [preferences, setPreferences] = useState<ImageDisplayPreferences>(
    () => {
      const auto = readImageAutoLevels(display, filterGaps);
      return { size: "compact", orientation, auto };
    },
  );
  useEffect(() => {
    const auto = preferences.auto;
    // A temporarily empty or invalid numeric draft must not replace the
    // clipping preference used by the next app session.
    if (
      !Number.isFinite(auto.percentile) ||
      auto.percentile < 0.01 ||
      auto.percentile > 25
    )
      return;
    try {
      localStorage.setItem(key, JSON.stringify(auto));
    } catch {
      /* Keep session preferences when local storage is unavailable. */
    }
  }, [key, preferences.auto]);
  return [preferences, setPreferences] as const;
}
