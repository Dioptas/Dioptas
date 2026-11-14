import { useEffect, useSyncExternalStore } from "react";
import { StatusMessage } from "./StatusMessage";
import { Button } from "./ui";
import {
  subscribeBackendStatus,
  backendStatus,
  dismissBackendGuidance,
} from "./backendUpdateStatus";

/** Update guidance must not gate processing or product requests through the
 * application's scientific error state. It uses the existing footer details. */
export function BackendStatusMessage({
  error,
  message,
  crystalFrames,
  processing,
}: {
  error: string | null;
  message: string;
  crystalFrames: number;
  processing: boolean;
}) {
  const {
    guidance,
    updating,
    message: updateMessage,
  } = useSyncExternalStore(subscribeBackendStatus, backendStatus);
  useEffect(() => {
    if (crystalFrames && guidance?.kind === "lost-scan")
      dismissBackendGuidance();
  }, [crystalFrames, guidance?.kind]);
  return (
    <>
      <StatusMessage
        error={
          error ?? (!updating && !processing ? guidance?.message : null) ?? null
        }
        message={updating && !processing ? updateMessage : message}
      />
      {!error && guidance && !updating && !processing && (
        <Button
          variant="secondary"
          className="status-action"
          aria-label={
            guidance.kind === "lost-scan"
              ? "Dismiss scan recovery message"
              : "Dismiss update message"
          }
          onClick={dismissBackendGuidance}
        >
          ×
        </Button>
      )}
    </>
  );
}
