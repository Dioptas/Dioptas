import { Button, Input } from "./ui";
import { useEffect, useId, useState, type ReactNode } from "react";
import type { State } from "./types";
import type { IntegrationState } from "./integration";
import { IntegrationFileNavigator } from "./IntegrationFileNavigator";
import "./integrationFileControls.css";

/** Qt's file browser: load/watch, file stepping, filename and working folder. */
export function IntegrationImageControls({
  onOpenBatch,
  batchOpen,
  batchDocked,
  state,
  source,
  fileStep,
  setFileStep,
  action,
  frameControl,
}: {
  onOpenBatch: () => void;
  batchOpen: boolean;
  batchDocked: boolean;
  state: State | null;
  source: IntegrationState;
  fileStep: number;
  setFileStep: (value: number) => void;
  action: (command: string, args?: Record<string, unknown>) => void;
  frameControl: ReactNode;
}) {
  const path = state?.imagePath ?? "";
  const directory =
    source.imageDirectory ??
    path.slice(0, Math.max(0, path.lastIndexOf("/"), path.lastIndexOf("\\")));
  const filename = state?.imageName ?? "";
  const [fileDraft, setFileDraft] = useState(filename);
  const [directoryDraft, setDirectoryDraft] = useState(directory);
  const [infoOpen, setInfoOpen] = useState(false);
  const infoId = useId();
  useEffect(() => setFileDraft(filename), [filename, path]);
  useEffect(() => setDirectoryDraft(directory), [directory]);
  const loadFilename = () => {
    if (fileDraft.trim())
      action("open_image", {
        path: fileDraft.trim(),
        directory: directoryDraft,
      });
  };
  return (
    <div className="integration-file-controls">
      <IntegrationFileNavigator
        kind="image"
        step={fileStep}
        onStepChange={setFileStep}
        canNavigate={!!state?.hasImage}
        order={source.fileIteration}
        onOrderChange={(mode) => action("integration_navigation", { mode })}
        checkboxLabel="Autoprocess"
        checked={!!source.autoProcess}
        onCheckedChange={(enabled) =>
          action("integration_autoprocess", {
            enabled,
            directory: directoryDraft,
          })
        }
        onLoad={() => {
          if (fileDraft.trim() && fileDraft !== filename) loadFilename();
          else
            action("open_image", {
              directory: directoryDraft,
              multiple: true,
              batch_mode: source.imageBatchMode ?? "integrate",
            });
        }}
        onNavigate={(direction) =>
          action("next_image", { direction, step: fileStep })
        }
      />
      {frameControl}
      <Input
        className="integration-file-path"
        aria-label="Image filename"
        value={fileDraft}
        onChange={(event) => setFileDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            loadFilename();
          }
          if (event.key === "Escape") setFileDraft(filename);
        }}
        title="Enter a filename, then press Enter or Load image"
        placeholder="Image filename"
        spellCheck={false}
      />
      <div className="integration-file-directory">
        <Input
          className="integration-file-path"
          aria-label="Image directory"
          value={directoryDraft}
          onChange={(event) => setDirectoryDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              action("integration_image_directory", { path: directoryDraft });
            }
            if (event.key === "Escape") setDirectoryDraft(directory);
          }}
          title="Enter an image directory and press Enter"
          placeholder="Image directory"
          spellCheck={false}
        />
        <Button
          aria-label="Choose image folder"
          title="Choose image folder"
          onClick={() => action("integration_image_directory")}
        >
          …
        </Button>
      </div>
      <div
        className="integration-image-batch-modes"
        role="radiogroup"
        aria-label="Batch mode"
      >
        <span>Batch mode:</span>
        {(["integrate", "add", "average", "save"] as const).map((mode) => (
          <label
            className="check-row"
            key={mode}
            title={
              {
                integrate: "Integrate all selected images",
                add: "Add all selected images",
                average: "Average all selected images",
                save: "Save corrected copies of all selected images",
              }[mode]
            }
          >
            <Input
              type="radio"
              name={`${infoId}-batch-mode`}
              aria-label={`Batch mode ${mode}`}
              checked={(source.imageBatchMode ?? "integrate") === mode}
              onChange={() => action("image_batch_mode", { mode })}
            />
            {mode[0].toUpperCase() + mode.slice(1)}
          </label>
        ))}
      </div>
      <div className="integration-file-actions">
        <Button
          type="button"
          aria-expanded={infoOpen}
          aria-controls={infoId}
          onClick={() => setInfoOpen((open) => !open)}
        >
          File Info
        </Button>
        <Button
          type="button"
          aria-label="Batch view…"
          aria-pressed={batchOpen}
          title={
            batchDocked
              ? "Hide docked Batch view"
              : batchOpen
                ? "Show open Batch window"
                : "Open Batch view"
          }
          onClick={onOpenBatch}
        >
          Batch…
        </Button>
      </div>
      <div className="integration-image-info" hidden={!infoOpen}>
        <pre id={infoId}>{source.fileInfo || path || "No file loaded"}</pre>
      </div>
    </div>
  );
}
