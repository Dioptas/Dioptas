import {
  useEffect,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import {
  canTraverseScientificHistory,
  scientificHistoryAction,
  scientificHistoryCommand,
} from "./historyLabels";
import type { useMaskTools } from "./maskDomain";
import type { createPlotViews } from "./plotViewport";
import type { State } from "./types";
import type { ScheduledRun } from "./workspaceCommands";

export type WorkspaceMode =
  "calibration" | "integration" | "map" | "mask" | "scxrd";

export interface WorkspaceShortcutOptions {
  run: ScheduledRun;
  currentState: RefObject<State | null>;
  canPick: boolean;
  mode: WorkspaceMode;
  setMode: Dispatch<SetStateAction<WorkspaceMode>>;
  onPickShortcut?: () => void;
  setPickingEnabled: (enabled: boolean) => void;
  selectedPicks: number[];
  setSelectedPicks: (picks: number[]) => void;
  maskTools: ReturnType<typeof useMaskTools>;
  plotViews: ReturnType<typeof createPlotViews>;
  mapPlotViews: ReturnType<typeof createPlotViews>;
  setResetKey: Dispatch<SetStateAction<number>>;
  setMapResetKey: Dispatch<SetStateAction<number>>;
  settingsOpen: boolean;
  changeConfigurationControls: (visible: boolean) => void;
  showConfigurationControls: boolean;
  scxrdDraftDirty: boolean;
  setNotice: (message: string) => void;
  imageFileStep: number;
}

export function useWorkspaceShortcuts({
  run,
  currentState,
  canPick,
  mode,
  setMode,
  onPickShortcut,
  setPickingEnabled,
  selectedPicks,
  setSelectedPicks,
  maskTools,
  plotViews,
  mapPlotViews,
  setResetKey,
  setMapResetKey,
  settingsOpen,
  changeConfigurationControls,
  showConfigurationControls,
  scxrdDraftDirty,
  setNotice,
  imageFileStep,
}: WorkspaceShortcutOptions) {
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      const target =
        event.target instanceof Element ? event.target : document.body;
      if (settingsOpen) return;
      if (
        target.closest(
          '[role="dialog"], dialog, [role="listbox"], [role="menu"]',
        ) ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      )
        return;
      // Native controls own their unmodified activation keys.
      if (target.closest('[contenteditable="true"]')) return;
      if (
        !(event.metaKey || event.ctrlKey) &&
        ["Enter", " "].includes(event.key) &&
        target.closest('button, a, summary, [role="tab"]')
      )
        return;
      if (event.defaultPrevented) return;
      const key = event.key.toLowerCase(),
        mod = event.metaKey || event.ctrlKey;
      if (mode === "scxrd" && mod && ["s", "o", "z", "y"].includes(key)) {
        event.preventDefault();
        if (key === "s" || key === "o")
          void run(
            "scxrd_file",
            { operation: key === "s" ? "save" : "open" },
            key === "s"
              ? "Saving single-crystal recipe…"
              : "Opening single-crystal recipe…",
          );
        else if (!scxrdDraftDirty)
          void run(
            "scxrd_edit",
            { operation: key === "y" || event.shiftKey ? "redo" : "undo" },
            "Restoring single-crystal decision…",
          );
        else
          setNotice(
            "Apply or reset the single-crystal settings draft before Undo/Redo.",
          );
        return;
      }
      if (!mod && !event.altKey && event.shiftKey && key === "c") {
        event.preventDefault();
        if (!event.repeat)
          changeConfigurationControls(!showConfigurationControls);
      } else if (
        !mod &&
        !event.altKey &&
        !event.shiftKey &&
        ["PageUp", "PageDown"].includes(event.key) &&
        (mode === "integration" || mode === "calibration") &&
        currentState.current?.hasImage
      ) {
        event.preventDefault();
        void run(
          "next_image",
          {
            direction: event.key === "PageUp" ? -1 : 1,
            step: mode === "integration" ? imageFileStep : 1,
            files_only: true,
          },
          "Opening image…",
        );
      } else if (mod && key === "o") {
        event.preventDefault();
        void run(
          "open_image",
          mode === "integration"
            ? {
                multiple: true,
                batch_mode:
                  currentState.current?.integration.imageBatchMode ??
                  "integrate",
              }
            : {},
          "Opening image…",
        );
      } else if (mod && key === "s") {
        event.preventDefault();
        if (mode === "mask") void run("mask_file", { save: true }, "Saving…");
        else void run("save_project", {}, "Saving…");
      } else if (mod && key === "z") {
        event.preventDefault();
        if (
          !canTraverseScientificHistory(
            currentState.current,
            event.shiftKey,
            mode,
          )
        )
          return;
        void run(
          scientificHistoryCommand(
            scientificHistoryAction(currentState.current, mode, event.shiftKey),
            event.shiftKey,
          ),
          {},
          "Restoring previous state…",
        );
      } else if (mod && key === "y") {
        event.preventDefault();
        if (!canTraverseScientificHistory(currentState.current, true, mode))
          return;
        void run(
          scientificHistoryCommand(
            scientificHistoryAction(currentState.current, mode, true),
            true,
          ),
          {},
          "Restoring previous state…",
        );
      } else if (mode === "mask") {
        if (mod) return;
        if (key === "b") {
          maskTools.setShape("point");
          maskTools.setErase(false);
        }
        if (key === "e") {
          maskTools.setShape("point");
          maskTools.setErase(true);
        }
        if (key === "v") maskTools.setShape("navigate");
        if (key === "f") {
          plotViews.detector.current = null;
          setResetKey((k) => k + 1);
        }
        return;
      } else if (mod) return;
      else if (key === "b" || key === "e") {
        setMode("mask");
        maskTools.setShape("point");
        maskTools.setErase(key === "e");
      } else if (key === "p" && canPick) {
        if (onPickShortcut) {
          onPickShortcut();
        } else {
          setMode("calibration");
          setPickingEnabled(true);
        }
      } else if (key === "f") {
        if (mode === "map") {
          mapPlotViews.detector.current = null;
          setMapResetKey((k) => k + 1);
        } else {
          plotViews.detector.current = null;
          setResetKey((k) => k + 1);
        }
      } else if (
        (event.key === "Delete" || event.key === "Backspace") &&
        mode === "calibration" &&
        selectedPicks.length
      ) {
        event.preventDefault();
        void run("remove_picks", { indices: selectedPicks });
        setSelectedPicks([]);
      } else if (
        (mode === "integration" || mode === "calibration") &&
        event.key === "Enter" &&
        currentState.current?.hasImage &&
        currentState.current.calibrated
      )
        void run("integrate", {}, "Integrating image and cake…");
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [
    run,
    canPick,
    mode,
    onPickShortcut,
    selectedPicks,
    maskTools,
    settingsOpen,
    changeConfigurationControls,
    showConfigurationControls,
    scxrdDraftDirty,
    imageFileStep,
  ]);
}
