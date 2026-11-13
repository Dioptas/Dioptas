import type { Response, State, AutoLevels } from "./types";
import type * as P from "./commandPayloads";
import type {
  NativePayloadContracts,
  NativeTransportMetadata,
} from "./nativePayloadContracts.generated";
export type { RequestedProducts } from "./nativePayloadContracts.generated";
import type { DetectorPresentation } from "./detectorSnapshot";

export type { JsonValue, JsonObject } from "./commandPayloads";
export type TransportMetadata = NativeTransportMetadata;

/** Snapshot patches are intentionally partial: pattern-only mutations retain
 * detector products. Aggregate Response remains the renderer's merge shape. */
export type WorkspaceDelta = Pick<
  Response,
  | "state"
  | "image"
  | "rawImage"
  | "mask"
  | "cake"
  | "pattern"
  | "rings"
  | "linked"
  | "phaseGuides"
  | "patternOnly"
  | "phaseOnly"
  | "clearImage"
  | "calibrationReset"
  | "imageStateReset"
  | "configurationReset"
  | "nextRing"
  | "noPeakFound"
  | "correctionNotice"
  | "preparedCorrections"
>;
type BatchDelta = WorkspaceDelta &
  Pick<
    Response,
    | "batch"
    | "batchWarning"
    | "batchPhaseLines"
    | "batchSelection"
    | "batchPosition"
    | "batchWavelength"
    | "batchOpened"
    | "batchWaterfallCreated"
  >;
type MapDelta = WorkspaceDelta &
  Pick<Response, "map" | "mapWarning" | "mapPending">;
type ProjectDelta = BatchDelta &
  MapDelta &
  Pick<Response, "configurationNavigation">;
type PhaseDelta = WorkspaceDelta &
  Pick<Response, "phaseEditor" | "phaseRevision">;
export type BatchSaved =
  | { savedPath: string; savedPaths?: never; exportedFrames?: number }
  | { savedPaths: string[]; exportedFrames: number; savedPath?: never };
type Saved = { savedPath: string; savedPaths?: string[] };
type Spec<Payload, Success> = { payload: Payload; success: Success };

/** The complete frontend scientific command surface. Host window-management
 * commands continue to use their purpose-specific Tauri API. */
export interface CommandContracts {
  scxrd_table: Spec<
    {
      kind: "tracks" | "reflections";
      offset: number;
      filter?: "all" | "usable" | "excluded";
    },
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_levels: Spec<
    AutoLevels,
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_pixel: Spec<
    { x: number; y: number; contour?: boolean },
    {
      scxrdPixel: {
        x: number;
        y: number;
        value: number | null;
        twoTheta: number | null;
        /** Constant-2θ line through the pixel, only when asked for. */
        contour?: import("./types").RingOverlay[] | null;
      } | null;
    }
  >;
  scxrd_snapshot: Spec<
    P.EmptyPayload,
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_load: Spec<
    { path?: string; paths?: string[] },
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_settings: Spec<
    { config: import("./singleCrystalDomain").CrystalConfig },
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_run: Spec<
    { stage: number; automatic?: boolean },
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_frame: Spec<
    { frame: number; kind?: import("./singleCrystalDomain").CrystalImageKind },
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_edit: Spec<
    import("./singleCrystalDomain").CrystalEdit,
    { scxrd: import("./singleCrystalDomain").CrystalData }
  >;
  scxrd_file: Spec<
    P.FilePayload & {
      operation: import("./singleCrystalDomain").CrystalFileOperation;
    },
    { scxrd: import("./singleCrystalDomain").CrystalData; savedPath?: string }
  >;
  state: Spec<P.EmptyPayload, ProjectDelta & { state: State }>;
  progress: Spec<
    P.EmptyPayload,
    { progress: NonNullable<Response["progress"]> }
  >;
  cancel_refinement: Spec<P.EmptyPayload, {}>;
  __host__: Spec<
    P.EmptyPayload,
    {
      runtime: "rust";
      protocol: number;
      transport: string;
      pid: number;
      engine?: string;
      qtApplication: boolean;
    }
  >;
  example: Spec<P.EmptyPayload, ProjectDelta>;
  open_image: Spec<
    P.ImageOpenPayload,
    ProjectDelta &
      Pick<Response, "imageUnavailable"> & {
        savedPaths?: string[];
        imageBatchSaved?: boolean;
      }
  >;
  next_image: Spec<
    {
      direction: P.Direction;
      step?: number;
      files_only?: boolean;
      pattern_only?: boolean;
      reset_calibration?: boolean;
      keep_calibration?: boolean;
      reset_image_state?: boolean;
    },
    ProjectDelta & Pick<Response, "imageUnavailable">
  >;
  choose_hdf5_companion: Spec<
    NativePayloadContracts["choose_hdf5_companion"],
    { chosenPath?: string }
  >;
  select_image_source: Spec<
    NativePayloadContracts["select_image_source"],
    ProjectDelta
  >;
  open_project: Spec<P.FilePayload, ProjectDelta>;
  save_project: Spec<P.FilePayload, Saved>;
  open_calibration: Spec<
    P.FilePayload & { clear_image?: boolean },
    WorkspaceDelta
  >;
  save_calibration: Spec<P.FilePayload, Saved>;
  reset_calibration: Spec<P.EmptyPayload, WorkspaceDelta>;
  open_calibrant: Spec<
    P.FilePayload & { validation?: boolean },
    WorkspaceDelta
  >;
  detector_file: Spec<P.FilePayload & { reset?: boolean }, WorkspaceDelta>;
  distortion_file: Spec<P.FilePayload & { reset?: boolean }, WorkspaceDelta>;
  calibration_setup: Spec<P.CalibrationSetupPayload, WorkspaceDelta>;
  fit_parameters: Spec<
    { parameters?: P.FitParameters; polarization?: number },
    WorkspaceDelta
  >;
  workflow_settings: Spec<P.WorkflowSettingsPayload, WorkspaceDelta>;
  manual_geometry: Spec<
    { convention: "pyfai" | "fit2d"; values: P.ManualGeometryValues },
    WorkspaceDelta
  >;
  calibrate: Spec<
    {
      restart?: boolean;
      refine?: boolean;
      parameters?: P.FitParameters;
      polarization?: number;
      engine?: "rust" | "dioptrin";
    },
    WorkspaceDelta
  >;
  pick_peak: Spec<NativePayloadContracts["pick_peak"], WorkspaceDelta>;
  remove_pick: Spec<{ index: number }, WorkspaceDelta>;
  remove_picks: Spec<{ indices: number[] }, WorkspaceDelta>;
  reassign_pick: Spec<{ index: number; ring: number }, WorkspaceDelta>;
  clear_peaks: Spec<P.EmptyPayload, WorkspaceDelta>;
  load_peaks: Spec<P.FilePayload, WorkspaceDelta>;
  save_peaks: Spec<P.FilePayload, Saved>;
  validation_calibrant: Spec<{ calibrant: string }, WorkspaceDelta>;
  validation_position: Spec<
    {
      x: number;
      unit?: import("./types").Unit;
      azimuth?: number;
      source?: "pattern" | "cake" | "detector" | "image";
      y?: number;
    },
    WorkspaceDelta & { linked: Response["linked"] }
  >;
  pixel: Spec<
    NativePayloadContracts["pixel"] & { raw?: boolean },
    { pixel: NonNullable<Response["pixel"]> }
  >;
  image_levels: Spec<
    P.LevelsPayload & { source?: "detector" | "raw_detector" | "cake" },
    Pick<Response, "levels" | "display">
  >;
  image_transform: Spec<
    {
      operation:
        | "rotate_left"
        | "rotate_right"
        | "flip_horizontal"
        | "flip_vertical"
        | "reset";
    },
    WorkspaceDelta
  >;
  image_batch_mode: Spec<{ mode: P.ImageBatchMode }, WorkspaceDelta>;
  settings: Spec<P.IntegrationSettingsPayload, WorkspaceDelta>;
  integration_settings: Spec<P.IntegrationSettingsPayload, WorkspaceDelta>;
  integrate: Spec<P.EmptyPayload, WorkspaceDelta>;
  display_products: Spec<{ cake?: boolean; rings?: boolean }, WorkspaceDelta>;
  integration_roi: Spec<
    { limits: [number, number, number, number] | null },
    WorkspaceDelta
  >;
  integration_background: Spec<P.PatternBackgroundPayload, WorkspaceDelta>;
  integration_clear_background: Spec<P.EmptyPayload, WorkspaceDelta>;
  integration_image_background: Spec<
    NativePayloadContracts["integration_image_background"],
    WorkspaceDelta
  >;
  integration_flat_field: Spec<
    NativePayloadContracts["integration_flat_field"],
    WorkspaceDelta
  >;
  integration_transfer: Spec<
    NativePayloadContracts["integration_transfer"],
    WorkspaceDelta
  >;
  integration_correction: Spec<P.CorrectionPayload, WorkspaceDelta>;
  integration_correction_preload: Spec<
    P.CorrectionContext,
    {
      correctionPreviewPending?: boolean;
      preparedCorrections?: Response["preparedCorrections"];
    }
  >;
  integration_correction_preview: Spec<
    P.CorrectionContext & P.LevelsPayload & { kind: P.CorrectionPreviewKind },
    { correctionPreview: NonNullable<Response["correctionPreview"]> }
  >;
  integration_overlay: Spec<P.OverlayPayload, WorkspaceDelta>;
  integration_open_pattern: Spec<
    P.FilePayload & { direction?: P.Direction; step?: number },
    WorkspaceDelta
  >;
  integration_pattern_navigation: Spec<{ mode: P.FileOrder }, WorkspaceDelta>;
  integration_navigation: Spec<
    NativePayloadContracts["integration_navigation"],
    WorkspaceDelta
  >;
  integration_output_directory: Spec<P.FilePayload, WorkspaceDelta>;
  integration_image_directory: Spec<P.FilePayload, WorkspaceDelta>;
  integration_autocreate: Spec<
    { enabled?: boolean; directory?: string },
    WorkspaceDelta
  >;
  integration_autoprocess: Spec<
    { enabled: boolean; directory?: string },
    WorkspaceDelta
  >;
  integration_autoprocess_poll: Spec<P.EmptyPayload, WorkspaceDelta>;
  integration_save_pattern: Spec<P.FigureExportPayload, Saved>;
  integration_save_image: Spec<P.FigureExportPayload, Saved>;
  integration_save_background: Spec<P.FilePayload, Saved>;
  integration_save_spottiness: Spec<
    P.FilePayload & { relative?: boolean; format?: string },
    Saved
  >;
  save_combined_pattern: Spec<P.FilePayload, Saved>;
  integration_diagnostics: Spec<
    P.EmptyPayload,
    { integrationDiagnostics: P.IntegrationDiagnostics }
  >;
  processing_workers: Spec<
    NativePayloadContracts["processing_workers"],
    WorkspaceDelta
  >;
  cake_profile: Spec<
    NativePayloadContracts["cake_profile"],
    { cakeProfile: NonNullable<Response["cakeProfile"]> }
  >;
  save_cake_profile: Spec<NativePayloadContracts["save_cake_profile"], Saved>;
  mask_file: Spec<
    P.FilePayload & { save?: boolean; add?: boolean; flipud?: boolean },
    WorkspaceDelta & Partial<Saved>
  >;
  mask_edit: Spec<P.MaskEditPayload, WorkspaceDelta>;
  mask_stroke: Spec<
    { points: [number, number][]; radius: number; erase?: boolean },
    WorkspaceDelta
  >;
  mask_plugin: Spec<P.MaskPluginPayload, WorkspaceDelta>;
  clear_mask: Spec<P.EmptyPayload, WorkspaceDelta>;
  undo_mask: Spec<P.EmptyPayload, WorkspaceDelta>;
  redo_mask: Spec<P.EmptyPayload, WorkspaceDelta>;
  undo_calibration: Spec<P.EmptyPayload, WorkspaceDelta>;
  redo_calibration: Spec<P.EmptyPayload, WorkspaceDelta>;
  integration_phase: Spec<P.PhasePayload, PhaseDelta>;
  integration_phase_state: Spec<P.EmptyPayload, PhaseDelta>;
  integration_phase_guides: Spec<
    { binary?: boolean },
    WorkspaceDelta & { phaseGuides: NonNullable<Response["phaseGuides"]> }
  >;
  integration_phase_editor: Spec<
    P.PhaseTarget,
    { phaseEditor: NonNullable<Response["phaseEditor"]>; phaseRevision: number }
  >;
  integration_phase_files: Spec<
    P.FilePayload & { paths?: string[] },
    { phaseImport: NonNullable<Response["phaseImport"]> }
  >;
  integration_phase_catalog: Spec<
    { query?: string },
    { phaseCatalog: NonNullable<Response["phaseCatalog"]> }
  >;
  integration_phase_documentation: Spec<
    { material_id: string; reference: number; kind: "report" | "record" },
    { documentationUrl: string }
  >;
  integration_phase_export: Spec<
    P.FilePayload &
      (P.PhaseTarget | { material_id: string }) & {
        material_id?: string;
        reference?: number;
        format?: string;
        save_current?: boolean;
      },
    Saved & Pick<Response, "phaseEditor" | "phaseRevision">
  >;
  integration_phase_list: Spec<
    P.FilePayload & { save?: boolean },
    PhaseDelta & Partial<Saved>
  >;
  configuration: Spec<NativePayloadContracts["configuration"], ProjectDelta>;
  configuration_select: Spec<
    NativePayloadContracts["configuration_select"],
    ProjectDelta
  >;
  configuration_navigation: Spec<
    NativePayloadContracts["configuration_navigation"],
    ProjectDelta
  >;
  combination_settings: Spec<
    NativePayloadContracts["combination_settings"],
    ProjectDelta
  >;
  custom_command: Spec<
    P.CustomCommandPayload,
    {
      customCommands?: Response["customCommands"];
      customCommandRuns?: Response["customCommandRuns"];
      customCommandContext?: Response["customCommandContext"];
    }
  >;
  batch_load: Spec<P.BatchLoadPayload, BatchDelta>;
  batch_load_data: Spec<P.BatchLoadPayload, BatchDelta>;
  batch_folder: Spec<P.BatchLoadPayload, BatchDelta>;
  batch_open: Spec<P.FilePayload, BatchDelta>;
  integration_batch: Spec<P.BatchLoadPayload, BatchDelta>;
  batch_snapshot: Spec<P.EmptyPayload, { batch: Response["batch"] }>;
  batch_select: Spec<
    {
      index: number;
      reintegrate?: boolean;
      position?: import("./linkedPosition").PatternPosition;
    },
    BatchDelta
  >;
  batch_unit: Spec<{ unit: import("./types").Unit }, BatchDelta>;
  batch_normalize: Spec<P.NormalizationPayload, BatchDelta>;
  batch_normalization_settings: Spec<P.NormalizationPayload, BatchDelta>;
  batch_waterfall: Spec<
    {
      series: string;
      bins: [number, number];
      rows: [number, number];
      step?: number;
    },
    BatchDelta
  >;
  batch_background_settings: Spec<
    { parameters?: P.BackgroundParameters; range?: [number, number] | null },
    BatchDelta
  >;
  batch_background_extract: Spec<
    { parameters?: P.BackgroundParameters; range?: [number, number] | null },
    BatchDelta
  >;
  batch_background_from_pattern: Spec<P.EmptyPayload, BatchDelta>;
  batch_background_display: Spec<
    { subtract?: boolean; cut?: boolean },
    BatchDelta
  >;
  batch_levels: Spec<P.LevelsPayload, { batchLevels: [number, number] | null }>;
  batch_folder_step: Spec<{ direction: P.Direction }, BatchDelta>;
  integration_save_batch: Spec<P.BatchExportPayload, BatchSaved>;
  map_load: Spec<P.BatchLoadPayload, MapDelta>;
  map_folder: Spec<P.BatchLoadPayload, MapDelta>;
  map_batch: Spec<P.FilePayload, MapDelta>;
  map_snapshot: Spec<P.EmptyPayload, { map: Response["map"] }>;
  map_select: Spec<
    {
      index?: number;
      row?: number;
      column?: number;
      slot?: number;
      reintegrate?: boolean;
      integration_view?: boolean;
    },
    MapDelta
  >;
  map_poll: Spec<{ check_only?: boolean; follow?: boolean }, MapDelta>;
  map_display: Spec<
    { smooth?: number; contours?: number },
    {
      mapPreview?: Response["mapPreview"];
      mapContours?: Response["mapContours"];
    }
  >;
  map_export: Spec<
    P.FilePayload & { png_data?: string; format?: string },
    Saved
  >;
  map_mask: Spec<
    { use_mask?: boolean; transparent_mask?: boolean; reintegrate?: boolean },
    MapDelta
  >;
  map_levels: Spec<P.LevelsPayload, { mapLevels: [number, number] | null }>;
  map_grid: Spec<
    {
      rows?: number;
      columns?: number;
      snake?: boolean;
      transpose?: boolean;
      flip_horizontal?: boolean;
      flip_vertical?: boolean;
    },
    MapDelta
  >;
  map_roi: Spec<P.MapRoiPayload, MapDelta>;
  map_expression: Spec<
    { name: string; expression?: string; new_name?: string; remove?: boolean },
    MapDelta
  >;
  map_layer: Spec<{ name: string }, MapDelta>;
  map_arrange: Spec<P.MapArrangePayload, MapDelta>;
  map_normalize: Spec<P.NormalizationPayload, MapDelta>;
}
export type CommandName = keyof CommandContracts;
export type CommandPayload<C extends CommandName> =
  CommandContracts[C]["payload"] & TransportMetadata;
export type CommandSuccess<C extends CommandName> =
  CommandContracts[C]["success"];
type ResultMetadata = {
  error?: string;
  activity?: { path?: string; paths?: string[]; count?: number };
  errorContext?: P.JsonValue;
};
type NoDecision = {
  imageChange?: never;
  calibrationChange?: never;
  hdf5SourceRequest?: never;
};
export type CommandResult<C extends CommandName> = C extends CommandName
  ? ResultMetadata &
      (
        | ({ ok: true; cancelled?: false } & NoDecision & CommandSuccess<C>)
        | ({ ok: false; error: string; cancelled?: boolean } & NoDecision &
            Partial<CommandSuccess<C>>)
        | ({ ok: boolean; cancelled: true } & NoDecision &
            Partial<CommandSuccess<C>>)
        | ({
            ok: true;
            cancelled?: boolean;
            imageChange: NonNullable<Response["imageChange"]>;
            calibrationChange?: never;
            hdf5SourceRequest?: never;
          } & Partial<CommandSuccess<C>>)
        | ({
            ok: true;
            cancelled?: boolean;
            calibrationChange: NonNullable<Response["calibrationChange"]>;
            imageChange?: never;
            hdf5SourceRequest?: never;
          } & Partial<CommandSuccess<C>>)
        | ({
            ok: true;
            cancelled?: boolean;
            hdf5SourceRequest: NonNullable<Response["hdf5SourceRequest"]>;
            imageChange?: never;
            calibrationChange?: never;
          } & Partial<CommandSuccess<C>>)
      )
  : never;

/** A mapped tuple keeps dynamic command names correlated with their payloads.
 * In particular a union name cannot be paired with an arbitrary union payload. */
export type CommandInvocation<C extends CommandName = CommandName> = {
  [K in C]: {} extends CommandPayload<K>
    ? [command: K, payload?: CommandPayload<K>]
    : [command: K, payload: CommandPayload<K>];
}[C];
export type CommandRequest<C extends CommandName = CommandName> = {
  [K in C]: { command: K; payload: CommandPayload<K> };
}[C];
type IsUnion<T, All = T> = T extends All
  ? [All] extends [T]
    ? false
    : true
  : never;
export type SingleCommand<C extends CommandName> = C &
  (IsUnion<C> extends true ? never : unknown);
type PayloadKeys<T> = T extends unknown ? keyof T : never;
export type ExactPayload<C extends CommandName, T> = T extends object
  ? T & Record<Exclude<keyof T, PayloadKeys<CommandPayload<C>>>, never>
  : T;
/** Extra keys must be rejected by the forwarding overload too; a structurally
 * assignable tuple alone would otherwise let literal typos escape validation. */
type ExtraInvocationKeys<A extends readonly [CommandName, ...unknown[]]> =
  A extends [
    command: infer C extends CommandName,
    payload: infer Payload,
    ...tail: unknown[],
  ]
    ? Exclude<keyof Payload, PayloadKeys<CommandPayload<C>>>
    : never;
export type CheckedInvocation<A extends readonly [CommandName, ...unknown[]]> =
  A &
    ([ExtraInvocationKeys<A>] extends [never]
      ? unknown
      : { readonly unexpectedPayloadKeys: ExtraInvocationKeys<A> });
export type CheckedRunInvocation<
  A extends readonly [CommandName, ...unknown[]],
> = CheckedInvocation<A>;
type ExtraRequestKeys<R extends CommandRequest> = R extends {
  command: infer C extends CommandName;
  payload: infer Payload;
}
  ? Exclude<keyof Payload, PayloadKeys<CommandPayload<C>>>
  : never;
export type CheckedRequest<R extends CommandRequest> = R &
  ([ExtraRequestKeys<R>] extends [never]
    ? unknown
    : { readonly unexpectedPayloadKeys: ExtraRequestKeys<R> });
export interface Invoke {
  <C extends CommandName>(
    command: SingleCommand<C>,
    ...args: {} extends CommandPayload<NoInfer<C>>
      ? [payload?: CommandPayload<NoInfer<C>>]
      : [payload: CommandPayload<NoInfer<C>>]
  ): Promise<CommandResult<C>>;
  <const A extends CommandInvocation>(
    ...call: CheckedInvocation<A>
  ): Promise<CommandResult<A[0]>>;
}
export type RunInvocation<C extends CommandName = CommandName> = {
  [K in C]: {} extends CommandPayload<K>
    ? [
        command: K,
        payload?: CommandPayload<K>,
        message?: string,
        onSuccess?: (result: CommandResult<K>) => void,
      ]
    : [
        command: K,
        payload: CommandPayload<K>,
        message?: string,
        onSuccess?: (result: CommandResult<K>) => void,
      ];
}[C];
export interface ScopedRun<Names extends CommandName = CommandName> {
  <C extends Names>(
    command: SingleCommand<C>,
    ...args: {} extends CommandPayload<NoInfer<C>>
      ? [
          payload?: CommandPayload<NoInfer<C>>,
          message?: string,
          onSuccess?: (result: CommandResult<C>) => void,
        ]
      : [
          payload: CommandPayload<NoInfer<C>>,
          message?: string,
          onSuccess?: (result: CommandResult<C>) => void,
        ]
  ): Promise<void>;
  <const A extends RunInvocation<Names>>(
    ...call: CheckedRunInvocation<A>
  ): Promise<void>;
}
export type Run = ScopedRun<CommandName>;
export type CommandAction<C extends CommandName = CommandName> = <
  const A extends CommandInvocation<C>,
>(
  ...call: CheckedInvocation<A>
) => void;
export type CommandRequestReader<C extends CommandName = CommandName> = <
  const A extends CommandInvocation<C>,
>(
  ...call: CheckedInvocation<A>
) => Promise<CommandResult<A[0]> | undefined>;

/** The detached detector snapshot has its own host command and transport. */
export type DetectorSnapshotResult =
  | { ok: true; presentation: DetectorPresentation | null }
  | { ok: false; error: string };
