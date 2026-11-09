import type { Response } from "./types";
import type { PhaseReference } from "./integrationPhase";
/** Integration-only command/state contract; shared mask and calibration stay owned by Session. */
export type CorrectionMaterial = {
  mode: "manual" | "formula";
  formula: string;
  density: number;
};
export interface IntegrationState {
  roi: [number, number, number, number] | null;
  automaticBinning: boolean;
  actualBins: number;
  supersampling: number;
  method?: "polygon" | "pyfai_full" | "subpixel";
  sparseLayout?: "csc" | "csr" | "auto";
  azimuthRange: [number, number] | null;
  cakeAzimuthRange: [number, number] | null;
  cakeBins: number;
  solidAngle: boolean;
  polarization: number;
  poissonErrors: boolean;
  trimZeros: boolean;
  autoSave: boolean;
  formats: string[];
  outputDirectory: string;
  imageBackground: {
    filename: string | null;
    scale: number;
    offset: number;
    poisson?: boolean;
  };
  patternBackground: {
    enabled: boolean;
    smoothing: number;
    iterations: number;
    order: number;
    range: [number, number] | null;
    overlay: boolean;
  };
  transfer?: {
    original: string | null;
    response: string | null;
    enabled: boolean;
  };
  flatField: { filename: string | null; enabled: boolean };
  corrections: Record<
    string,
    {
      enabled: boolean;
      parameters: Record<string, number>;
      material?: CorrectionMaterial;
      container?: { enabled: boolean; material: CorrectionMaterial };
      fields: Record<string, { label: string; min: number; max: number }>;
    }
  >;
  overlayDirectory: string;
  waterfallSeparation: number;
  overlays: {
    uid: string;
    background: boolean;
    name: string;
    visible: boolean;
    color: string;
    scale: number;
    offset: number;
  }[];
  sameConditions: boolean;
  phaseColdPressure: boolean;
  phases: {
    uid?: string;
    name: string;
    pressure: number;
    temperature: number;
    visible: boolean;
    color: string;
    references: string[];
    reference: number;
    thermal: boolean;
    fileBacked: boolean;
    referenceDetails: PhaseReference[];
  }[];
  batchFrames: number;
  imageBatchMode?: "integrate" | "add" | "average" | "save";
  patternName: string;
  originalPatternColor?: string;
  originalPatternVisible?: boolean;
  patternPath: string;
  patternFileIteration: string;
  fileInfo: string;
  fileIteration: string;
  imageDirectory: string;
  autoProcess: boolean;
  autoProcessError: string;
  frame: number;
  frames: number;
}
export type IntegrationRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
  onSuccess?: (result: Response) => void,
) => Promise<void>;

/** UI-only identity for the non-removable measured-pattern row. */
export const ORIGINAL_PATTERN_UID = "original-pattern";
