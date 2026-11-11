import type { Invoke, Response } from "./types";

export type OperationFailure = {
  title: string;
  details: string;
  report?: string;
};
export const failureEvent = "dioptas-operation-failure";
const recent: { time: string; action: string; args: string; status: string }[] =
  [];
let context = "No workspace state available.";
let backend = "Not connected";
let sequence = 0;
const quiet = new Set([
  "progress",
  "pixel",
  "state",
  "image_levels",
  "map_levels",
  "batch_levels",
  "map_display",
  "map_snapshot",
  "batch_snapshot",
  "integration_phase_state",
  "integration_correction_preload",
  "integration_phase_guides",
  "validation_position",
  "integration_autoprocess_poll",
  "map_poll",
]);

function bounded(value: unknown, depth = 0): unknown {
  if (typeof value === "string")
    return value.length > 1000 ? value.slice(0, 1000) + "…" : value;
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer)
    return "[binary data omitted]";
  if (depth > 3) return "[…]";
  if (Array.isArray(value))
    return [
      ...value.slice(0, 8).map((v) => bounded(v, depth + 1)),
      ...(value.length > 8 ? [`… ${value.length - 8} more`] : []),
    ];
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 30)
        .map(([k, v]) => [k, bounded(v, depth + 1)]),
    );
  return value;
}
export function recordAction(action: string, args: unknown = {}) {
  const entry = {
    time: new Date().toISOString(),
    action,
    args: JSON.stringify(bounded(args)).slice(0, 3000),
    status: "started",
  };
  recent.push(entry);
  if (recent.length > 200) recent.shift();
  return entry;
}
function describe(error: unknown): string {
  return error instanceof Error
    ? `${error.name}: ${error.message}\n${error.stack ?? ""}`
    : String(error);
}
export function createErrorReport(
  action: string,
  error: unknown,
  extra?: unknown,
): string {
  return [
    "Dioptas desktop error report",
    `Build: ${import.meta.env?.VITE_DIOPTAS_BUILD ?? "development"}`,
    `Time: ${new Date().toISOString()}`,
    `Backend: ${backend}`,
    `Window: ${typeof location === "undefined" ? "test" : location.search || "main"}`,
    `Platform: ${typeof navigator === "undefined" ? "test" : navigator.userAgent}`,
    `Operation: ${action}`,
    "",
    "Error / available diagnostic stack:",
    describe(error).slice(0, 32000),
    ...(extra
      ? ["", "Backend context:", JSON.stringify(extra).slice(0, 40000)]
      : []),
    "",
    "Workspace at failure:",
    context,
    "",
    "Recent steps (oldest first):",
    ...recent
      .slice(-50)
      .map((e) => `${e.time} ${e.action} ${e.args} [${e.status}]`),
    "",
    "This report is local. Copy it into your bug report; it is not sent automatically.",
  ].join("\n");
}
export function fileOperationFailure(
  command: string,
  details: string,
  args: Record<string, unknown> = {},
): OperationFailure | null {
  const titles: Record<string, string> = {
    open_calibration: "Couldn’t load calibration",
    detector_file: "Couldn’t load detector",
    distortion_file: "Couldn’t load distortion correction",
    open_image: "Couldn’t load image",
    select_image_source: "Couldn’t load image source",
    open_project: "Couldn’t load project",
    load_peaks: "Couldn’t load peaks",
    open_calibrant: "Couldn’t load calibrant",
    mask_file: args.save ? "Couldn’t save mask" : "Couldn’t load mask",
  };
  return titles[command] ? { title: titles[command], details } : null;
}
export function reportFailure(
  action: string,
  error: unknown,
  args: Record<string, unknown> = {},
  extra?: unknown,
) {
  if (pendingFailure && quiet.has(action)) return;
  const details = error instanceof Error ? error.message : String(error);
  const short = details.includes("Open the matching detector image first.");
  const failure: OperationFailure = {
    ...(fileOperationFailure(action, details, args) ?? {
      title: "An error occurred",
      details,
    }),
    ...(!short && { report: createErrorReport(action, error, extra) }),
  };
  pendingFailure = { ...failure, id: ++sequence };
  window.dispatchEvent(
    new CustomEvent(failureEvent, { detail: pendingFailure }),
  );
}
export function withErrorReporting(invoke: Invoke): Invoke {
  return async (action, args = {}) => {
    const entry =
      !quiet.has(action) &&
      !(action === "custom_command" && args.operation === "list")
        ? recordAction(action, args)
        : undefined;
    let response: Response;
    try {
      response = await invoke(action, args);
    } catch (error) {
      if (entry) entry.status = "failed";
      reportFailure(action, error, args);
      throw error;
    }
    // Older live workers and the explicit Python compatibility backend still
    // return this expected search outcome as an error.
    if (
      action === "pick_peak" &&
      !response.ok &&
      response.error ===
        "No peak found here. Click on a bright ring, or try single-peak mode."
    )
      response = { ok: true, noPeakFound: true };
    if (entry)
      entry.status = response.cancelled
        ? "cancelled"
        : response.ok
          ? "completed"
          : "failed";
    const activity = (response as Response & { activity?: unknown }).activity;
    if (entry && activity)
      entry.args = JSON.stringify(
        bounded({ ...args, selectedFiles: activity }),
      ).slice(0, 3000);
    if (!response.ok) {
      if (!entry) recordAction(action, args).status = "failed";
      reportFailure(
        action,
        response.error ?? "The operation failed.",
        args,
        (response as Response & { errorContext?: unknown }).errorContext,
      );
    }
    if (response.state) {
      const s = response.state;
      backend = `${s.calibration.engineLabel} (${s.calibration.engine})`;
      context = JSON.stringify({
        image: s.imagePath,
        shape: s.shape,
        project: s.projectName,
        calibration: s.calibrationName,
        detector: s.calibration.detector,
        transformations: s.calibration.transformations,
        configuration: s.configurationIndex,
        configurations: s.configurationLabels,
        unit: s.unit,
        bins: s.bins,
        useMask: s.useMask,
        geometry: s.geometry,
      });
    }
    return response;
  };
}

let pendingFailure: (OperationFailure & { id: number }) | null = null;
export function currentFailure() {
  return pendingFailure;
}
export function dismissFailure() {
  pendingFailure = null;
}
