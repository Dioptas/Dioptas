import type { PhaseEditorData as BasePhaseEditorData } from "./integrationPhase";

export interface EditorField {
  key: string;
  label: string;
  unit: string;
  value: number | string | null;
  min?: number;
  max?: number;
  integer?: boolean;
  required?: boolean;
  default?: number | string | null;
  choices?: string[];
  isDefault?: boolean;
}
export interface EditorData extends BasePhaseEditorData {
  name: string;
  editError?: string;
  pressure: number;
  coldPressure: boolean;
  temperature: number;
  modified: boolean;
  origin: string;
  recordOrigin: string;
  recordLabel: string;
  defaultReference: number;
  eosFields: EditorField[];
  materialFields: EditorField[];
  recordData: Record<string, unknown> | null;
  thermalFields: EditorField[];
  thermalSelection: string;
  eosOptions: { value: string; error: string }[];
  thermalOptions: { value: string; error: string }[];
  structure: {
    spaceGroup: string;
    spaceGroupNumber: number | null;
    groups: { number: number; symbol: string }[];
    sites: Record<string, string | number | null>[];
    formula: string;
    storedZ: number | null;
    calculatedZ: number | null;
    compositionStatus: string;
    compositionDetail: string;
    modified: boolean;
    assumption: string;
  };
}

export type EditorEdit = (
  operation: string,
  args?: Record<string, unknown>,
) => Promise<boolean>;
