import { Button, Input, TextArea } from "./ui";
import { useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, GripVertical, Plus, Trash2 } from "lucide-react";
import { getCommandIcon } from "./customCommandIcons";
import { CustomCommandIconPicker } from "./CustomCommandIconPicker";
import {
  commandInputs,
  type CustomCommand,
  type CustomCommandController,
} from "./customCommands";
import "./customCommands.css";

const blank = (): CustomCommand => ({
  id: "",
  name: "",
  program: "",
  arguments: ["{image_path}", "{frame_index}"],
  enabled: true,
  icon: "terminal",
});

export function CustomCommandSettings({
  controller,
  ready,
}: {
  controller: CustomCommandController;
  ready: boolean;
}) {
  const {
    commands,
    runs,
    context,
    error,
    pending,
    request,
    moveCommand,
    reorderCommand,
    historyRevision,
    setEditorDirty,
  } = controller;
  const [draft, setDraft] = useState<CustomCommand | null>(null);
  const [argumentsText, setArgumentsText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const seenHistoryRevision = useRef(historyRevision);
  useLayoutEffect(() => {
    setEditorDirty(dirty);
    return () => setEditorDirty(false);
  }, [dirty, setEditorDirty]);
  useLayoutEffect(() => {
    if (seenHistoryRevision.current === historyRevision) return;
    seenHistoryRevision.current = historyRevision;
    if (draft?.id) {
      const restored = commands.find((command) => command.id === draft.id);
      setDraft(restored ? { ...restored } : null);
      setArgumentsText(restored?.arguments.join("\n") ?? "");
    }
    setDirty(false);
    setNotice("");
  }, [historyRevision, commands, draft?.id]);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<{
    id: string;
    placement: "before" | "after";
  } | null>(null);
  const scrollPane = useRef<HTMLDivElement>(null);
  const [previewWidth, setPreviewWidth] = useState(59);
  useLayoutEffect(() => {
    const nav = document.querySelector<HTMLElement>(".mode-navigation");
    if (!nav) return;
    const measure = () => {
      const button = nav.querySelector<HTMLElement>(
        ".navigation-custom-commands .workspace-nav",
      );
      setPreviewWidth(
        button?.getBoundingClientRect().width ?? nav.clientWidth - 8,
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(nav);
    return () => observer.disconnect();
  }, [commands.length]);
  const endDrag = () => {
    setDraggedId(null);
    setDropTarget(null);
  };
  const edit = (command: CustomCommand) => {
    setDraft({ ...command });
    setArgumentsText(command.arguments.join("\n"));
    setDirty(false);
    setNotice("");
  };
  const change = (values: Partial<CustomCommand>) => {
    setDraft((draft) => draft && { ...draft, ...values });
    setDirty(true);
    setNotice("");
  };
  const deleteAction = async (identifier: string) => {
    if (await request("delete", { identifier })) {
      if (draft?.id === identifier) {
        setDraft(null);
        setDirty(false);
      }
      setNotice("Action deleted.");
    }
  };
  const argumentsList = argumentsText === "" ? [] : argumentsText.split("\n");
  const validTokens = argumentsList.every((argument) =>
    [...argument.matchAll(/\{([a-z_][a-z_0-9]*)\}/g)].every((match) =>
      commandInputs.some(([key]) => key === match[1]),
    ),
  );
  const run = draft?.id ? runs[draft.id] : null;
  const PreviewIcon = getCommandIcon(draft?.icon);
  return (
    <div
      className="custom-command-settings"
      aria-busy={pending}
      ref={scrollPane}
      onDragOver={(event) => {
        if (!draggedId || dirty || pending) return;
        const pane = scrollPane.current;
        if (!pane) return;
        const bounds = pane.getBoundingClientRect();
        if (event.clientY < bounds.top + 40) pane.scrollTop -= 16;
        else if (event.clientY > bounds.bottom - 40) pane.scrollTop += 16;
      }}
    >
      {error && (
        <p className="custom-command-error" role="alert">
          {error}
        </p>
      )}
      <div
        className="custom-command-list"
        role="group"
        aria-label="Saved custom actions"
      >
        {commands.map((command, index) => {
          const Icon = getCommandIcon(command.icon);
          return (
            <div
              key={command.id}
              className="custom-command-entry"
              data-command-id={command.id}
              data-dragging={draggedId === command.id || undefined}
              data-drop={
                dropTarget?.id === command.id ? dropTarget.placement : undefined
              }
              onDragOver={(event) => {
                if (!draggedId || dirty || pending || draggedId === command.id)
                  return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                const bounds = event.currentTarget.getBoundingClientRect();
                setDropTarget({
                  id: command.id,
                  placement:
                    event.clientY < bounds.top + bounds.height / 2
                      ? "before"
                      : "after",
                });
              }}
              onDrop={(event) => {
                if (!draggedId || dirty || pending || draggedId === command.id)
                  return;
                event.preventDefault();
                const source = event.dataTransfer.getData(
                  "application/x-dioptas-custom-command",
                );
                if (source === draggedId) {
                  const bounds = event.currentTarget.getBoundingClientRect();
                  reorderCommand(
                    source,
                    command.id,
                    event.clientY < bounds.top + bounds.height / 2
                      ? "before"
                      : "after",
                  );
                }
                endDrag();
              }}
            >
              <Button
                type="button"
                className="custom-command-drag-handle"
                aria-label={`Drag ${command.name} to reorder`}
                title="Drag to reorder · Up/Down keys also move this action"
                disabled={dirty || pending || commands.length < 2}
                draggable={!dirty && !pending && commands.length > 1}
                onDragStart={(event) => {
                  event.dataTransfer.setData(
                    "application/x-dioptas-custom-command",
                    command.id,
                  );
                  event.dataTransfer.setData("text/plain", command.name);
                  event.dataTransfer.effectAllowed = "move";
                  if (event.currentTarget.parentElement)
                    event.dataTransfer.setDragImage(
                      event.currentTarget.parentElement,
                      12,
                      12,
                    );
                  setDraggedId(command.id);
                }}
                onDragEnd={endDrag}
                onKeyDown={(event) => {
                  if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                    event.preventDefault();
                    moveCommand(command.id, event.key === "ArrowUp" ? -1 : 1);
                  }
                }}
              >
                <GripVertical size={16} />
              </Button>
              <Button
                className="custom-command-edit"
                title={command.name}
                aria-pressed={draft?.id === command.id}
                disabled={dirty || pending}
                onClick={() => edit(command)}
              >
                <Icon size={16} />
                <span>
                  {command.name}
                  {!command.enabled ? " · hidden" : ""}
                </span>
              </Button>
              <Button
                aria-label={`Move ${command.name} up`}
                title="Move up"
                disabled={dirty || pending || index === 0}
                onClick={() => moveCommand(command.id, -1)}
              >
                <ArrowUp size={15} />
              </Button>
              <Button
                aria-label={`Move ${command.name} down`}
                title="Move down"
                disabled={dirty || pending || index === commands.length - 1}
                onClick={() => moveCommand(command.id, 1)}
              >
                <ArrowDown size={15} />
              </Button>
              <Button
                type="button"
                className="custom-command-delete"
                aria-label={`Delete action: ${command.name}`}
                title={`Delete action: ${command.name}`}
                disabled={!ready || pending || !!runs[command.id]?.running}
                onClick={() => void deleteAction(command.id)}
              >
                <Trash2 size={15} />
              </Button>
            </div>
          );
        })}
        <Button
          className="custom-command-add"
          disabled={dirty || pending}
          onClick={() => edit(blank())}
        >
          <Plus size={16} />
          Add action
        </Button>
      </div>
      {commands.length > 1 && (
        <p className="settings-save-note">
          Drag an action by its handle, or use the arrows, to set the sidebar
          and menu order. Order changes are saved immediately.
        </p>
      )}
      {!draft ? (
        <section className="settings-card">
          <h3>Run your own tools</h3>
          <p>
            Add a named button for a program or script you use alongside
            Dioptas. Choose which details to pass, such as the current image
            path, frame index, calibration path, or project path, or run it
            without extra inputs.
          </p>
          <p className="settings-detail">
            Open an image in another app, run a processing script, or look up
            beamline metadata. Saved buttons appear above Undo and Redo in the
            left sidebar.
          </p>
        </section>
      ) : (
        <form
          className="settings-card custom-command-editor"
          onSubmit={async (event) => {
            event.preventDefault();
            if (
              await request("save", {
                command: { ...draft, arguments: argumentsList },
              })
            ) {
              setDraft(null);
              setDirty(false);
              setNotice("Action saved.");
            }
          }}
        >
          <div className="custom-command-name-row">
            <label>
              Button name
              <Input
                autoFocus
                required
                maxLength={80}
                disabled={pending}
                value={draft.name}
                placeholder="Move"
                aria-describedby="custom-command-name-help"
                onChange={(event) => change({ name: event.target.value })}
              />
            </label>
            <div
              className="custom-command-label-preview"
              role="group"
              style={{ width: previewWidth }}
              aria-label="Sidebar button preview"
              title={draft.name || "Button name"}
            >
              <PreviewIcon size={18} aria-hidden="true" />
              <span>{draft.name || "Label"}</span>
            </div>
          </div>
          <p id="custom-command-name-help">
            Aim for one short word, such as Move or Lookup. The preview shows
            how it fits in the sidebar.
          </p>
          <CustomCommandIconPicker
            value={draft.icon}
            disabled={!ready || pending}
            onChange={(icon) => change({ icon })}
          />
          <label>
            Program or executable script
            <Input
              required
              value={draft.program}
              disabled={pending}
              placeholder="/usr/bin/python3"
              onChange={(event) => change({ program: event.target.value })}
            />
          </label>
          <p>
            For Python, enter the interpreter above and put the script’s full
            path on the first argument line. For a shell script, use its
            executable path or a shell such as /bin/bash.
          </p>
          <label>
            Arguments · one per line
            <TextArea
              rows={5}
              disabled={pending}
              spellCheck={false}
              value={argumentsText}
              onChange={(event) => {
                setArgumentsText(event.target.value);
                setDirty(true);
                setNotice("");
              }}
              aria-describedby="custom-command-argument-help"
            />
          </label>
          <p id="custom-command-argument-help">
            Each line is one argument. Paths with spaces need no quotes. Click
            an input below to append it; you can also write
            --image=&#123;image_path&#125;.
          </p>
          {!validTokens && (
            <p role="alert" className="custom-command-error">
              Unknown input placeholder. Choose one of the inputs below.
            </p>
          )}
          <div
            className="custom-command-inputs"
            role="group"
            aria-label="Available action inputs"
          >
            {commandInputs.map(([key, label, description]) => (
              <Button
                key={key}
                type="button"
                title={`${description}. ${context[key] ?? "Currently unavailable"}`}
                onClick={() => {
                  setArgumentsText((text) =>
                    text ? `${text}\n{${key}}` : `{${key}}`,
                  );
                  setDirty(true);
                  setNotice("");
                }}
              >
                {label}
              </Button>
            ))}
          </div>
          <details className="custom-command-context">
            <summary>Current input values</summary>
            <dl>
              {commandInputs.map(([key, label, description]) => (
                <div key={key}>
                  <dt title={description}>{label}</dt>
                  <dd>{context[key] ?? "Unavailable"}</dd>
                </div>
              ))}
            </dl>
            <p>
              Frame index starts at 0; frame number starts at 1. Calibration
              path refers to the loaded or last saved file. Save edited geometry
              as .poni before using that file in another tool.
            </p>
          </details>
          <label className="check-row">
            <Input
              type="checkbox"
              disabled={pending}
              checked={draft.enabled}
              onChange={(event) => change({ enabled: event.target.checked })}
            />
            Show button in sidebar
          </label>
          <div className="custom-command-actions">
            <Button
              type="submit"
              variant="primary"
              disabled={
                !ready ||
                pending ||
                !draft.name.trim() ||
                !draft.program.trim() ||
                !validTokens
              }
            >
              Save action
            </Button>
            <Button
              type="button"
              disabled={pending}
              onClick={() => {
                setDraft(null);
                setDirty(false);
                setNotice("");
              }}
            >
              Cancel
            </Button>
            {draft.id && (
              <Button
                type="button"
                disabled={!ready || pending || !!run?.running}
                onClick={() => void deleteAction(draft.id)}
              >
                Delete action
              </Button>
            )}
          </div>
        </form>
      )}
      {notice && (
        <p role="status" className="settings-save-note">
          {notice}
        </p>
      )}
      {Object.entries(runs).map(([id, run]) => (
        <section key={id} className="settings-card custom-command-output">
          <h3>
            {run.name} ·{" "}
            {run.running
              ? "Running…"
              : run.exitCode === 0
                ? "Finished"
                : `Failed (exit ${run.exitCode})`}
          </h3>
          <details>
            <summary>Program and arguments</summary>
            <pre>{run.arguments.join("\n")}</pre>
          </details>
          {run.output && (
            <pre aria-label={`${run.name} output`}>{run.output}</pre>
          )}
        </section>
      ))}
    </div>
  );
}
