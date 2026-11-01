import type { Raster, Unit } from "./types";
export interface MapRoi {
  name: string;
  min: number;
  max: number;
  reduction: string;
  background: boolean;
  color: string;
}
export interface MapData {
  raster: Raster;
  unit: Unit;
  points: number;
  canRebuild: boolean;
  dimension: [number, number];
  presets: [number, number][];
  snake: boolean;
  transpose: boolean;
  flip_horizontal: boolean;
  flip_vertical: boolean;
  active: string;
  rois: MapRoi[];
  expressions: Record<string, string>;
  selected: number | null;
  selectedCell: [number, number] | null;
  selectedSlot: number | null;
  slots: (number | null)[];
  labels: string[];
  excluded: number[];
  normalized: boolean;
  normalizationRange: [number, number];
  normalizationReference: number;
  indices: number[][];
  slotIndices: number[][];
  values: (number | null)[][];
}
export type MapRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => Promise<void>;
