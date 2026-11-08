import { Undo2, Redo2 } from "lucide-react";
import {
  canTraverseScientificHistory,
  historyActionLabel,
  scientificHistoryCommand,
} from "./historyLabels";
import type { State } from "./types";
import type { CustomCommandController } from "./customCommands";

/** One history action contract for the shared scientific and custom-action contexts. */
export function HistoryControls({
  state,
  ready,
  customActive,
  custom,
  run,
}: {
  state: State | null;
  ready: boolean;
  customActive: boolean;
  custom: CustomCommandController;
  run: (command: string) => unknown;
}) {
  return (
    <div
      className="navigation-group navigation-history"
      role="group"
      aria-label="Edit history"
    >
      {[false, true].map((redo) => {
        const name = redo ? "Redo" : "Undo";
        const label = customActive
          ? redo
            ? custom.redoLabel
            : custom.undoLabel
          : historyActionLabel(redo ? state?.redoLabel : state?.undoLabel);
        const available = customActive
          ? redo
            ? custom.canRedo
            : custom.canUndo
          : canTraverseScientificHistory(state, redo);
        const shortcut = redo ? "⇧⌘/Ctrl+Z" : "⌘/Ctrl+Z";
        const Icon = redo ? Redo2 : Undo2;
        return (
          <button
            key={name}
            className="workspace-nav"
            aria-label={name}
            aria-description={label ?? undefined}
            title={
              customActive
                ? (custom.historyHint ??
                  `${name}: ${label ?? "custom action"} · ${shortcut}`)
                : `${name} ${label} · ${shortcut}`
            }
            disabled={!ready || !available}
            onClick={() => {
              if (customActive) void (redo ? custom.redo() : custom.undo());
              else
                void run(
                  scientificHistoryCommand(
                    redo ? state?.redoLabel : state?.undoLabel,
                    redo,
                  ),
                );
            }}
          >
            <Icon size={18} />
          </button>
        );
      })}
    </div>
  );
}
