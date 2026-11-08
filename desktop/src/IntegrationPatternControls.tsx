import { PathInput } from "./PathInput";
import { useEffect, useState } from "react";
import type { IntegrationState } from "./integration";
import { Check } from "./IntegrationFields";
import { IntegrationFileNavigator } from "./IntegrationFileNavigator";
import "./integrationFileControls.css";

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
    <div className="integration-file-controls integration-pattern-files">
      <IntegrationFileNavigator
        kind="pattern"
        step={step}
        onStepChange={setStep}
        canNavigate={!!path}
        order={source.patternFileIteration ?? "number"}
        onOrderChange={(mode) =>
          action("integration_pattern_navigation", { mode })
        }
        checkboxLabel="Autocreate"
        checked={source.autoSave}
        onCheckedChange={(enabled) =>
          action("integration_autocreate", {
            enabled,
            directory: directoryDraft,
          })
        }
        onLoad={() => {
          if (fileDraft.trim() && fileDraft !== filename) loadFilename();
          else
            action("integration_open_pattern", { directory: directoryDraft });
        }}
        onNavigate={(direction) =>
          action("integration_open_pattern", { direction, step })
        }
      />
      <input
        className="integration-file-path"
        aria-label="Pattern filename"
        value={fileDraft}
        onChange={(event) => setFileDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            loadFilename();
          }
          if (event.key === "Escape") setFileDraft(filename);
        }}
        title="Enter a filename, then press Enter or Load pattern"
        placeholder="Pattern filename"
        spellCheck={false}
      />
      <div className="integration-file-directory">
        <PathInput
          className="integration-file-path"
          aria-label="Pattern directory"
          value={directoryDraft}
          onChange={(event) => setDirectoryDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              action("integration_output_directory", { path: directoryDraft });
            }
            if (event.key === "Escape")
              setDirectoryDraft(source.outputDirectory);
          }}
          title="Pattern input folder and autocreate output folder"
          placeholder="Pattern directory"
          spellCheck={false}
        />
        <button
          aria-label="Choose pattern folder"
          title="Choose pattern folder"
          onClick={() => action("integration_output_directory")}
        >
          …
        </button>
      </div>
      <div className="integration-pattern-types">
        <span>Pattern types:</span>
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
  );
}
