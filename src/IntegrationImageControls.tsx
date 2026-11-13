import { forwardAction } from "./commandDispatch";
import type { CommandInvocation, CheckedInvocation } from "./commandContracts";
import { Input, Button, Select } from "./ui";
import { IntegrationImageSourceControl } from "./IntegrationImageSourceControl";
import { MiddleElidedInput, MiddleElidedText } from "./MiddleElidedInput";
import { useEffect, useId, useRef, useState } from "react";
import type { State } from "./types";
import type { IntegrationState } from "./integration";
import { IntegrationFileNavigator } from "./IntegrationFileNavigator";
import { IntegrationFrameNavigator } from "./IntegrationFrameNavigator";
import "./integrationFileControls.css";

/** File → source → frame, with the processor's committed folder as the authority. */
export function IntegrationImageControls({
  onOpenBatch,
  batchOpen,
  batchDocked,
  state,
  source,
  fileStep,
  setFileStep,
  frameStep,
  setFrameStep,
  action,
}: {
  onOpenBatch: () => void;
  batchOpen: boolean;
  batchDocked: boolean;
  state: State;
  source: IntegrationState;
  fileStep: number;
  setFileStep: (value: number) => void;
  frameStep: number;
  setFrameStep: (value: number) => void;
  action: import("./commandContracts").CommandAction;
}) {
  const path = state.imagePath ?? "";
  const parent = path.slice(
    0,
    Math.max(0, path.lastIndexOf("/"), path.lastIndexOf("\\")),
  );
  const directory = source.imageDirectory || parent;
  const filename = state.imageName ?? "";
  const [fileDraft, setFileDraft] = useState(filename);
  const [infoOpen, setInfoOpen] = useState(false);
  const [frameError, setFrameError] = useState<string | null>(null);
  const [sourceNotice, setSourceNotice] = useState<string | null>(null);
  const id = useId();
  const statusId = `${id}-status`;
  const previous = useRef({
    path,
    source: state.selectedImageSource,
    frame: source.frame,
    configuration: state.configurationContext ?? state.configurationIndex,
  });
  useEffect(() => setFileDraft(filename), [filename, path]);
  useEffect(() => {
    const before = previous.current;
    const configuration =
      state.configurationContext ?? state.configurationIndex;
    if (
      before.path === path &&
      before.configuration === configuration &&
      before.source !== state.selectedImageSource &&
      before.frame > source.frames
    ) {
      setSourceNotice(
        `Frame ${before.frame} → ${source.frame} · source has ${source.frames} ${source.frames === 1 ? "image" : "frames"}`,
      );
    } else if (before.path !== path || before.configuration !== configuration)
      setSourceNotice(null);
    previous.current = {
      path,
      source: state.selectedImageSource,
      frame: source.frame,
      configuration,
    };
  }, [
    path,
    state.selectedImageSource,
    state.configurationContext,
    state.configurationIndex,
    source.frame,
    source.frames,
  ]);
  const send: import("./commandContracts").CommandAction = <
    A extends CommandInvocation,
  >(
    ...call: CheckedInvocation<A>
  ) => {
    setSourceNotice(null);
    forwardAction<A>(action, call);
  };
  const loadFilename = () => {
    if (fileDraft.trim())
      send("open_image", { path: fileDraft.trim(), directory });
  };
  const showDirectory = source.autoProcess || !path || directory !== parent;
  const location = showDirectory ? directory : path;
  const locationLabel = source.autoProcess
    ? "Watching:"
    : showDirectory
      ? "Folder:"
      : null;
  const shape = state.shape;
  const message = frameError || source.autoProcessError || sourceNotice;
  return (
    <div className="integration-file-controls integration-files-aligned integration-image-files-aligned">
      <IntegrationFileNavigator
        kind="image"
        step={fileStep}
        onStepChange={setFileStep}
        canNavigate={state.hasImage}
        order={source.fileIteration}
        onOrderChange={(mode) => send("integration_navigation", { mode })}
        onLoad={() => {
          if (fileDraft.trim() && fileDraft !== filename) loadFilename();
          else
            send("open_image", {
              directory,
              multiple: true,
              batch_mode: source.imageBatchMode ?? "integrate",
            });
        }}
        onNavigate={(direction) =>
          send("next_image", { direction, step: fileStep, files_only: true })
        }
        filenameControl={
          <MiddleElidedInput
            className="integration-file-path"
            aria-label="Image filename"
            value={fileDraft}
            onChange={(event) => setFileDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                loadFilename();
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setFileDraft(filename);
              }
            }}
            title={fileDraft === filename ? path || filename : fileDraft}
            aria-description="Enter a filename, then press Enter or Load image"
            placeholder="Image filename"
            spellCheck={false}
          />
        }
        folderControl={
          <Button
            aria-label="Choose image folder"
            title={`Image folder: ${directory || "Choose a folder"}`}
            onClick={() => send("integration_image_directory")}
          >
            Folder…
          </Button>
        }
      />
      <IntegrationImageSourceControl
        state={state}
        onChange={(dataset) => send("select_image_source", { dataset })}
      />
      {state.hasImage && (
        <IntegrationFrameNavigator
          frame={source.frame}
          frames={source.frames}
          step={frameStep}
          onStepChange={setFrameStep}
          onSelect={(frame) => send("integration_navigation", { frame })}
          onNavigate={(direction) =>
            send("integration_navigation", { direction, step: frameStep })
          }
          onValidationChange={setFrameError}
          validationId={statusId}
        />
      )}
      <div
        className="integration-image-status"
        aria-label="Image location"
        id={statusId}
      >
        <div
          className="integration-image-location-line"
          aria-label={source.autoProcess ? "Watched folder" : "Image path"}
        >
          {locationLabel && <span>{locationLabel}</span>}
          {location ? (
            <MiddleElidedText value={location} />
          ) : (
            <span>Load an image or choose a folder</span>
          )}
        </div>
        {shape && (
          <span className="integration-image-dimensions">
            {shape[1]} × {shape[0]} px
            {source.frames === 1 ? " · Single image" : ""}
          </span>
        )}
        {message && (
          <span
            className={
              frameError || source.autoProcessError
                ? "ui-field-error"
                : "integration-source-notice"
            }
            role={frameError || source.autoProcessError ? "alert" : "status"}
          >
            {message}
          </span>
        )}
      </div>
      <div className="integration-file-options integration-image-options">
        <div className="integration-file-actions">
          <Button
            type="button"
            aria-expanded={infoOpen}
            aria-controls={`${id}-info`}
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
        <label className="integration-image-batch-modes">
          <span>Batch mode</span>
          <Select
            aria-label="Batch mode"
            value={source.imageBatchMode ?? "integrate"}
            onChange={(event) =>
              send("image_batch_mode", {
                mode: event.target
                  .value as import("./commandPayloads").ImageBatchMode,
              })
            }
            title="Action when loading multiple images"
          >
            {(["integrate", "add", "average", "save"] as const).map((mode) => (
              <option key={mode} value={mode}>
                {mode[0].toUpperCase() + mode.slice(1)}
              </option>
            ))}
          </Select>
        </label>
        <label className="check-row integration-autoprocess">
          <Input
            type="checkbox"
            checked={source.autoProcess}
            onChange={(event) =>
              send("integration_autoprocess", { enabled: event.target.checked })
            }
          />
          Autoprocess
        </label>
      </div>
      <div
        className="integration-image-info"
        hidden={!infoOpen}
        id={`${id}-info`}
      >
        <dl>
          <dt>Loaded image</dt>
          <dd>{path || "No file loaded"}</dd>
          {state.selectedImageSource && (
            <>
              <dt>Image source</dt>
              <dd>{state.selectedImageSource}</dd>
            </>
          )}
          <dt>{source.autoProcess ? "Watched folder" : "Input folder"}</dt>
          <dd>{directory || "No folder selected"}</dd>
        </dl>
        <pre>{source.fileInfo}</pre>
      </div>
    </div>
  );
}
