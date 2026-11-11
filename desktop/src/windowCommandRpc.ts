import type {
  CommandInvocation,
  CommandName,
  CommandPayload,
  CommandRequestReader,
  CommandResult,
  Invoke,
  Run,
  RunInvocation,
} from "./commandContracts";
import type { Response } from "./types";

export type ScientificWindowRequest = {
  [C in CommandName]: {
    type: "request";
    id: string;
    command: C;
    args: CommandPayload<C>;
    read: boolean;
  };
}[CommandName];
export type WindowCommandRequest =
  | ScientificWindowRequest
  | {
      type: "request";
      id: string;
      command: "batch_hide";
      args: Record<string, never>;
      read: false;
    };
type WindowInvocation =
  CommandInvocation | [command: "batch_hide", payload?: Record<string, never>];
export type WindowRunInvocation =
  | RunInvocation
  | [command: "batch_hide", payload?: Record<string, never>, message?: string];
export type WindowRun = <const A extends WindowRunInvocation>(
  ...call: A
) => Promise<void>;
export type WindowCommandAcknowledgement = Pick<
  Response,
  "ok" | "error" | "cancelled"
>;

/** A detached edit returns only an acknowledgement. Its updated scientific data
 * arrives through the existing refresh/snapshot path, never through this reply. */
export class WindowCommandRpc {
  private readonly send: (request: WindowCommandRequest) => void;
  private readonly timeoutMs: number;
  private readonly pending = new Map<
    string,
    {
      resolve(result: Response): void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();
  constructor(
    send: (request: WindowCommandRequest) => void,
    timeoutMs = 120000,
  ) {
    this.send = send;
    this.timeoutMs = timeoutMs;
  }

  private call(
    read: boolean,
    command: WindowInvocation[0],
    args: object = {},
  ): Promise<Response> {
    return new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      const timer = setTimeout(() => {
        this.pending.delete(id);
        resolve({ ok: false, error: "The main window did not respond." });
      }, this.timeoutMs);
      this.pending.set(id, { resolve, timer });
      // The public read/edit signatures preserve the command/payload relation.
      // Reassemble its wire envelope here, where TypeScript loses that relation.
      try {
        this.send({
          type: "request",
          id,
          command,
          args,
          read,
        } as WindowCommandRequest);
      } catch (error) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(error);
      }
    });
  }
  readonly read: Invoke = async <const A extends CommandInvocation>(
    ...call: A
  ) => {
    // The response is correlated with this command by its private request id.
    // Keep this transport assertion here rather than in detached UI components.
    return (await this.call(true, call[0], call[1])) as CommandResult<A[0]>;
  };
  readonly edit = <const A extends WindowRunInvocation>(
    ...call: A
  ): Promise<WindowCommandAcknowledgement> =>
    this.call(false, call[0], call[1]);

  receive(id: string, result: Response) {
    const task = this.pending.get(id);
    if (!task) return;
    clearTimeout(task.timer);
    this.pending.delete(id);
    task.resolve(result);
  }
  close() {
    for (const task of this.pending.values()) {
      clearTimeout(task.timer);
      task.resolve({ ok: false, cancelled: true });
    }
    this.pending.clear();
  }
}

/** These adapters unpack the correlated envelope at the window IPC boundary.
 * Main-window admission and execution continue through their existing owners. */
export function readWindowCommand(
  request: ScientificWindowRequest,
  reader: CommandRequestReader,
) {
  return reader(...([request.command, request.args] as CommandInvocation));
}
export function runWindowCommand(
  request: ScientificWindowRequest,
  run: Run,
  message: string,
  onSuccess: (result: Response) => void,
) {
  return run(
    ...([request.command, request.args, message, onSuccess] as RunInvocation),
  );
}
