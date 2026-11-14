export type BackendGuidance = { message: string; kind: "update" | "lost-scan" };
export function backendUpdateMessage(message: string) {
  return message.replace(
    /^Backend update failed; current session retained\.\s*/,
    "",
  );
}
type UpdateStatus = {
  guidance: BackendGuidance | null;
  updating: boolean;
  message: string;
};
let status: UpdateStatus = { guidance: null, updating: false, message: "" };
let generation = 0;
const listeners = new Set<() => void>();
function publish(next: UpdateStatus) {
  status = next;
  for (const listener of listeners) listener();
}
export function subscribeBackendStatus(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function backendStatus() {
  return status;
}
export function beginBackendUpdate(
  message: string,
  restored: boolean,
  failed: boolean,
) {
  ++generation;
  publish({
    message,
    updating: !restored && !failed,
    guidance:
      status.guidance?.kind === "lost-scan"
        ? status.guidance
        : failed
          ? { kind: "update", message: backendUpdateMessage(message) }
          : null,
  });
  return generation;
}
export function isCurrentBackendUpdate(token: number) {
  return generation === token;
}
export function publishBackendGuidance(guidance: BackendGuidance) {
  if (status.guidance?.kind !== "lost-scan" || guidance.kind === "lost-scan")
    publish({ ...status, guidance });
}
export function dismissBackendGuidance() {
  publish({ ...status, guidance: null });
}
