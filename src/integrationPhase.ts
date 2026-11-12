export interface PhaseReference {
  label: string;
  assessment: string;
  detail: string;
}
export type { DatabaseMaterial as PhaseMaterial } from "./phaseDatabaseTypes";
export interface PhaseImport {
  paths: string[];
  minimumDSpacing: number;
}
export interface PhaseEditorData {
  index: number;
  filename: string;
  editable: boolean;
  eosEditable: boolean;
  canReload: boolean;
  symmetry: string;
  lattice: Record<string, number>;
  latticeEditable: string[];
  eosType: string;
  thermalType: string;
  eosParameters: Record<string, number>;
  references: PhaseReference[];
  reference: number;
  reflections: {
    h: number;
    k: number;
    l: number;
    intensity: number;
    d0: number;
    d: number;
    twoTheta: number | null;
  }[];
}
