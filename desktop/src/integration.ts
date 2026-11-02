/** Integration-only command/state contract; shared mask and calibration stay owned by Session. */
export interface IntegrationState {
  roi: [number, number, number, number] | null;
  automaticBinning: boolean;
  actualBins: number;
  supersampling: number;
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
  imageBackground: { filename: string | null; scale: number; offset: number };
  patternBackground: {
    enabled: boolean;
    smoothing: number;
    iterations: number;
    order: number;
    range: [number, number] | null;
    overlay: boolean;
  };
  flatField: { filename: string | null; enabled: boolean };
  corrections: Record<
    string,
    {
      enabled: boolean;
      parameters: Record<string, number>;
      fields: Record<string, { label: string; min: number; max: number }>;
    }
  >;
  overlays: {
    name: string;
    visible: boolean;
    color: string;
    scale: number;
    offset: number;
  }[];
  sameConditions: boolean;
  phases: {
    name: string;
    pressure: number;
    temperature: number;
    visible: boolean;
    color: string;
    references: string[];
    reference: number;
  }[];
  batchFrames: number;
  patternName: string;
  fileInfo: string;
  fileIteration: string;
  frame: number;
  frames: number;
}
export type IntegrationRun = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => Promise<void>;
