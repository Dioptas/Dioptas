import { useEffect } from "react";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import type { IntegrationRun } from "./integration";

export const openNativePhaseEditor = (uid: string) =>
  invoke("open_phase_editor", { uid });

/** Refresh the main plots after a child edit, and refresh the child after main edits. */
export function useNativePhaseEditorSync(
  run: IntegrationRun,
  revision?: number,
) {
  useEffect(() => {
    if (!isTauri()) return;
    let disposed = false,
      queued = false,
      pending = false;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      if (disposed || pending || !queued) return;
      pending = true;
      queued = false;
      let received = false;
      await run(
        "integration_phase_state",
        {},
        "Updating phase preview…",
        () => {
          received = true;
        },
      );
      pending = false;
      if (!received) queued = true;
      if (queued && !disposed) timer = setTimeout(() => void refresh(), 100);
    };
    const subscription = listen("phase-editor-changed", () => {
      queued = true;
      void refresh();
    });
    const smoke = listen("phase-editor-smoke", (e) =>
      window.dispatchEvent(
        new CustomEvent("phase-editor-smoke", { detail: e.payload }),
      ),
    );
    return () => {
      disposed = true;
      clearTimeout(timer);
      void subscription.then((stop) => stop());
      void smoke.then((stop) => stop());
    };
  }, [run]);
  useEffect(() => {
    if (isTauri()) void emit("phase-editor-refresh", { revision });
  }, [revision]);
}
