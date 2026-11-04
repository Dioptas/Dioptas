import { useEffect, useMemo, useState } from "react";
import type { Raster } from "./types";
import { useImageDisplayPreferences } from "./useImageDisplayPreferences";
export function useMapDisplay(raster: Raster | null, name: string) {
  // The scan panel moves between webviews. Restore contrast for exactly the
  // same raster content, while new layers continue to get their own Auto limits.
  const identity = useMemo(() => {
    if (name !== "map") return null;
    if (raster?.bufferId) return raster.bufferId;
    if (typeof raster?.data !== "string") return null;
    let hash = 2166136261;
    for (let i = 0; i < raster.data.length; i++)
      hash = Math.imul(hash ^ raster.data.charCodeAt(i), 16777619);
    return `${raster.width}:${raster.height}:${hash >>> 0}`;
  }, [name, raster?.data, raster?.bufferId, raster?.width, raster?.height]);
  const readSaved = (): {
    limits: [number, number];
    autoActive: boolean;
  } | null => {
    if (name === "map" && identity) {
      try {
        const saved = JSON.parse(
          localStorage.getItem("dioptas-map:contrast") ?? "null",
        );
        if (
          saved?.identity === identity &&
          Array.isArray(saved.limits) &&
          saved.limits.length === 2 &&
          saved.limits.every(Number.isFinite)
        )
          return {
            limits: saved.limits,
            autoActive: saved.autoActive === true,
          };
      } catch {
        /* Use source defaults. */
      }
    }
    return null;
  };
  const saved = readSaved();
  const readLimits = (): [number, number] =>
    saved?.limits ?? raster?.limits ?? [0, 1];
  const [current, setCurrent] = useState(() => ({
    source: raster?.data,
    limits: readLimits(),
  }));
  const limits =
    current.source === raster?.data ? current.limits : readLimits();
  if (current.source !== raster?.data)
    setCurrent({ source: raster?.data, limits });
  const setLimits = (next: [number, number], autoActive = false) => {
    setCurrent((previous) =>
      previous.source === raster?.data
        ? { source: raster?.data, limits: next }
        : previous,
    );
    if (name === "map" && identity) {
      try {
        localStorage.setItem(
          "dioptas-map:contrast",
          JSON.stringify({ identity, limits: next, autoActive }),
        );
      } catch {
        /* Session only. */
      }
    }
  };
  const [log, setLog] = useMapPreference<boolean>(`${name}-log`, false),
    [palette, setPalette] = useMapPreference<string>(`${name}-palette`, "grey");
  const [prefs, setPrefs] = useImageDisplayPreferences(
    name,
    "horizontal",
    false,
  );
  return {
    limits,
    setLimits,
    setAutoLimits: (next: [number, number]) => setLimits(next, true),
    initialLevelsReady: !!saved,
    initialAutoActive: saved?.autoActive ?? true,
    log,
    setLog,
    palette,
    setPalette,
    prefs,
    setPrefs,
  };
}
export function useMapPreference<T extends string | number | boolean>(
  name: string,
  fallback: T,
) {
  const key = `dioptas-map:${name}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(key) ?? "null");
      return typeof stored === typeof fallback &&
        (typeof stored !== "number" || Number.isFinite(stored))
        ? stored
        : fallback;
    } catch {
      return fallback;
    }
  });
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key !== key) return;
      try {
        const next = JSON.parse(event.newValue ?? "null");
        if (
          typeof next === typeof fallback &&
          (typeof next !== "number" || Number.isFinite(next))
        )
          setValue(next);
      } catch {
        /* Keep this window's preference. */
      }
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, [key, fallback]);
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* Session-only preference. */
    }
  }, [key, value]);
  return [value, setValue] as const;
}
