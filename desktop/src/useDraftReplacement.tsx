import { useCallback, useRef, useState } from "react";
import { ConfirmDraftReplacement } from "./ConfirmDraftReplacement";

/** One replacement policy for all commands that intentionally open new settings. */
export function useDraftReplacement({
  geometry,
  fit,
  integration,
}: {
  geometry: boolean;
  fit: boolean;
  integration: boolean;
}) {
  const current = useRef({ geometry, fit, integration });
  current.current = { geometry, fit, integration };
  const [pending, setPending] = useState<{
    action: string;
    drafts: string[];
    proceed: () => void;
  } | null>(null);
  const request = useCallback((command: string, proceed: () => void) => {
    if (!["open_calibration", "open_project", "example"].includes(command))
      return false;
    const state = current.current;
    const drafts = [
      ...(state.geometry ? ["manual geometry"] : []),
      ...(state.fit ? ["fit starting values"] : []),
      ...(state.integration && command !== "open_calibration"
        ? ["integration options"]
        : []),
    ];
    if (!drafts.length) return false;
    setPending({
      action:
        command === "open_project"
          ? "Open project"
          : command === "example"
            ? "Load example"
            : "Load calibration",
      drafts,
      proceed,
    });
    return true;
  }, []);
  return {
    request,
    dialog: pending ? (
      <ConfirmDraftReplacement
        action={pending.action}
        drafts={pending.drafts}
        onCancel={() => setPending(null)}
        onContinue={() => {
          setPending(null);
          pending.proceed();
        }}
      />
    ) : null,
  };
}
