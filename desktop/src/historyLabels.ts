import type { State } from "./types";

const peakEdits = new Set([
  "pick_peak",
  "remove_pick",
  "remove_picks",
  "clear_peaks",
  "load_peaks",
  "reassign_pick",
]);
const geometryEdits = new Set([
  "calibrate",
  "manual_geometry",
  "open_calibration",
  "calibration_setup",
  "calibration_engine",
  "fit_parameters",
  "open_calibrant",
  "validation_calibrant",
  "image_transform",
  "open_image",
  "next_image",
  "detector_file",
  "distortion_file",
]);
const historyCommands = new Set([
  "undo_mask",
  "redo_mask",
  "undo_calibration",
  "redo_calibration",
]);
export const isScientificHistoryCommand = (command: string) =>
  historyCommands.has(command);
export const isCalibrationHistoryCommand = (command: string) =>
  isScientificHistoryCommand(command) && command.endsWith("_calibration");
/** Native masks have their own history; calibration and integration share one.
 * The comparison backend supplies explicit labels for its global history. */
export const scientificHistoryAction = (
  state: State | null,
  mode: string,
  redo = false,
) => {
  const label = redo ? state?.redoLabel : state?.undoLabel;
  return label ?? (mode === "mask" ? "mask_edit" : undefined);
};
export const canTraverseScientificHistory = (
  state: State | null,
  redo = false,
  mode = "calibration",
) => {
  if (
    state?.undoLabel !== undefined ||
    state?.redoLabel !== undefined ||
    mode === "mask"
  )
    return !!(redo ? state?.canRedoMask : state?.canUndoMask);
  return !!(redo ? state?.calibration?.canRedo : state?.calibration?.canUndo);
};

/** Name explicit history actions when supplied by the processor. */
export function historyActionLabel(action?: string) {
  if (!action) return "scientific edit";
  if (action.startsWith("mask_") || action === "clear_mask") return "mask edit";
  if (peakEdits.has(action)) return "calibration edit: peak selections";
  if (action === "open_image") return "image load";
  if (action === "next_image") return "image navigation";
  if (geometryEdits.has(action))
    return `calibration edit: ${action.replaceAll("_", " ")}`;
  if (action === "integration_overlay") return "overlay edit";
  if (action === "integration_settings") return "integration options";
  if (action === "integration_phase") return "phase edit";
  return action.replaceAll("_", " ");
}

export function scientificHistoryCommand(
  action: string | undefined,
  redo = false,
) {
  const preserveFit =
    !!action && !peakEdits.has(action) && !geometryEdits.has(action);
  return `${redo ? "redo" : "undo"}_${preserveFit ? "mask" : "calibration"}`;
}
