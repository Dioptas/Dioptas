import type { IntegrationState } from "./integration";
import type { Raster, State } from "./types";

export interface CorrectionPreview {
  kind: string;
  label: string;
  units: string;
  convention: "divisor";
  raster: Raster;
}

/** Qt permits loaded flat/transfer maps while disabled; analytical maps exist
 * only while applied. Incomplete transfer pairs never have a preview. */
export function correctionPreviewAvailable(
  source: IntegrationState,
  kind: string,
) {
  if (kind === "flat") return !!source.flatField.filename;
  if (kind === "transfer")
    return !!source.transfer?.original && !!source.transfer?.response;
  return source.corrections[kind]?.enabled ?? false;
}

export function correctionPreviewContext(
  state: State | null,
  visible: boolean,
) {
  return JSON.stringify([
    visible,
    state?.revision,
    state?.configurationContext,
    state?.configurationIndex,
    state?.projectName,
    state?.imagePath,
    state?.selectedImageSource,
    state?.integration.frame,
    state?.shape,
    state?.calibration.transformations,
  ]);
}

/** Read-only commands do not dismiss the display. Edits dismiss immediately,
 * including failed edits, before any asynchronous native response can arrive. */
export function retainsCorrectionPreview(command: string) {
  return [
    "integration_correction_preview",
    "state",
    "pixel",
    "image_levels",
    "validation_position",
    "cake_profile",
    "save_cake_profile",
    "integration_save_spottiness",
    "integration_phase_state",
    "integration_phase_guides",
    "integration_diagnostics",
    "integration_autoprocess_poll",
    "save_project",
    "save_pattern",
    "save_combined_pattern",
    "batch_snapshot",
    "map_snapshot",
  ].includes(command);
}
