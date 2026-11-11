import { Input, Button, Portal } from "./ui";
import { Dialog } from "./Dialog";
import { MiddleElidedInput, MiddleElidedText } from "./MiddleElidedInput";
import { useEffect, useId, useState } from "react";
import type { IntegrationRun, IntegrationState } from "./integration";
import { Check } from "./IntegrationFields";
import { IntegrationFileNavigator } from "./IntegrationFileNavigator";
import "./integrationFileControls.css";
import "./integrationPatternControls.css";

/** Qt PatternWidget: a file browser and one row of autocreate formats. */
export function IntegrationPatternControls({
  source,
  action,
  step,
  setStep,
}: {
  source: IntegrationState;
  action: (
    command: string,
    args?: Record<string, unknown>,
    onSuccess?: Parameters<IntegrationRun>[3],
  ) => Promise<void>;
  step: number;
  setStep: (value: number) => void;
}) {
  const path = source.patternPath ?? "";
  const filename = path.split(/[\\/]/).at(-1) ?? "";
  const [fileDraft, setFileDraft] = useState(filename);
  const [folderNoticeOpen, setFolderNoticeOpen] = useState(false);
  const folderNoticeId = useId();
  const directory = source.outputDirectory;
  useEffect(() => setFileDraft(filename), [filename, path]);
  const loadFilename = () => {
    if (fileDraft.trim())
      action("integration_open_pattern", {
        path: fileDraft.trim(),
        directory,
      });
  };
  const chooseAutocreateFolder = async () => {
    setFolderNoticeOpen(false);
    let selected: string | undefined;
    await action("integration_output_directory", {}, (result) => {
      if (!result.cancelled)
        selected = result.state?.integration?.outputDirectory;
    });
    if (selected)
      await action("integration_autocreate", {
        enabled: true,
        directory: selected,
      });
  };
  const setAutocreate = async (enabled: boolean) => {
    if (enabled && !directory) {
      setFolderNoticeOpen(true);
    } else {
      await action("integration_autocreate", {
        enabled,
        ...(directory ? { directory } : {}),
      });
    }
  };
  return (
    <div className="integration-file-controls integration-files-aligned integration-pattern-files">
      <IntegrationFileNavigator
        kind="pattern"
        step={step}
        onStepChange={setStep}
        canNavigate={!!path}
        order={source.patternFileIteration ?? "number"}
        onOrderChange={(mode) =>
          action("integration_pattern_navigation", { mode })
        }
        onLoad={() => {
          if (fileDraft.trim() && fileDraft !== filename) loadFilename();
          else action("integration_open_pattern", { directory });
        }}
        onNavigate={(direction) =>
          action("integration_open_pattern", { direction, step })
        }
        filenameControl={
          <MiddleElidedInput
            className="integration-file-path"
            aria-label="Pattern filename"
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
            aria-description="Enter a filename, then press Enter or Load pattern"
            placeholder="Pattern filename"
            spellCheck={false}
          />
        }
        folderControl={
          <Button
            aria-label="Choose pattern folder"
            title={`Pattern input and autocreate output folder: ${directory || "Choose a folder"}`}
            onClick={() => action("integration_output_directory")}
          >
            Folder…
          </Button>
        }
      />

      <div className="integration-image-status" aria-label="Pattern location">
        <div
          className="integration-image-location-line"
          aria-label="Pattern folder"
        >
          {directory ? (
            <MiddleElidedText value={directory} />
          ) : (
            <span>Load a pattern or choose a folder</span>
          )}
        </div>
      </div>
      <div
        className="integration-file-options integration-pattern-options"
        role="group"
        aria-label="Autocreate pattern formats"
      >
        <label className="check-row integration-autocreate">
          <Input
            type="checkbox"
            checked={source.autoSave}
            onChange={(event) => setAutocreate(event.target.checked)}
          />
          Autocreate
        </label>
        {[".xy", ".xye", ".chi", ".dat", ".fxye"].map((format) => (
          <Check
            key={format}
            label={format}
            checked={source.formats.includes(format)}
            onChange={(enabled) =>
              action("integration_settings", {
                formats: enabled
                  ? [...source.formats, format]
                  : source.formats.filter((entry) => entry !== format),
              })
            }
          />
        ))}
      </div>
      {folderNoticeOpen && (
        <Portal>
          <Dialog
            className="ui-confirm-dialog autocreate-folder-dialog"
            aria-labelledby={`${folderNoticeId}-title`}
            aria-describedby={`${folderNoticeId}-description`}
            onDismiss={() => setFolderNoticeOpen(false)}
          >
            <h2 id={`${folderNoticeId}-title`}>Choose a save folder</h2>
            <p id={`${folderNoticeId}-description`}>
              Before enabling Autocreate, select the folder where pattern files
              will be saved.
            </p>
            <div className="ui-dialog-actions">
              <Button type="button" onClick={() => setFolderNoticeOpen(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                autoFocus
                onClick={chooseAutocreateFolder}
              >
                Choose folder…
              </Button>
            </div>
          </Dialog>
        </Portal>
      )}
    </div>
  );
}
