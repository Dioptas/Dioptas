import { useEffect, useState, type ReactNode } from "react";
import type { State } from "./types";
import type { IntegrationState } from "./integration";
import { IntegrationFileNavigator } from "./IntegrationFileNavigator";
import "./integrationFileControls.css";

/** Qt's file browser: load/watch, file stepping, filename and working folder. */
export function IntegrationImageControls({
  onOpenBatch,
  state,
  source,
  fileStep,
  setFileStep,
  action,
  frameControl,
}: {
  onOpenBatch: () => void;
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
            action("open_image", { directory: directoryDraft, multiple: true });
        }}
        onNavigate={(direction) =>
          action("next_image", { direction, step: fileStep })
        }
      />
      <button className="secondary" onClick={onOpenBatch}>
        Batch view…
      </button>
      {frameControl}
      <input
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
        <input
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
        <button
          aria-label="Choose image folder"
          title="Choose image folder"
          onClick={() => action("integration_image_directory")}
        >
          …
        </button>
      </div>
      <details className="integration-image-info">
        <summary>File Info</summary>
        <pre>{source.fileInfo || path || "No file loaded"}</pre>
      </details>
    </div>
  );
}
