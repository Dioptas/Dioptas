import type { AutoLevels, Calibration, Unit } from "./types";
import type { CorrectionMaterial } from "./integration";
import type { CustomCommand } from "./customCommands";

export type JsonValue =
  null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export interface EmptyPayload {}
export type Direction = -1 | 1;
export type FileOrder = "number" | "time";
export type ImageBatchMode = "integrate" | "add" | "average" | "save";
export interface FilePayload {
  path?: string;
  directory?: string;
  suggested_name?: string;
}
export interface Hdf5Binding {
  owner: string;
  stored_filename: string;
  actual_file: string;
}
export interface Hdf5Printf {
  owner: string;
  stored_filename: string;
  dataset?: string;
  mapping_index?: number;
  declared_dataset?: string;
  blocks: number;
}
export interface ReaderOptions {
  dataset?: string;
  follow_external_links?: boolean;
  hdf5_bindings?: Hdf5Binding[];
  hdf5_printf?: Hdf5Printf[];
  hdf5_snapshot?: boolean;
  source_frame?: number;
  cbf_dialect?: string;
}
export interface ImageOpenPayload extends FilePayload, ReaderOptions {
  frame?: number;
  multiple?: boolean;
  batch_mode?: ImageBatchMode;
  output_directory?: string;
  pattern_only?: boolean;
  reset_calibration?: boolean;
  keep_calibration?: boolean;
  reset_image_state?: boolean;
}
export type GeometryParameter =
  "dist" | "poni1" | "poni2" | "rot1" | "rot2" | "rot3" | "wavelength";
export type ManualGeometryValues = Partial<
  Record<
    | GeometryParameter
    | "pixel1"
    | "pixel2"
    | "polarization_factor"
    | "directDist"
    | "centerX"
    | "centerY"
    | "tilt"
    | "tiltPlanRotation"
    | "pixelX"
    | "pixelY",
    number
  >
>;
export type FitParameters = Partial<
  Record<
    GeometryParameter,
    {
      value?: number;
      refine?: boolean;
      min?: number | null;
      max?: number | null;
    }
  >
>;
export interface CalibrationSetupPayload {
  calibrant?: string;
  detector?: string;
  orientation?: number;
  wavelength?: number;
  distance?: number;
  pixel_x?: number;
  pixel_y?: number;
  fit_tilts?: boolean;
}
export type WorkflowSettingsPayload = Partial<Calibration["workflow"]>;
export interface IntegrationSettingsPayload {
  unit?: Unit;
  bins?: number | null;
  cake_bins?: number;
  use_mask?: boolean;
  transparent_mask?: boolean;
  polarization?: number;
  poisson_errors?: boolean;
  solid_angle?: boolean;
  supersampling?: number;
  method?: "polygon" | "subpixel" | "pyfai_full";
  trim_zeros?: boolean;
  auto_save?: boolean;
  azimuthal_std?: boolean;
  spottiness_relative?: boolean;
  sparse_layout?: "csc" | "csr" | "auto";
  azimuth_range?: [number, number] | null;
  cake_azimuth_range?: [number, number] | null;
  formats?: string[];
}
export interface BackgroundParameters {
  smoothing: number;
  iterations: number;
  order: number;
}
export interface PatternBackgroundPayload extends BackgroundParameters {
  enabled: boolean;
  range?: [number, number] | null;
}
export type CorrectionKind =
  "cbn" | "oiadac" | "plate" | "slab" | "cylinder" | "sphere";
export type CorrectionPreviewKind = CorrectionKind | "flat" | "transfer";
export type CorrectionParameters = Partial<
  Record<
    | "diamond_thickness"
    | "seat_thickness"
    | "small_cbn_seat_radius"
    | "large_cbn_seat_radius"
    | "tilt"
    | "tilt_rotation"
    | "center_offset"
    | "center_offset_angle"
    | "diamond_abs_length"
    | "cbn_abs_length"
    | "abs_length"
    | "thickness"
    | "incident_angle"
    | "detector_thickness"
    | "radius"
    | "height"
    | "density"
    | "capillary_radius"
    | "capillary_thickness"
    | "sample_radius"
    | "wall_thickness",
    number
  >
>;
export interface CorrectionPayload {
  kind: CorrectionKind;
  enabled?: boolean;
  parameters?: CorrectionParameters;
  material?: Partial<CorrectionMaterial>;
  container?: { enabled?: boolean; material?: Partial<CorrectionMaterial> };
}
export interface CorrectionContext {
  revision?: number;
  configuration?: number;
}
export type AtLeastOne<T> = Partial<T> &
  { [K in keyof T]-?: Required<Pick<T, K>> }[keyof T];
/** Native UIDs are preferred; index-only targets remain an explicit compatibility variant. */
export type OverlayTarget =
  { uid: string; index?: never } | { index: number; uid?: never };
export interface OverlayChanges {
  name?: string;
  color?: string;
  visible?: boolean;
  scale?: number;
  offset?: number;
}
export type OverlayPayload =
  | ({ operation: "load"; paths?: string[] } & FilePayload)
  | {
      operation:
        | "capture"
        | "capture_background"
        | "clear"
        | "waterfall"
        | "waterfall_auto"
        | "reset_offsets";
    }
  | { operation: "waterfall_separation"; separation: number }
  | { operation: "visibility" | "original_visibility"; visible: boolean }
  | { operation: "color_scale"; colors: string[] }
  | { operation: "original_color"; color: string }
  | ({ operation: "remove" | "background" | "match_intensity" } & OverlayTarget)
  | ({ operation: "move"; direction: Direction } & OverlayTarget)
  | ({ operation: "update" } & OverlayTarget & AtLeastOne<OverlayChanges>);
export type OverlayOperation = OverlayPayload["operation"];
export type PhaseEditorOperation =
  | "update"
  | "parameter"
  | "editor_parameter"
  | "editor_name"
  | "editor_ratio"
  | "reflection"
  | "editor_eos_type"
  | "editor_thermal_type"
  | "editor_thermal_parameter"
  | "editor_record"
  | "editor_metadata"
  | "editor_ranges"
  | "editor_space_group"
  | "editor_site"
  | "reload"
  | "editor_copy";
export type PhaseOperation =
  | PhaseEditorOperation
  | "editor_transaction"
  | "load"
  | "load_database"
  | "dac_thermal_pressure"
  | "same_conditions"
  | "clear"
  | "visibility_all"
  | "remove"
  | "move";
export type PhaseTarget =
  | { index: number; editor_uid?: string }
  | { index?: number; editor_uid: string };
/** EoS parameter names/record metadata are schema-driven extension values. Their
 * JSON values stay explicit rather than weakening every command's payload. */
export interface PhaseEditFields extends FilePayload {
  index?: number;
  editor_uid?: string;
  editor?: boolean;
  editor_only?: boolean;
  paths?: string[];
  material_id?: string;
  minimum_d_spacing?: number;
  intensity_cutoff?: number;
  assume_structure?: boolean;
  pressure?: number;
  temperature?: number;
  reference?: number;
  visible?: boolean;
  color?: string;
  enabled?: boolean;
  factor?: number;
  direction?: Direction;
  parameter?: string;
  value?: string | number | boolean | null;
  action?:
    | "add"
    | "duplicate"
    | "delete"
    | "clear"
    | "default"
    | "rename"
    | "remove"
    | "update";
  row?: number;
  rows?: number[];
  site?: Record<string, string | number | null>;
  ranges?: JsonObject;
  record_index?: number;
  expected_record_token?: string;
  changes?: JsonObject;
}
export type PhasePayload = PhaseEditFields &
  (
    | { operation: "load"; path?: string; paths?: string[] }
    | { operation: "load_database"; material_id: string }
    | { operation: "dac_thermal_pressure"; enabled?: boolean; factor?: number }
    | { operation: "same_conditions"; enabled: boolean }
    | { operation: "visibility_all"; visible: boolean }
    | { operation: "clear" }
    | ({ operation: "move"; direction: Direction } & PhaseTarget)
    | ({ operation: "remove" | "reload" | "editor_copy" } & PhaseTarget)
    | ({ operation: "update" } & PhaseTarget &
        AtLeastOne<{
          pressure: number;
          temperature: number;
          reference: number;
          visible: boolean;
          color: string;
        }>)
    | ({
        operation: Exclude<
          PhaseEditorOperation,
          "update" | "reload" | "editor_copy"
        >;
      } & PhaseTarget)
    | ({
        operation: "editor_transaction";
        edit_operation: PhaseEditorOperation;
      } & PhaseTarget)
  );
export type PhaseEditorEdit = <O extends PhaseEditorOperation>(
  operation: O,
  args?: PhaseEditFields,
) => Promise<boolean>;
export type MaskEditPayload = { erase?: boolean } & (
  | {
      operation: "rectangle" | "circle" | "polygon" | "arc";
      points: [number, number][];
    }
  | { operation: "above" | "below"; threshold: number }
  | {
      operation: "range";
      lower?: number | null;
      upper?: number | null;
      unit?: Unit;
      outside?: boolean;
    }
  | { operation: "grow" | "shrink" | "invert" | "clear" | "cosmic" }
);
export type MaskOperation = MaskEditPayload["operation"];
export type MaskPluginPayload = {
  index: number;
  operation?: "enable" | "settings" | "imprint" | "reset";
  enabled?: boolean;
  settings?: Record<string, string | number | boolean>;
};
export interface NormalizationPayload {
  enabled?: boolean;
  reference?: number;
  start?: number;
  stop?: number | null;
  minimum?: number;
  maximum?: number;
  unit?: Unit;
  window?: string;
}
export interface BatchLoadPayload extends FilePayload, ReaderOptions {
  paths?: string[];
  reintegrate?: boolean;
  mask?: string;
  pattern_only?: boolean;
}
export interface BatchExportPayload extends FilePayload {
  format?: "h5" | "nxs" | "csv" | "xy" | "chi" | "dat" | "fxye" | "png";
  unit?: Unit;
  png_data?: string;
}
export type MapReduction = "sum" | "mean" | "max" | "area" | "center" | "width";
export interface MapWindowChanges {
  minimum?: number;
  maximum?: number;
  reduction?: MapReduction;
  background?: boolean;
  color?: string;
  new_name?: string;
  activate?: boolean;
}
export type MapRoiPayload =
  | { op: "add" }
  | { op: "remove"; name: string }
  | ({ op?: "update"; name: string } & MapWindowChanges);
export interface MapArrangePayload {
  op: "exclude" | "insert" | "remove" | "move" | "gaps";
  index?: number | null;
  slot?: number | null;
  offset?: number;
}
export type CustomCommandOperation = "list" | "save" | "delete" | "run";
export type CustomCommandPayload =
  | { operation: "list" }
  | { operation: "save"; command: CustomCommand }
  | { operation: "delete" | "run"; identifier: string };
export interface FigureExportPayload extends FilePayload {
  format?: string;
  subtract_background?: boolean;
  svg_data?: string;
  png_data?: string;
  source?: "image" | "cake";
  figure?: JsonObject;
}
export type LevelsPayload = Partial<AutoLevels> & { clipping?: number };
