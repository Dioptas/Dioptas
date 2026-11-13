import type { IntegrationRun } from "./integration";
import type { RunInvocation } from "./commandContracts";
import type { Response } from "./types";
import {
  captureCommandResponse,
  notifyScheduledSuccess,
} from "./workspaceCommands.ts";

type Waiter = {
  done: () => void;
  fail: (error: unknown) => void;
  deliver: (response: Response) => void;
};
type Entry = { call: RunInvocation; key: string | null; waiters: Waiter[] };

function conditionKey(call: RunInvocation) {
  if (call[0] !== "integration_phase" || call[1].operation !== "update")
    return null;
  const args = call[1];
  const fields = Object.keys(args).filter(
    (key) => !["operation", "index", "editor_uid"].includes(key),
  );
  if (fields.length !== 1 || !["pressure", "temperature"].includes(fields[0]))
    return null;
  return `${args.editor_uid ?? args.index}:${fields[0]}`;
}

/** Collapse consecutive queued P/T values, preserving discrete action order and
 * each caller's typed callback. The stored tuple keeps command/payload correlated. */
export function createPhaseCommandQueue(
  currentRun: () => IntegrationRun,
): IntegrationRun {
  const pending: Entry[] = [];
  let running = false;
  const drain = async () => {
    if (running) return;
    running = true;
    try {
      while (pending.length) {
        const next = pending.shift()!;
        try {
          const response = await captureCommandResponse(
            currentRun(),
            next.call,
          );
          for (const waiter of next.waiters) {
            try {
              if (response) waiter.deliver(response);
              waiter.done();
            } catch (error) {
              waiter.fail(error);
            }
          }
        } catch (error) {
          for (const waiter of next.waiters) waiter.fail(error);
        }
      }
    } finally {
      running = false;
    }
  };
  return <const A extends RunInvocation>(...call: A) =>
    new Promise<void>((done, fail) => {
      const key = conditionKey(call),
        tail = pending.at(-1);
      const waiter = {
        done,
        fail,
        deliver: (response: Response) => notifyScheduledSuccess(call, response),
      };
      if (key != null && tail?.key === key) {
        tail.call = call;
        tail.waiters.push(waiter);
      } else pending.push({ call, key, waiters: [waiter] });
      void drain();
    });
}
