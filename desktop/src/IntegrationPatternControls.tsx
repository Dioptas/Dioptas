import { Input, Button } from "./ui";
import { MiddleElidedInput } from "./MiddleElidedInput";
import { useEffect, useState } from "react";
import type { IntegrationState } from "./integration";
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
  action: (command: string, args?: Record<string, unknown>) => void;
  step: number;
  setStep: (value: number) => void;
}) {
  const path = source.patternPath ?? "";
  const filename = path.split(/[\\/]/).at(-1) ?? "";
  const [fileDraft, setFileDraft] = useState(filename);
  const [directoryDraft, setDirectoryDraft] = useState(source.outputDirectory);
  useEffect(() => setFileDraft(filename), [filename, path]);
  useEffect(
    () => setDirectoryDraft(source.outputDirectory),
    [source.outputDirectory],
  );
  const loadFilename = () => {
    if (fileDraft.trim())
      action("integration_open_pattern", {
        path: fileDraft.trim(),
        directory: directoryDraft,
      });
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
          else
            action("integration_open_pattern", { directory: directoryDraft });
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
            title="Choose pattern input and autocreate output folder"
            onClick={() => action("integration_output_directory")}
          >
            Folder…
          </Button>
        }
      />

      <div className="integration-folder-row">
        <span className="integration-browse-label">Folder</span>
        <MiddleElidedInput
          className="integration-file-path"
          aria-label="Pattern directory"
          value={directoryDraft}
          onChange={(event) => setDirectoryDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              action("integration_output_directory", {
                path: directoryDraft,
              });
            }
            if (event.key === "Escape") {
              event.preventDefault();
              setDirectoryDraft(source.outputDirectory);
            }
          }}
          title="Pattern input folder and autocreate output folder"
          placeholder="Pattern directory"
          spellCheck={false}
        />
      </div>
      <div className="integration-file-options integration-pattern-options">
        <label className="check-row integration-autocreate">
          <Input
            type="checkbox"
            checked={source.autoSave}
            onChange={(event) =>
              action("integration_autocreate", {
                enabled: event.target.checked,
                directory: directoryDraft,
              })
            }
          />
          Autocreate
        </label>
        <div
          className="integration-pattern-types"
          role="group"
          aria-label="Autocreate pattern formats"
        >
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
      </div>
    </div>
  );
}
