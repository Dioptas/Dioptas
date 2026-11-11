import type {
  CheckedRunInvocation,
  CommandName,
  CommandPayload,
  SingleCommand,
} from "./commandContracts";

/** Batch and Map controls submit work and observe committed snapshots. Their
 * original API has no result callback; detached edits return only an ACK. */
export type RunnerInvocation<C extends CommandName = CommandName> = {
  [K in C]: {} extends CommandPayload<K>
    ? [command: K, payload?: CommandPayload<K>, message?: string]
    : [command: K, payload: CommandPayload<K>, message?: string];
}[C];
export interface CommandRunner<Result = void> {
  <C extends CommandName>(
    command: SingleCommand<C>,
    ...args: {} extends CommandPayload<NoInfer<C>>
      ? [payload?: CommandPayload<NoInfer<C>>, message?: string]
      : [payload: CommandPayload<NoInfer<C>>, message?: string]
  ): Promise<Result>;
  <const A extends RunnerInvocation>(
    ...call: CheckedRunInvocation<A>
  ): Promise<Result>;
}

/** Preserve checked command tuples when TypeScript loses intersection tuple
 * information through a generic spread. No payload values are changed. */
export function forwardRunner<A extends RunnerInvocation, Result>(
  run: CommandRunner<Result>,
  call: CheckedRunInvocation<A>,
): Promise<Result> {
  return run.apply(undefined, call);
}
