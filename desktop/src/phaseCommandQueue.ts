import type { IntegrationRun } from "./integration";
import type { Response } from "./types";

type Waiter = {
  done: () => void;
  fail: (error: unknown) => void;
  onSuccess?: (response: Response) => void;
};
type Entry = {
  command: string;
  args: Record<string, unknown>;
  message?: string;
  key: string | null;
  waiters: Waiter[];
};

function conditionKey(command: string, args: Record<string, unknown>) {
  if (command !== "integration_phase" || args.operation !== "update")
    return null;
  const fields = Object.keys(args).filter(
    (key) => !["operation", "index", "editor_uid"].includes(key),
  );
  if (fields.length !== 1 || !["pressure", "temperature"].includes(fields[0]))
    return null;
  return `${args.editor_uid ?? args.index}:${fields[0]}`;
}

/** Collapse consecutive queued P/T values, preserving every discrete action's order. */
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
          let response: Response | undefined;
          await currentRun()(
            next.command,
            next.args,
            next.message,
            (result) => {
              response = result;
            },
          );
          for (const waiter of next.waiters) {
            try {
              if (response) waiter.onSuccess?.(response);
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
  return (command, args = {}, message, onSuccess) =>
    new Promise<void>((done, fail) => {
      const key = conditionKey(command, args);
      const tail = pending.at(-1);
      const waiter = { done, fail, onSuccess };
      if (key != null && tail?.key === key) {
        tail.args = args;
        tail.message = message;
        tail.waiters.push(waiter);
      } else pending.push({ command, args, message, key, waiters: [waiter] });
      void drain();
    });
}
