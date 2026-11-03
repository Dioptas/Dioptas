import { useCallback, useEffect, useRef, useState } from "react";
import { emit, listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { connect } from "./bridge";
import { PhaseEditor } from "./PhaseEditor";
import type { EditorData } from "./phaseEditorTypes";
import type { IntegrationRun } from "./integration";
import type { Invoke } from "./types";

export function NativePhaseEditor() {
  const [data, setData] = useState<EditorData | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [largeText, setLargeText] = useState(
    localStorage.getItem("dioptas-large-text") === "true",
  );
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key === "dioptas-large-text")
        setLargeText(event.newValue === "true");
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, []);
  const bridge = useRef<Invoke | null>(null);
  const uid = useRef(
    new URLSearchParams(location.search).get("phase_uid") || "",
  );
  const generation = useRef(0);
  const pending = useRef(false);
  const refreshQueued = useRef(false);
  const closeQueued = useRef(false);
  const refresh = useCallback(async () => {
    if (!bridge.current) return;
    if (pending.current) {
      refreshQueued.current = true;
      return;
    }
    const current = ++generation.current;
    try {
      const result = await bridge.current("integration_phase_editor", {
        editor_uid: uid.current,
      });
      if (current !== generation.current) return;
      if (!result.ok) throw Error(result.error);
      if (result.phaseEditor) {
        setData(result.phaseEditor as EditorData);
        setError("");
      }
    } catch (e) {
      if (current === generation.current) {
        setData(null);
        setError(String(e));
      }
    }
  }, []);
  useEffect(() => {
    let disposed = false;
    const closing = getCurrentWindow().onCloseRequested((event) => {
      if (pending.current) {
        event.preventDefault();
        closeQueued.current = true;
      }
    });
    const subscriptions = [
      listen<{ uid: string }>("phase-editor-target", (e) => {
        uid.current = e.payload.uid;
        ++generation.current;
        setData(null);
        void refresh();
      }),
      listen("phase-editor-refresh", () => void refresh()),
    ];
    void connect().then((invoke) => {
      if (!disposed) {
        bridge.current = invoke;
        setReady(true);
        void refresh();
      }
    });
    return () => {
      disposed = true;
      ++generation.current;
      void closing.then((stop) => stop());
      for (const p of subscriptions) void p.then((stop) => stop());
    };
  }, [refresh]);
  const run = useCallback<IntegrationRun>(
    async (command, args = {}, _message, onSuccess) => {
      if (!bridge.current) return;
      const target =
        typeof args.editor_uid === "string" ? args.editor_uid : uid.current;
      const current =
        target === uid.current ? ++generation.current : generation.current;
      pending.current = true;
      setReady(false);
      setError("");
      try {
        const result = await bridge.current(command, {
          ...args,
          editor_uid: target,
          editor_only: true,
        });
        if (!result.ok) throw Error(result.error);
        if (current === generation.current && target === uid.current) {
          if (result.phaseEditor)
            uid.current = (result.phaseEditor as EditorData).uid;
          onSuccess?.(result);
        }
        if (command !== "integration_phase_editor" && !result.cancelled)
          await emit("phase-editor-changed");
      } catch (e) {
        setError(String(e));
      } finally {
        pending.current = false;
        setReady(true);
        if (closeQueued.current) void getCurrentWindow().close();
        else if (refreshQueued.current) {
          refreshQueued.current = false;
          void refresh();
        }
      }
    },
    [refresh],
  );
  useEffect(() => {
    if (data) void getCurrentWindow().setTitle(`${data.name} — Phase Editor`);
  }, [data?.name]);
  return (
    <div
      className="app pe-native-app"
      data-text-size={largeText ? "large" : "normal"}
    >
      {error && (
        <div className="pe-native-error" role="alert">
          {error}
        </div>
      )}
      {data ? (
        <PhaseEditor
          data={data}
          ready={ready}
          run={run}
          onData={(next) => setData(next as EditorData)}
          onClose={() => void getCurrentWindow().close()}
          detached
        />
      ) : (
        <p className="pe-help">
          {error
            ? "Select a phase in the main window to open its editor."
            : "Opening phase…"}
        </p>
      )}
    </div>
  );
}
