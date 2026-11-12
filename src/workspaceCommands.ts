import type {
  CommandInvocation,
  CheckedInvocation,
  CheckedRunInvocation,
  CommandName,
  Run,
  RunInvocation,
  Invoke,
} from "./commandContracts";
import type { Response } from "./types";
import { forwardInvoke, forwardRun } from "./commandDispatch.ts";

export type ScheduledRunInvocation<C extends CommandName = CommandName> = {
  [K in C]: [
    ...RunInvocation<K>,
    shouldRun?: () => boolean,
    queueIfBusy?: boolean,
    replaceDrafts?: boolean,
  ];
}[C];
export type ScheduledRun = <const A extends ScheduledRunInvocation>(
  ...call: CheckedRunInvocation<A>
) => Promise<void>;
export function forwardScheduledRun<A extends ScheduledRunInvocation>(
  run: ScheduledRun,
  call: CheckedRunInvocation<A>,
): Promise<void> {
  return run.apply(undefined, call);
}
export interface SchedulingOptions {
  shouldRun?: () => boolean;
  queueIfBusy?: boolean;
  replaceDrafts?: boolean;
}

/** Audited tuple boundary: removing scheduling/callback fields preserves the
 * correlated command/payload pair already checked by RunInvocation. */
export function commandInvocation(
  call: ScheduledRunInvocation | RunInvocation,
): CommandInvocation {
  return [call[0], call[1]] as CommandInvocation;
}
export function scheduledInvocation(
  call: ScheduledRunInvocation | RunInvocation,
  options: SchedulingOptions,
): ScheduledRunInvocation {
  return [
    call[0],
    call[1],
    call[2],
    call[3],
    options.shouldRun ?? call[4],
    options.queueIfBusy ?? call[5],
    options.replaceDrafts ?? call[6],
  ] as ScheduledRunInvocation;
}
/** Keep generic callback correlation at this single boundary. This transaction
 * can only publish a prepared response from the invocation paired with call. */
export function notifyScheduledSuccess(
  call: ScheduledRunInvocation,
  result: Response,
) {
  const notify = call[3] as ((result: Response) => void) | undefined;
  notify?.(result);
}
export function withScheduling(
  run: ScheduledRun,
  options: SchedulingOptions,
): Run {
  return <const A extends RunInvocation>(...call: CheckedRunInvocation<A>) =>
    forwardScheduledRun(run, scheduledInvocation(call, options));
}
export function submitWorkspaceCommand(
  invoke: Invoke,
  call: ScheduledRunInvocation,
  mode: string,
  canDefer: boolean,
): Promise<Response> {
  const invocation = commandInvocation(call);
  if (
    mode === "mask" &&
    canDefer &&
    ![
      "configuration",
      "configuration_select",
      "combination_settings",
      "configuration_navigation",
      "save_combined_pattern",
      "processing_workers",
    ].includes(invocation[0])
  ) {
    // defer_integration is shared transport metadata on every command payload.
    const deferred = [
      invocation[0],
      { ...invocation[1], defer_integration: true },
    ] as CommandInvocation;
    return forwardInvoke(invoke, deferred);
  }
  if (invocation[0] === "map_select")
    return invoke("map_select", {
      ...invocation[1],
      integration_view: mode === "integration",
    });
  return forwardInvoke(invoke, invocation);
}
export function retryStoredMap(
  invoke: Invoke,
  call: ScheduledRunInvocation,
  mode: string,
): Promise<Response> {
  const invocation = commandInvocation(call);
  if (invocation[0] !== "map_select")
    throw new Error("Stored-map retry requires map_select.");
  return invoke("map_select", {
    ...invocation[1],
    integration_view: mode === "integration",
    reintegrate: false,
  });
}
export function withCommandMessage(
  run: ScheduledRun,
  message: string,
  options: SchedulingOptions = {},
) {
  return <const A extends CommandInvocation>(...call: CheckedInvocation<A>) => {
    const scheduled = [
      call[0],
      call[1],
      message,
      undefined,
      options.shouldRun,
      options.queueIfBusy,
      options.replaceDrafts,
    ] as ScheduledRunInvocation;
    return forwardScheduledRun(run, scheduled);
  };
}
export function withCommandSuccess(
  run: ScheduledRun,
  completed: (command: CommandName) => void,
): Run {
  return <const A extends RunInvocation>(...call: CheckedRunInvocation<A>) => {
    const scheduled = [
      call[0],
      call[1],
      call[2],
      (result: Response) => {
        notifyScheduledSuccess(call, result);
        completed(call[0]);
      },
    ] as ScheduledRunInvocation;
    return forwardScheduledRun(run, scheduled);
  };
}
/** A queue may coalesce callers before invoking a command once. Capture its
 * correlated result without delivering any one caller's callback prematurely. */
export async function captureCommandResponse(
  run: Run,
  call: RunInvocation,
): Promise<Response | undefined> {
  let response: Response | undefined;
  const captured = [
    call[0],
    call[1],
    call[2],
    (result: Response) => {
      response = result;
    },
  ] as RunInvocation;
  await forwardRun(run, captured);
  return response;
}
