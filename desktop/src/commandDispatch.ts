import type {
  CommandInvocation,
  CheckedInvocation,
  CheckedRunInvocation,
  CheckedRequest,
  CommandAction,
  CommandName,
  CommandPayload,
  CommandRequest,
  CommandResult,
  Invoke,
  Run,
  RunInvocation,
  TransportMetadata,
} from "./commandContracts";

/** Tuple reconstruction is kept here: adding common transport metadata cannot
 * change the command/payload pairing. No scientific values or buffers are copied. */
export function withTransportMetadata<A extends CommandInvocation>(
  call: CheckedInvocation<A>,
  metadata: TransportMetadata,
): CheckedInvocation<A> {
  return [call[0], { ...call[1], ...metadata }] as CheckedInvocation<A>;
}
export function invocationOf<C extends CommandName>(
  request: CommandRequest<C>,
): CommandInvocation<C> {
  return [request.command, request.payload] as CommandInvocation<C>;
}
/** Forwarding uses apply because TypeScript 7 loses the tuple relation when
 * spreading a generic exact-key intersection. Only checked correlated calls
 * enter these helpers; the assertion retains the same command's result type. */
export function forwardInvoke<A extends CommandInvocation>(
  invoke: Invoke,
  call: CheckedInvocation<A>,
): Promise<CommandResult<A[0]>> {
  return invoke.apply(undefined, call) as Promise<CommandResult<A[0]>>;
}
export function forwardRun<A extends RunInvocation>(
  run: Run,
  call: CheckedRunInvocation<A>,
): Promise<void> {
  return run.apply(undefined, call);
}
export function forwardAction<A extends CommandInvocation>(
  action: CommandAction,
  call: CheckedInvocation<A>,
): void {
  action.apply(undefined, call);
}
export function invokeCommand<R extends CommandRequest>(
  invoke: Invoke,
  request: CheckedRequest<R>,
): Promise<CommandResult<R["command"]>> {
  return forwardInvoke(invoke, [
    request.command,
    request.payload,
  ] as CommandInvocation) as Promise<CommandResult<R["command"]>>;
}
export function runCommand<R extends CommandRequest>(
  run: Run,
  request: CheckedRequest<R>,
  message?: string,
  onSuccess?: (response: CommandResult<R["command"]>) => void,
): Promise<void> {
  return forwardRun(run, [
    request.command,
    request.payload,
    message,
    onSuccess,
  ] as RunInvocation);
}
export type ActionInvocation<C extends CommandName = CommandName> = {
  [K in C]: {} extends CommandPayload<K>
    ? [
        command: K,
        payload?: CommandPayload<K>,
        onSuccess?: (response: CommandResult<K>) => void,
      ]
    : [
        command: K,
        payload: CommandPayload<K>,
        onSuccess?: (response: CommandResult<K>) => void,
      ];
}[C];
export interface RunAction<C extends CommandName = CommandName> {
  <K extends C>(
    command: import("./commandContracts").SingleCommand<K>,
    ...args: {} extends CommandPayload<NoInfer<K>>
      ? [
          payload?: CommandPayload<NoInfer<K>>,
          onSuccess?: (result: CommandResult<K>) => void,
        ]
      : [
          payload: CommandPayload<NoInfer<K>>,
          onSuccess?: (result: CommandResult<K>) => void,
        ]
  ): Promise<void>;
  <const A extends ActionInvocation<C>>(
    ...call: CheckedRunInvocation<A>
  ): Promise<void>;
}
export function fixedMessageAction(run: Run, message: string): RunAction {
  return <A extends ActionInvocation>(...call: CheckedRunInvocation<A>) =>
    forwardRun(run, [call[0], call[1], message, call[2]] as RunInvocation);
}

type OperationNames<P> = P extends { operation?: infer O extends string }
  ? O
  : never;
type OperationFields<P, O extends string> = P extends {
  operation?: infer Names;
}
  ? O extends Names
    ? Omit<P, "operation">
    : never
  : never;
export type OperationCall<P> = {
  [O in OperationNames<P>]: {} extends OperationFields<P, O>
    ? [operation: O, args?: OperationFields<P, O>]
    : [operation: O, args: OperationFields<P, O>];
}[OperationNames<P>];
/** Preserve operation-specific requirements when a control adds a fixed
 * operation discriminator to the payload it sends. */
export function operationPayload<P extends { operation?: string }>(
  call: OperationCall<P>,
): P;
export function operationPayload(
  call: readonly [operation: string, args?: object],
) {
  return Object.assign({ operation: call[0] }, call[1]);
}
