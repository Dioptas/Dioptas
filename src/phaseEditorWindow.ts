import { useEffect, useRef } from "react";
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
  const childRevisions = useRef(new Set<number>());
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
      await run("integration_phase_state", {}, "", () => {
        received = true;
      });
      pending = false;
      if (!received) queued = true;
      if (queued && !disposed) timer = setTimeout(() => void refresh(), 100);
    };
    const subscription = listen<{ revision?: number }>(
      "phase-editor-changed",
      (event) => {
        if (event.payload?.revision != null)
          childRevisions.current.add(event.payload.revision);
        queued = true;
        void refresh();
      },
    );
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
    if (revision != null) {
      const isOwn = childRevisions.current.has(revision);
      for (const ownRevision of childRevisions.current)
        if (ownRevision <= revision) childRevisions.current.delete(ownRevision);
      if (isOwn) return;
    }
    if (isTauri()) void emit("phase-editor-refresh", { revision });
  }, [revision]);
}
