import type { CustomCommandPayload } from "./commandPayloads";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Invoke } from "./types";
import { commandIconChoices, type CommandIconId } from "./customCommandIcons";

const iconPreferencesKey = "dioptas-custom-command-icons-v1";
const orderPreferencesKey = "dioptas-custom-command-order-v1";
type IconPreferences = Record<string, CommandIconId>;

function readIconPreferences(): IconPreferences {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem(iconPreferencesKey) ?? "{}",
    );
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
    return Object.fromEntries(
      Object.entries(saved).filter(([, icon]) =>
        commandIconChoices.some((choice) => choice.id === icon),
      ),
    );
  } catch {
    return {};
  }
}

function commandId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

function readCommandOrder(): string[] {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem(orderPreferencesKey) ?? "[]",
    );
    return Array.isArray(saved)
      ? saved.filter((id): id is string => typeof id === "string")
      : [];
  } catch {
    return [];
  }
}

function orderedCommands(commands: CustomCommand[], order: string[]) {
  const ranks = new Map(order.map((id, index) => [id, index]));
  return commands
    .slice()
    .sort(
      (a, b) =>
        (ranks.get(a.id) ?? order.length) - (ranks.get(b.id) ?? order.length),
    );
}

function copyCommands(commands: CustomCommand[]) {
  return commands.map((command) => ({
    ...command,
    arguments: command.arguments.slice(),
  }));
}

function sameCommands(a: CustomCommand[], b: CustomCommand[]) {
  const values = (commands: CustomCommand[]) =>
    commands.map((c) => [
      c.id,
      c.name,
      c.program,
      c.arguments,
      c.enabled,
      c.icon ?? "terminal",
    ]);
  return JSON.stringify(values(a)) === JSON.stringify(values(b));
}

interface ActionHistoryEntry {
  before: CustomCommand[];
  after: CustomCommand[];
  label: string;
}

export interface CustomCommand {
  id: string;
  name: string;
  program: string;
  arguments: string[];
  enabled: boolean;
  icon?: CommandIconId;
}
export interface CustomCommandRun {
  running: boolean;
  exitCode: number | null;
  output: string;
  name: string;
  arguments: string[];
}
export const commandInputs = [
  ["image_path", "Image path", "Full path of the current detector file"],
  ["frame_index", "Frame index", "Current frame, starting at 0"],
  ["frame_number", "Frame number", "Current frame, starting at 1"],
  ["dataset", "Dataset", "Selected HDF5 image source"],
  ["calibration_path", "Calibration path", "Loaded or last saved .poni file"],
  ["project_path", "Project path", "Current saved .dio project"],
  ["wavelength_angstrom", "Wavelength (Å)", "Current calibrated wavelength"],
  ["image_name", "Image filename", "Filename including its extension"],
  ["image_directory", "Image folder", "Folder containing the detector file"],
] as const;
export type CommandContext = Record<string, string | number | null>;

export function missingCommandInput(
  command: CustomCommand,
  context: CommandContext,
) {
  for (const argument of command.arguments) {
    for (const match of argument.matchAll(/\{([a-z_][a-z_0-9]*)\}/g)) {
      const value = context[match[1]];
      if (value === undefined || value === null || value === "")
        return commandInputs.find(([key]) => key === match[1])?.[1] ?? match[1];
    }
  }
  return null;
}

type CustomRequestCall =
  | [operation?: "list", payload?: {}, recordHistory?: boolean]
  | [
      operation: "save",
      payload: { command: CustomCommand },
      recordHistory?: boolean,
    ]
  | [
      operation: "delete" | "run",
      payload: { identifier: string },
      recordHistory?: boolean,
    ];
export function useCustomCommands(invoke: Invoke, session: unknown) {
  const [commands, setCommands] = useState<CustomCommand[]>([]);
  const [runs, setRuns] = useState<Record<string, CustomCommandRun>>({});
  const [context, setContext] = useState<CommandContext>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [editorDirty, setEditorDirty] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [historyRevision, setHistoryRevision] = useState(0);
  const [, refreshHistory] = useState(0);
  const currentCommands = useRef<CustomCommand[]>([]);
  const history = useRef<{
    undo: ActionHistoryEntry[];
    redo: ActionHistoryEntry[];
  }>({ undo: [], redo: [] });
  const applyingHistory = useRef(false);
  const recordChange = useCallback(
    (before: CustomCommand[], after: CustomCommand[], label: string) => {
      if (sameCommands(before, after)) return;
      history.current = {
        undo: [
          ...history.current.undo,
          { before: copyCommands(before), after: copyCommands(after), label },
        ].slice(-100),
        redo: [],
      };
      refreshHistory((value) => value + 1);
    },
    [],
  );
  const requestVersion = useRef(0);
  const mutatePending = useRef(false);
  const iconPreferences = useRef<IconPreferences | null>(null);
  const commandOrder = useRef<string[] | null>(null);
  if (commandOrder.current === null) commandOrder.current = readCommandOrder();
  if (iconPreferences.current === null)
    iconPreferences.current = readIconPreferences();
  const request = useCallback(
    async (...call: CustomRequestCall) => {
      const [operation = "list", payload = {}, recordHistory = true] = call;
      if (applyingHistory.current && recordHistory) return false;
      if (operation === "list" && mutatePending.current) return false;
      if (operation !== "list" && mutatePending.current) return false;
      const version = ++requestVersion.current;
      if (operation !== "list") {
        mutatePending.current = true;
        setPending(true);
      }
      try {
        const before = copyCommands(currentCommands.current);
        const submitted = call[0] === "save" ? { ...call[1].command } : null;
        // Supplying the ID also lets older workers return a newly saved action
        // that can be matched to its frontend-only appearance preference.
        if (submitted && !submitted.id) submitted.id = commandId();
        let requestPayload: CustomCommandPayload;
        if (operation === "list") requestPayload = { operation };
        else if (operation === "save" && submitted)
          requestPayload = { operation, command: submitted };
        else if (call[0] === "delete" || call[0] === "run")
          requestPayload = {
            operation: call[0],
            identifier: call[1].identifier,
          };
        else throw Error("Choose a custom action operation.");
        let result = await invoke("custom_command", requestPayload);
        // A preview worker loaded before the expanded icon set may accept only
        // the original symbols. Keep the chosen appearance in the frontend.
        if (
          !result.ok &&
          submitted &&
          [
            "Choose an available command icon.",
            "Choose an available action icon.",
          ].includes(result.error ?? "")
        ) {
          result = await invoke("custom_command", {
            operation: "save",
            command: { ...submitted, icon: "terminal" },
          });
        }
        if (!result.ok)
          throw new Error(result.error ?? "Custom action failed.");
        const preferences = { ...iconPreferences.current };
        if (submitted) {
          const saved = result.customCommands?.find(
            (command) => command.id === submitted.id,
          );
          const icon = submitted.icon ?? "terminal";
          if (!saved)
            throw new Error("The saved custom action was not returned.");
          if (saved.icon === icon || (!saved.icon && icon === "terminal"))
            delete preferences[submitted.id];
          else preferences[submitted.id] = icon;
        } else if (
          operation === "delete" &&
          "identifier" in payload &&
          typeof payload.identifier === "string"
        ) {
          delete preferences[payload.identifier];
        }
        let preferenceWarning: string | null = null;
        if (operation === "save" || operation === "delete") {
          iconPreferences.current = preferences;
          try {
            localStorage.setItem(
              iconPreferencesKey,
              JSON.stringify(preferences),
            );
          } catch {
            if (submitted && preferences[submitted.id])
              preferenceWarning =
                "The icon is applied for this session. Local preferences are unavailable; restart Dioptas to retain it with the updated processing worker.";
          }
        }
        if (version === requestVersion.current) {
          const next = orderedCommands(
            (result.customCommands ?? []).map((command) => ({
              ...command,
              icon: preferences[command.id] ?? command.icon,
            })),
            commandOrder.current ?? [],
          );
          const previousCommands = currentCommands.current;
          currentCommands.current = next;
          setLoaded(true);
          setCommands(next);
          if (
            recordHistory &&
            (operation === "save" || operation === "delete")
          ) {
            const affectedId =
              submitted?.id ??
              ("identifier" in payload ? payload.identifier : undefined);
            const previous = before.find(
              (command) => command.id === affectedId,
            );
            const label =
              operation === "delete"
                ? `Delete action “${previous?.name ?? ""}”`
                : previous
                  ? `Edit action “${submitted!.name}”`
                  : `Create action “${submitted!.name}”`;
            if (
              sameCommands(
                before.filter((command) => command.id !== affectedId),
                next.filter((command) => command.id !== affectedId),
              )
            ) {
              recordChange(before, next, label);
            } else {
              // Do not include unrelated external changes in an undo entry.
              history.current = { undo: [], redo: [] };
              refreshHistory((value) => value + 1);
              preferenceWarning =
                "Custom actions changed outside this window. Action history has been reset.";
            }
          } else if (
            recordHistory &&
            operation === "list" &&
            !sameCommands(previousCommands, next)
          ) {
            // Changes made outside this UI establish a fresh history baseline.
            history.current = { undo: [], redo: [] };
            refreshHistory((value) => value + 1);
          }
          setRuns(result.customCommandRuns ?? {});
          setContext(result.customCommandContext ?? {});
          setError(preferenceWarning);
        }
        return true;
      } catch (error) {
        if (version === requestVersion.current)
          setError(error instanceof Error ? error.message : String(error));
        return false;
      } finally {
        if (operation !== "list") {
          mutatePending.current = false;
          setPending(false);
        }
      }
    },
    [invoke, recordChange],
  );
  useEffect(() => {
    if (session) void request();
  }, [session, request]);
  const running = Object.values(runs).some((run) => run.running);
  useEffect(() => {
    if (!running) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      await request();
      if (!cancelled) timer = setTimeout(poll, 1000);
    };
    timer = setTimeout(poll, 500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [running, request]);
  const reorderCommand = (
    identifier: string,
    target: string,
    placement: "before" | "after",
  ) => {
    if (
      mutatePending.current ||
      applyingHistory.current ||
      identifier === target
    )
      return;
    const before = currentCommands.current;
    const command = before.find((command) => command.id === identifier);
    const reordered = before.filter((command) => command.id !== identifier);
    const targetIndex = reordered.findIndex((command) => command.id === target);
    if (!command || targetIndex < 0) return;
    reordered.splice(targetIndex + (placement === "after" ? 1 : 0), 0, command);
    commandOrder.current = reordered.map((command) => command.id);
    currentCommands.current = reordered;
    setCommands(reordered);
    recordChange(before, reordered, "Reorder actions");
    try {
      localStorage.setItem(
        orderPreferencesKey,
        JSON.stringify(commandOrder.current),
      );
      setError(null);
    } catch {
      setError(
        "Action order changed for this session; interface preferences could not be saved.",
      );
    }
  };
  const moveCommand = (identifier: string, direction: -1 | 1) => {
    const index = commands.findIndex((command) => command.id === identifier);
    const target = commands[index + direction];
    if (index >= 0 && target)
      reorderCommand(identifier, target.id, direction < 0 ? "before" : "after");
  };
  const wouldDeleteRunningAction = (target: CustomCommand[]) =>
    currentCommands.current.some(
      (command) =>
        runs[command.id]?.running &&
        !target.some((item) => item.id === command.id),
    );
  const restoreHistory = async (direction: "undo" | "redo") => {
    const entry = history.current[direction].at(-1);
    if (
      !entry ||
      editorDirty ||
      mutatePending.current ||
      applyingHistory.current
    )
      return;
    const target = direction === "undo" ? entry.before : entry.after;
    if (wouldDeleteRunningAction(target)) return;
    applyingHistory.current = true;
    setRestoring(true);
    try {
      if (!(await request("list", {}, false))) return;
      if (
        !sameCommands(
          currentCommands.current,
          direction === "undo" ? entry.after : entry.before,
        )
      ) {
        history.current = { undo: [], redo: [] };
        setError(
          "Custom actions changed outside this window. Action history has been reset.",
        );
        return;
      }
      const current = copyCommands(currentCommands.current);
      // Each entry changes one definition, or just the locally persisted order.
      // Reuse the normal validated save/delete path; never execute an action.
      for (const command of current) {
        if (!target.some((item) => item.id === command.id)) {
          if (!(await request("delete", { identifier: command.id }, false)))
            return;
        }
      }
      for (const command of target) {
        const previous = current.find((item) => item.id === command.id);
        if (!previous || !sameCommands([previous], [command])) {
          if (!(await request("save", { command }, false))) return;
        }
      }
      commandOrder.current = target.map((command) => command.id);
      const restored = orderedCommands(
        currentCommands.current,
        commandOrder.current,
      );
      currentCommands.current = restored;
      setCommands(restored);
      try {
        localStorage.setItem(
          orderPreferencesKey,
          JSON.stringify(commandOrder.current),
        );
        setError(null);
      } catch {
        setError(
          "Action order restored for this session; interface preferences could not be saved.",
        );
      }
      history.current[direction].pop();
      history.current[direction === "undo" ? "redo" : "undo"].push(entry);
      setHistoryRevision((value) => value + 1);
    } finally {
      applyingHistory.current = false;
      setRestoring(false);
      refreshHistory((value) => value + 1);
    }
  };
  const undoEntry = history.current.undo.at(-1);
  const redoEntry = history.current.redo.at(-1);
  return {
    commands,
    runs,
    context,
    error,
    pending: pending || restoring || !loaded,
    request,
    moveCommand,
    reorderCommand,
    canUndo:
      !!undoEntry &&
      !pending &&
      !restoring &&
      !editorDirty &&
      !wouldDeleteRunningAction(undoEntry.before),
    canRedo:
      !!redoEntry &&
      !pending &&
      !restoring &&
      !editorDirty &&
      !wouldDeleteRunningAction(redoEntry.after),
    undoLabel: undoEntry?.label,
    redoLabel: redoEntry?.label,
    historyHint: editorDirty ? "Save or cancel the current edit first." : null,
    undo: () => restoreHistory("undo"),
    redo: () => restoreHistory("redo"),
    historyRevision,
    setEditorDirty,
  };
}
export type CustomCommandController = ReturnType<typeof useCustomCommands>;
