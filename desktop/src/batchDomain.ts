import type { Raster, Unit } from "./types";
export interface BatchData {
  raster: Raster;
  pattern: import("./types").Pattern;
  x: number[];
  unit: Unit;
  wavelength: number | null;
  entries: { path: string; name: string; frame: number }[];
  selected: number;
  total: number;
  canReintegrate: boolean;
  normalized: boolean;
  normalizationRange: [number, number];
  normalizationReference: number;
  calibration: string | null;
}
export type BatchRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => Promise<void>;
