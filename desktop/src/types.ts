import type {
  PhaseEditorData,
  PhaseImport,
  PhaseMaterial,
} from "./integrationPhase";
import type { MapData } from "./mapDomain";
export type Unit = "2th_deg" | "q_A^-1" | "d_A";
export type Tool = "pan" | "mask" | "erase" | "pick";
export type Palette = string;
export interface AutoLevels {
  mode: "percentile" | "minmax" | "mean3std";
  percentile: number;
  filter_gaps: boolean;
}
export interface ImageDisplayPreferences {
  orientation: "vertical" | "horizontal";
  auto: AutoLevels;
}
export interface Raster {
  width: number;
  height: number;
  fullWidth: number;
  fullHeight: number;
  step: number;
  dtype: "u8" | "f32le";
  limits: [number, number];
  // Frontend annotation: these limits already use this source's Auto settings.
  autoLevels?: AutoLevels;
  data: string | ArrayBuffer | Uint8Array<ArrayBuffer>;
  bufferId?: string;
  histogram?: { edges: number[]; counts: number[]; finitePixels: number };
}
export interface Cake extends Raster {
  radialRange: [number, number];
  azimuthRange: [number, number];
  unit: Unit;
}
export interface Spottiness {
  x: number[];
  mean: (number | null)[];
  std: (number | null)[];
  relative: (number | null)[];
}
export interface Pattern {
  /** Original integrated observables, before any pattern-background operations. */
  spottiness?: Spottiness | null;
  sigma?: (number | null)[] | null;
  azimuthalStd?: (number | null)[] | null;
  x: number[];
  y: (number | null)[];
  unit: Unit;
  backgroundCurves?: {
    name: string;
    color: string;
    x: number[];
    y: (number | null)[];
  }[];
  curves?: {
    name: string;
    color: string;
    x: number[];
    y: (number | null)[];
    selected?: boolean;
  }[];
  phaseLines?: {
    phaseIndex?: number;
    x: number;
    intensity: number;
    name: string;
    color: string;
    hkl: number[];
  }[];
}
export interface State {
  processingWorkers?: {
    requested: number | null;
    effective: number;
    available: number;
    automatic: number;
  };
  supportsRequestedProducts?: boolean;
  revision: number;
  hasImage: boolean;
  imageName: string | null;
  imagePath: string | null;
  imageSources?:
    { dataset: string; frames: number; shape: [number, number] }[] | null;
  selectedImageSource?: string | null;
  automaticImageSource?: boolean;
  imageSourceError?: string | null;
  shape: [number, number] | null;
  calibrationName: string | null;
  calibrated: boolean;
  projectName: string | null;
  unit: Unit;
  bins: number | null;
  useMask: boolean;
  transparentMask: boolean;
  maskedPixels: number;
  canUndoMask: boolean;
  canRedoMask: boolean;
  undoLabel?: string;
  redoLabel?: string;
  maskDetails: import("./maskDomain").MaskDetails;
  exampleAvailable: boolean;
  elapsedMs: number | null;
  integrationDirty: boolean;
  configurationCount: number;
  configurationIndex: number;
  configurationLabels?: string[];
  configurationContext?: number;
  combination?: {
    patterns: boolean;
    cakes: boolean;
    ready: boolean;
    reason: string | null;
    factor: number;
    configurations: {
      index: number;
      imageName: string;
      calibrated: boolean;
      factor: number;
    }[];
    backends: Record<string, string>;
  };
  geometry: {
    dist: number;
    poni1: number;
    poni2: number;
    wavelength: number;
    rot1: number;
    rot2: number;
    rot3: number;
  };
  integration: import("./integration").IntegrationState;
  calibration: Calibration;
}
export interface Calibration {
  setupConfirmed: boolean;
  detectorIsCustom: boolean;
  detectorOrientation?: number;
  detectorAssignment?: string | null;
  detectorCandidates?: string[];
  referenceLines: { ring: number; x: number }[];
  workflow: {
    autoIncrement: boolean;
    searchSize: number;
    automaticRefinement: boolean;
    algorithm: string;
    deltaTth: number;
    meanFactor: number;
    intensityLimit: number;
    numberOfRings: number;
  };
  parameters: Record<string, { value: number; refine: boolean }>;
  freeParameterCount: number;
  polarization: number;
  fitWavelength: boolean;
  detectorFile: string | null;
  distortionFile: string | null;
  transformations: string[];
  pyfai: Record<string, number>;
  fit2d: Record<string, number>;
  steps: string[];
  geometrySource: string;
  canUndo: boolean;
  canRedo: boolean;
  engine: string;
  engineLabel: string;
  engines: { id: string; label: string; available: boolean }[];
  calibrant: string;
  calibrants: string[];
  detectors: string[];
  detector: string;
  pixelX: number;
  pixelY: number;
  distance: number;
  wavelength: number;
  fitTilts: boolean;
  fitDirty: boolean;
  rmsDegrees: number | null;
  saved: boolean;
  picks: { ring: number; points: number[][] }[];
  rings: { ring: number; twoTheta: number }[];
}
export interface RingOverlay {
  ring: number;
  color?: string;
  lineWidth?: number;
  opacity?: number;
  phaseIndex?: number;
  reflectionIndex?: number;
  twoTheta?: number;
  points: number[][];
}
export interface Response {
  imageUnavailable?: boolean;
  configurationNavigation?: { advanced: number[]; skipped: number[] };
  configurationReset?: boolean;
  calibrationChange?: {
    path: string;
    imageShape: [number, number];
    calibrationShape: [number, number] | null;
  };
  imageStateReset?: boolean;
  imageChange?: {
    calibrated?: boolean;
    canKeepCalibration?: boolean;
    options?: Record<string, unknown>;
    path: string;
    frame: number;
    previousShape: [number, number];
    newShape: [number, number];
  };
  calibrationReset?: boolean;
  savedPaths?: string[];
  clearImage?: boolean;
  customCommands?: import("./customCommands").CustomCommand[];
  customCommandRuns?: Record<
    string,
    import("./customCommands").CustomCommandRun
  >;
  customCommandContext?: import("./customCommands").CommandContext;
  phaseRevision?: number;
  batch?: import("./batchDomain").BatchData | null;
  /** Phase references in d spacings (Å), independent of the batch display unit. */
  batchPhaseLines?: Pattern["phaseLines"];
  batchSelection?: number;
  batchPosition?: import("./linkedPosition").PatternPosition;
  batchWavelength?: number | null;
  batchOpened?: boolean;
  batchWaterfallCreated?: boolean;
  batchLevels?: [number, number];
  batchWarning?: string | null;
  phaseEditor?: PhaseEditorData;
  phaseImport?: PhaseImport;
  phaseCatalog?: PhaseMaterial[];
  map?: MapData | null;
  mapPending?: number;
  mapLevels?: [number, number];
  mapWarning?: string | null;
  mapPreview?: Raster;
  mapContours?: number[][][];
  ok: boolean;
  error?: string;
  cancelled?: boolean;
  patternOnly?: boolean;
  phaseOnly?: boolean;
  state?: State;
  image?: Raster;
  rawImage?: Raster;
  phaseGuides?: RingOverlay[];
  mask?: Raster;
  cake?: Cake | null;
  pattern?: Pattern | null;
  savedPath?: string;
  correctionNotice?: string;
  pixel?: {
    x: number;
    y: number;
    value: number | null;
    twoTheta?: number;
    twoThetaResolution?: number;
  };
  nextRing?: number;
  noPeakFound?: boolean;
  levels?: [number, number] | null;
  display?: "detector" | "cake";
  progress?: {
    running: boolean;
    current: number;
    total: number;
    label?: string;
    fps?: number;
    elapsedSeconds?: number;
    mapPreview?: {
      raster: Raster;
      completed: number;
      total: number;
      active: string;
      unit: Unit;
      pattern: Pattern;
    };
    calibration?: {
      activeRing: number | null;
      picks: Calibration["picks"];
      rings: RingOverlay[];
      rmsDegrees: number | null;
    };
  };
  linked?: {
    twoTheta: number;
    radial: number;
    contours: RingOverlay[];
    azimuth?: number | null;
    imagePoint?: { x: number; y: number } | null;
  } | null;
  rings?: RingOverlay[];
}
export type Invoke = (
  command: string,
  args?: Record<string, unknown>,
) => Promise<Response>;
declare global {
  interface Window {
    pywebview?: { api: { invoke: Invoke } };
  }
}
export const unitLabel = (unit: Unit) =>
  ({ "2th_deg": "2θ (°)", "q_A^-1": "Q (Å⁻¹)", d_A: "d (Å)" })[unit];
export const number = (value: number, digits = 2) =>
  value.toLocaleString("en-US", { maximumFractionDigits: digits });
