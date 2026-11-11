import type { Raster, Unit } from "./types";
export interface BatchData {
  id: string;
  /** Stem of the explicitly opened processed file; preserved in projects. */
  exportBaseName?: string | null;
  waterfallKey?: string;
  raster: Raster;
  pattern: import("./types").Pattern;
  x: number[];
  unit: Unit;
  sourceUnit: Unit;
  mask: string | null;
  wavelength: number | null;
  files: { path: string; name: string; frames: number; first: number | null }[];
  entries: { path: string; name: string; frame: number }[];
  selected: number;
  total: number;
  canReintegrate: boolean;
  backgroundState?: import("./BatchBackgroundControls").BatchBackgroundState;
  sourceBins?: [number, number];
  normalized: boolean;
  normalizationRange: [number, number];
  normalizationReference: number;
  normalizationRegion?: { minimum: number; maximum: number; unit: Unit } | null;
  normalizationReferenceName?: string;
  calibration: string | null;
  /** Phase coordinates are d spacings in angstroms, independent of display unit. */
  phaseLines?: import("./types").Pattern["phaseLines"];
  position?: import("./linkedPosition").PatternPosition | null;
}
export type BatchRun = import("./windowCommandRpc").WindowRun;
