import type { PhaseReference } from "./integrationPhase";

export interface DatabaseRecord extends PhaseReference {
  eos: string;
  thermal: string;
  pressureRange: string;
  parameters: Record<string, number | null>;
  errors: Record<string, number | null>;
  fixed: string[];
  loadError: string;
  assumedLoadError: string;
  authors: string;
  year: string;
  identifier: string;
  citation: string;
  notes: string;
  temperatureRange: [number, number] | null;
  temperatureRef: number | null;
  thermalParameters: Record<string, unknown>;
  thermalErrors: Record<string, number | null>;
  thermalFixed: string[];
  reportUrl: string;
  recordUrl: string;
  sourceRecord: Record<string, unknown>;
}
export interface DatabaseMaterial {
  id: string;
  name: string;
  formula: string;
  spaceGroup: string;
  diffraction: boolean;
  diffractionStatus: string;
  canAssumeStructure: boolean;
  assumptionNote: string;
  defaultReference: number;
  hold: string;
  notes: string;
  references: DatabaseRecord[];
}
