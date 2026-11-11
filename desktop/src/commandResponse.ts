import type { AutoLevels, Invoke, Raster, Response, State } from "./types";
import type { CommandResult } from "./commandCoordinator";
import type { CalibrationResetRequest } from "./CalibrationResetDialog";
import { restoreMapPosition } from "./linkedPosition.ts";
import { prepareDetectorImage } from "./prepareDetectorImage.ts";
import { fileOperationFailure } from "./errorReporting.ts";
import {
  historyActionLabel,
  isCalibrationHistoryCommand,
  isScientificHistoryCommand,
} from "./historyLabels.ts";

type DeferredResponse =
  | { kind: "hdf5"; request: NonNullable<Response["hdf5SourceRequest"]> }
  | { kind: "calibration"; request: CalibrationResetRequest };
export function deferredResponse(
  result: Response,
): DeferredResponse | undefined {
  // Resolve source/geometry decisions before ordinary error handling. These
  // replies ask for a decision instead of publishing a workspace snapshot.
  if (result.hdf5SourceRequest)
    return { kind: "hdf5", request: result.hdf5SourceRequest };
  const request = result.imageChange ?? result.calibrationChange;
  if (request) return { kind: "calibration", request };
}
export type CompletionEffect =
  | { kind: "draft"; target: "integration" | "geometry" | "fit"; state: State }
  | { kind: "notice"; message: string | null }
  | { kind: "autoprocess-error"; message: string | null }
  | { kind: "clear-picks" }
  | { kind: "calibration-step"; step: 0 | 3 };
/** Pure post-command policy. Ordering determines the final notice and preserves
 * cancellation semantics: publish its snapshot/callback, retain option drafts. */
export function commandCompletion(
  command: string,
  args: Record<string, unknown>,
  result: Response,
  historyLabel?: string,
  pendingDrafts = false,
): CompletionEffect[] {
  const effects: CompletionEffect[] = [];
  const notice = (message: string | null) =>
    effects.push({ kind: "notice", message });
  if (command === "next_image" && result.ok)
    notice(
      result.imageUnavailable
        ? Number(args.direction ?? 1) < 0
          ? "No previous image available"
          : "No new image available"
        : null,
    );
  if (!result.cancelled && result.state) {
    const state = result.state;
    if (["open_project", "example"].includes(command))
      effects.push({ kind: "draft", target: "integration", state });
    if (["open_project", "example", "open_calibration"].includes(command)) {
      effects.push({ kind: "draft", target: "geometry", state });
      effects.push({ kind: "draft", target: "fit", state });
    }
    if (command === "manual_geometry")
      effects.push({ kind: "draft", target: "geometry", state });
    if (command === "calibrate")
      effects.push({ kind: "draft", target: "fit", state });
  }
  if (command === "save_project" && result.savedPath && pendingDrafts)
    notice(
      `Saved ${result.savedPath.split(/[\\/]/).at(-1)} · unapplied option drafts remain in this session`,
    );
  if (result.correctionNotice) notice(result.correctionNotice);
  if (command === "pick_peak" && result.noPeakFound)
    notice("No peaks found in this area");
  if (command === "open_calibration" && !result.cancelled)
    notice(
      `Loaded calibration: ${result.state?.calibrationName ?? "PONI"}${result.state?.hasImage ? "" : " · Load a matching detector image"}`,
    );
  if (isScientificHistoryCommand(command))
    notice(
      `${command.startsWith("undo") ? "Undid" : "Redid"} ${historyActionLabel(historyLabel)}`,
    );
  if (command === "integration_autoprocess_poll" && result.state)
    effects.push({
      kind: "autoprocess-error",
      message: result.state.integration.autoProcessError || null,
    });
  if (
    (command === "load_peaks" && !result.cancelled) ||
    isCalibrationHistoryCommand(command) ||
    [
      "clear_peaks",
      "remove_pick",
      "remove_picks",
      "open_image",
      "select_image_source",
      "example",
      "image_transform",
      "open_project",
    ].includes(command)
  )
    effects.push({ kind: "clear-picks" });
  if (
    !result.cancelled &&
    ["calibrate", "manual_geometry", "open_calibration"].includes(command)
  )
    effects.push({
      kind: "calibration-step",
      step: command === "open_calibration" && !result.state?.hasImage ? 0 : 3,
    });
  return effects;
}
export interface CommandCompletionPorts {
  drafts: {
    integration(state: State): void;
    geometry(calibration: State["calibration"]): void;
    fit(calibration: State["calibration"]): void;
  };
  workflow: {
    notice(message: string | null): void;
    error(message: string | null): void;
    clearPicks(): void;
    calibrationStep(step: 0 | 3): void;
  };
}
function complete(effects: CompletionEffect[], ports: CommandCompletionPorts) {
  for (const effect of effects)
    switch (effect.kind) {
      case "draft":
        if (effect.target === "integration")
          ports.drafts.integration(effect.state);
        else ports.drafts[effect.target](effect.state.calibration);
        break;
      case "notice":
        ports.workflow.notice(effect.message);
        break;
      case "autoprocess-error":
        ports.workflow.error(effect.message);
        break;
      case "clear-picks":
        ports.workflow.clearPicks();
        break;
      case "calibration-step":
        ports.workflow.calibrationStep(effect.step);
        break;
    }
}
export interface CommandResponseContext {
  command: string;
  args: Record<string, unknown>;
  historyLabel?: string;
  invoke: Invoke;
  submit(): Promise<Response>;
  retryStoredMap(): Promise<Response>;
  selectedPosition: Response["linked"];
  pendingDrafts(): boolean;
  detector: {
    autoActive(): boolean;
    raw(): boolean;
    previous(raw: boolean): Raster | null;
    autoLevels(): AutoLevels;
  };
}
export interface CommandResponsePorts extends CommandCompletionPorts {
  defer(decision: DeferredResponse): void;
  apply(
    result: Response,
    resetImageView?: boolean,
    retainClick?: boolean,
  ): void;
  trace(event: string, result: Response): void;
  success?(result: Response): void;
}
/** A response transaction inside CommandCoordinator's reservation. All source
 * preparation finishes before snapshot publication and the caller's callback.
 * Scheduling and progress retain their independent coordinator/workflow owners. */
export async function handleCommandResponse(
  context: CommandResponseContext,
  ports: CommandResponsePorts,
): Promise<CommandResult<Response>> {
  const { command, args, invoke } = context;
  try {
    let result = await context.submit();
    ports.trace("command-response", result);
    const deferred = deferredResponse(result);
    if (deferred) {
      ports.defer(deferred);
      return { status: "deferred", value: result };
    }
    if (
      command === "map_select" &&
      args.reintegrate === true &&
      !result.ok &&
      result.error ===
        "Reintegration needs the original image and a loaded calibration."
    )
      result = await context.retryStoredMap();
    const retainMapClick =
      result.ok &&
      ((!!result.map && (command === "map_select" || command === "map_poll")) ||
        result.batchSelection !== undefined);
    if (retainMapClick)
      result = await restoreMapPosition(
        invoke,
        result,
        context.selectedPosition,
      );
    const raw = context.detector.raw();
    if (context.detector.autoActive())
      result = await prepareDetectorImage(
        invoke,
        result,
        context.detector.previous(raw),
        context.detector.autoLevels(),
        raw,
      );
    ports.trace("command-prepared", result);
    const unitOnly =
      ["settings", "integration_settings"].includes(command) &&
      Object.keys(args).length === 1 &&
      "unit" in args;
    ports.apply(result, !unitOnly, retainMapClick);
    ports.trace("command-applied", result);
    complete(
      commandCompletion(
        command,
        args,
        result,
        context.historyLabel,
        context.pendingDrafts(),
      ),
      ports,
    );
    ports.success?.(result);
    return {
      status: result.cancelled ? "cancelled" : "applied",
      value: result,
    };
  } catch (error) {
    const details = error instanceof Error ? error.message : String(error);
    const failure = fileOperationFailure(command, details, args);
    ports.workflow.error(failure?.title ?? details);
    try {
      ports.apply(await invoke("state"), false);
    } catch {
      /* Preserve the original error and plot context. */
    }
    return { status: "failed", error };
  }
}
