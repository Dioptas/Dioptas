// Enabled only in benchmark builds. The explicit native benchmark observes the
// real App, Tauri binary bridge and shared renderers without replacing them.
import type { Raster, State } from "./types";

export type NavigationProbe = {
  run: (action: string, payload?: Record<string, unknown>) => Promise<void>;
  state: () => State | null;
  image: () => Raster | null;
};
declare global {
  interface Window {
    __dioptasNavigationProbe?: NavigationProbe;
    __dioptasNavigationTrace?: (event: {
      stage: string;
      at: number;
      [key: string]: unknown;
    }) => void;
  }
}
export const navigationTimingEnabled =
  import.meta.env?.VITE_DIOPTAS_NAVIGATION_BENCHMARK === "1";

export function navigationTrace(
  stage: string,
  fields: Record<string, unknown> = {},
) {
  if (navigationTimingEnabled)
    window.__dioptasNavigationTrace?.({
      stage,
      at: performance.now(),
      ...fields,
    });
}
