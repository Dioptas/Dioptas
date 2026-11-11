import type {
  CheckedInvocation,
  CommandInvocation,
  CommandPayload,
  CommandRequest,
  CommandResult,
  Invoke,
  Run,
} from "../../src/commandContracts";
import { forwardInvoke, invokeCommand } from "../../src/commandDispatch";
import type { ProfileRun } from "../../src/detectorProfileCommands";

declare const invoke: Invoke;
declare const run: Run;
declare const profileRun: ProfileRun;
invoke("state");
run("calibrate", { restart: true });
invoke("state", { requested_products: { cake: false, rings: true } });
invoke("pixel", { x: 1, y: 2, source: "geometry" });
invoke("pick_peak", { x: 1, y: 2, ring: 1, automatic: true });
run("integration_overlay", { operation: "move", uid: "a", direction: 1 });
run("integration_overlay", { operation: "update", uid: "a", scale: 2 });
run("integration_overlay", { operation: "update", index: 0, offset: 3 }); // explicit compatibility variant
run("mask_edit", {
  operation: "polygon",
  points: [
    [1, 2],
    [3, 4],
    [5, 6],
  ],
});
run("integration_phase", {
  operation: "update",
  editor_uid: "phase-a",
  pressure: 12,
});
run("integration_phase", {
  operation: "editor_transaction",
  editor_uid: "phase-a",
  edit_operation: "editor_parameter",
  parameter: "K0",
  value: 160,
});
run("configuration", { operation: "rename", name: "Detector B" });
run("integration_transfer", { source: "response", path: "response.tif" });

// @ts-expect-error Unknown scientific commands are never a string fallback.
invoke("unknown_scientific_command", {});
// @ts-expect-error Coordinates are numerical.
invoke("pixel", { x: "1", y: 2 });
// @ts-expect-error Peak requests require an explicit ring.
invoke("pick_peak", { x: 1, y: 2 });
// @ts-expect-error A required pixel payload cannot be omitted.
invoke("pixel");
// @ts-expect-error A worker count is not a pixel payload.
invoke("pixel", { workers: 2 });
// @ts-expect-error A move needs its direction.
run("integration_overlay", { operation: "move", uid: "a" });
// @ts-expect-error A remove needs its captured target.
run("integration_overlay", { operation: "remove" });
// @ts-expect-error An update must contain at least one edited field.
run("integration_overlay", { operation: "update", uid: "a" });
// @ts-expect-error Geometric mask drawing requires its vertices.
run("mask_edit", { operation: "polygon" });
// @ts-expect-error A targeted phase update must identify the phase.
run("integration_phase", { operation: "update", pressure: 12 });
// @ts-expect-error An editor transaction requires its edit operation.
run("integration_phase", {
  operation: "editor_transaction",
  editor_uid: "phase-a",
});
// @ts-expect-error Rename requires the resulting name.
run("configuration", { operation: "rename" });
// @ts-expect-error Native transfer sources are a closed domain.
run("integration_transfer", { source: "flat" });
// @ts-expect-error Plugin settings contain JSON scalar controls, not functions.
run("mask_plugin", { name: "Spot Mask", settings: { threshold: () => 10 } });

declare const dynamicName: "pixel" | "processing_workers";
// @ts-expect-error A union command cannot borrow an unrelated member's payload.
invoke(dynamicName, { x: 1, y: 2 });
const invalidRequest: CommandRequest = {
  command: "pixel",
  // @ts-expect-error The request-object API retains command/payload correlation.
  payload: { workers: 2 },
};
void invalidRequest;
const request = {
  command: "pixel",
  payload: { x: 1, y: 2 },
} satisfies CommandRequest;
invokeCommand(invoke, request).then((result) => {
  // @ts-expect-error Pixel reads cannot promise export paths.
  result.savedPath;
});
// @ts-expect-error The envelope forwarding helper must reject extras too.
invokeCommand(invoke, {
  command: "pixel",
  payload: { x: 1, y: 2, typo: true },
});

invoke("progress").then((result) => {
  // @ts-expect-error Progress results have no pixel field.
  result.pixel;
});
run("integration_phase_editor", { editor_uid: "a" }, "", (result) => {
  if (
    result.ok &&
    !result.cancelled &&
    !result.imageChange &&
    !result.calibrationChange &&
    !result.hdf5SourceRequest
  ) {
    result.phaseEditor.index;
    // @ts-expect-error Editor inspection is not a map display result.
    result.mapPreview;
  }
});
invoke("pixel", { x: 1, y: 2 }).then((result) => {
  if (result.ok) {
    // @ts-expect-error A cancellation or decision is not an applied pixel read.
    const pixel: NonNullable<CommandResult<"pixel">["pixel"]> = result.pixel;
    void pixel;
  }
  if (
    result.ok &&
    !result.cancelled &&
    !result.imageChange &&
    !result.calibrationChange &&
    !result.hdf5SourceRequest
  ) {
    const intensity: number | null = result.pixel.value;
    void intensity;
  }
});
profileRun(
  "save_cake_profile",
  { two_theta: 5, bins: 3, shift: 0 },
  "",
  (reply) => {
    // @ts-expect-error The detached profile callback returns an acknowledgement, not a saved path.
    reply.savedPath;
  },
);

// Generic wrappers preserve the original call and exact per-command result.
const wrapped: Invoke = <A extends CommandInvocation>(
  ...call: CheckedInvocation<A>
) => forwardInvoke<A>(invoke, call);
wrapped("pixel", { x: 1, y: 2 }).then((result) => {
  // @ts-expect-error Forwarding cannot widen a pixel response into any command result.
  result.batch;
});
// @ts-expect-error The checked tuple helper cannot be a route around payload validation.
forwardInvoke(invoke, ["pixel", { x: 1, y: 2, typo: true }]);
const payload: CommandPayload<"processing_workers"> = { workers: null };
void payload;
