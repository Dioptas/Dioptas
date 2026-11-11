import { useCallback, useEffect, useRef, useState } from "react";
import { emit, listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { connect } from "./bridge";
import { PhaseEditor } from "./PhaseEditor";
import type { EditorData } from "./phaseEditorTypes";
import type {
  PhaseEditorRun,
  PhaseEditorRunInvocation,
} from "./phaseEditorTypes";
import { phaseEditorInvocation } from "./phaseEditorCommands";
import { notifyScheduledSuccess } from "./workspaceCommands";
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
  const draftDirty = useRef(false);
  const refreshQueued = useRef<{ revision?: number } | null>(null);
  const appliedRevision = useRef(-1);
  const closeQueued = useRef(false);
  const refresh = useCallback(async (revision?: number) => {
    if (!bridge.current) return;
    if (revision != null && revision <= appliedRevision.current) return;
    if (pending.current || draftDirty.current) {
      const previous = refreshQueued.current;
      refreshQueued.current =
        previous == null
          ? { revision }
          : previous.revision != null && revision != null
            ? { revision: Math.max(previous.revision, revision) }
            : {};
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
        appliedRevision.current =
          result.phaseRevision ?? appliedRevision.current;
        setData(result.phaseEditor as EditorData);
        setError("");
      }
    } catch (e) {
      if (current === generation.current) {
        if (!draftDirty.current) setData(null);
        setError(String(e));
      }
    }
  }, []);
  useEffect(() => {
    let disposed = false;
    const closing = getCurrentWindow().onCloseRequested((event) => {
      if (draftDirty.current) {
        event.preventDefault();
        setError(
          "Apply or cancel publication edits before closing the editor.",
        );
      } else if (pending.current) {
        event.preventDefault();
        closeQueued.current = true;
      }
    });
    const subscriptions = [
      listen<{ uid: string }>("phase-editor-target", (e) => {
        if (draftDirty.current) {
          if (e.payload.uid !== uid.current)
            setError(
              "Apply or cancel publication edits before opening a different phase. Then select that phase again.",
            );
          return;
        }
        uid.current = e.payload.uid;
        appliedRevision.current = -1;
        ++generation.current;
        setData(null);
        void refresh();
      }),
      listen<{ revision?: number }>(
        "phase-editor-refresh",
        (event) => void refresh(event.payload?.revision),
      ),
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
  const run = useCallback<PhaseEditorRun>(
    async <const A extends PhaseEditorRunInvocation>(...call: A) => {
      const [command, args] = call;
      if (!bridge.current) return;
      const target =
        args && "editor_uid" in args && typeof args.editor_uid === "string"
          ? args.editor_uid
          : uid.current;
      const current =
        target === uid.current ? ++generation.current : generation.current;
      pending.current = true;
      setReady(false);
      setError("");
      try {
        const result = await bridge.current(
          ...phaseEditorInvocation(call, target),
        );
        if (!result.ok) throw Error(result.error);
        if (current === generation.current && target === uid.current) {
          appliedRevision.current =
            result.phaseRevision ?? appliedRevision.current;
          if (result.phaseEditor)
            uid.current = (result.phaseEditor as EditorData).uid;
          notifyScheduledSuccess(call, result);
        }
        if (command !== "integration_phase_editor" && !result.cancelled)
          await emit("phase-editor-changed", {
            revision: result.phaseRevision,
          });
      } catch (e) {
        setError(String(e));
      } finally {
        pending.current = false;
        setReady(true);
        if (closeQueued.current) void getCurrentWindow().close();
        else if (refreshQueued.current) {
          const queued = refreshQueued.current;
          refreshQueued.current = null;
          void refresh(queued.revision);
        }
      }
    },
    [refresh],
  );
  const setDraftDirty = useCallback(
    (dirty: boolean) => {
      draftDirty.current = dirty;
      if (!dirty && refreshQueued.current && !pending.current) {
        const queued = refreshQueued.current;
        refreshQueued.current = null;
        void refresh(queued.revision);
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
          onDraftDirty={setDraftDirty}
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
