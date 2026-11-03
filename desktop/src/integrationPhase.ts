export interface PhaseReference {
  label: string;
  assessment: string;
  detail: string;
}
export interface PhaseMaterial {
  id: string;
  name: string;
  spaceGroup: string;
  diffraction: boolean;
  defaultReference: number;
  hold: string;
  references: (PhaseReference & {
    eos: string;
    thermal: string;
    pressureRange: string;
    parameters: Record<string, number>;
    errors: Record<string, number | null>;
    fixed: string[];
    loadError: string;
  })[];
}
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
