// Generated from command_payload_schema.json; do not edit by hand.

export type FileOrder = "number" | "time";

export type TransferSource = "original" | "response";

export type ConfigurationTarget = "file" | "folder";

export type ConfigurationScope = "active" | "all";

export type ResponseDisposition = "applied" | "cancelled" | "deferred" | "failed";

export type DecisionKind = "hdf5_source" | "image_change" | "calibration_change";

export interface RequestedProducts {
  cake: boolean;
  rings?: boolean;
}

export interface NativeTransportMetadata {
  requested_products?: RequestedProducts;
  defer_integration?: boolean;
}

export interface PixelPayload {
  x: number;
  y: number;
  source?: string | null;
}

export interface PickPeakPayload {
  x: number;
  y: number;
  ring: number;
  automatic?: boolean;
  search_size?: number;
}

export interface ImageSourcePayload {
  dataset: string;
}

export interface FrameNavigationPayload {
  frame?: number;
  direction?: number;
  step?: number;
  mode?: FileOrder;
}

export interface TransferPayload {
  source?: TransferSource;
  path?: string | null;
  enabled?: boolean;
  reset?: boolean;
}

export interface FlatFieldPayload {
  path?: string | null;
  enabled?: boolean;
  reset?: boolean;
}

export interface ImageBackgroundPayload {
  path?: string | null;
  reset?: boolean;
  scale?: number;
  offset?: number;
  poisson?: boolean;
}

export interface CombinationPayload {
  patterns?: boolean;
  cakes?: boolean;
  factor?: number;
}

export interface ConfigurationSelectPayload {
  index: number;
}

export interface ConfigurationRenamePayload {
  name: string;
}

export interface ConfigurationRemovePayload {
  index?: number;
}

export interface EmptyPayload {
}

export interface ConfigurationNavigationPayload {
  target: ConfigurationTarget;
  direction: number;
  step?: number;
  number_position?: number;
  mec?: boolean;
  scope?: ConfigurationScope;
  folder_number_position?: number;
  folder_filename_position?: number;
  folder_filename_step?: number;
}

export interface ProcessingWorkersPayload {
  workers?: number | null;
}

export interface CakeProfilePayload {
  two_theta: number;
  bins: number;
  shift: number;
  path?: string | null;
  directory?: string | null;
  suggested_name?: string | null;
}

export interface Hdf5CompanionPayload {
  directory?: string | null;
}

export interface NativePayloadContracts {
  pixel: PixelPayload;
  pick_peak: PickPeakPayload;
  select_image_source: ImageSourcePayload;
  integration_navigation: FrameNavigationPayload;
  integration_transfer: TransferPayload;
  integration_flat_field: FlatFieldPayload;
  integration_image_background: ImageBackgroundPayload;
  combination_settings: CombinationPayload;
  configuration_select: ConfigurationSelectPayload;
  configuration_navigation: ConfigurationNavigationPayload;
  processing_workers: ProcessingWorkersPayload;
  cake_profile: CakeProfilePayload;
  save_cake_profile: CakeProfilePayload;
  choose_hdf5_companion: Hdf5CompanionPayload;
  configuration: (ConfigurationSelectPayload & { operation?: "select" }) | (EmptyPayload & { operation: "add" }) | (EmptyPayload & { operation: "duplicate" }) | (ConfigurationRenamePayload & { operation: "rename" }) | (ConfigurationRemovePayload & { operation: "remove" });
}

export type NativeCoveredCommand = keyof NativePayloadContracts;
