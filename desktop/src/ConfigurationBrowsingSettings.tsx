import { Button, Input } from "./ui";
import { FileImage, FolderOpen } from "lucide-react";
import { useLayoutEffect, useState } from "react";
import {
  defaultBrowsing,
  mecBrowsing,
  saveConfigurationBrowsing,
  useConfigurationBrowsing,
} from "./configurationBrowsing";
import "./configurationNavigation.css";

function BrowsingNumber({
  label,
  accessibleLabel,
  value,
  number,
  minimum,
  onChange,
}: {
  label: string;
  accessibleLabel: string;
  value: number;
  number: boolean;
  minimum?: number;
  onChange: (next: number) => void;
}) {
  const [text, setText] = useState(String(value));
  useLayoutEffect(() => setText(String(value)), [value]);
  const min = minimum ?? (number ? 0 : 1),
    max = number ? 100 : 1000000;
  return (
    <label>
      {label}
      <Input
        type="number"
        aria-label={accessibleLabel}
        min={min}
        max={max}
        step={1}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          const next = event.target.valueAsNumber;
          if (Number.isInteger(next) && next >= min && next <= max)
            onChange(next);
        }}
        onBlur={() => setText(String(value))}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
    </label>
  );
}
function NumberPreview({
  text,
  position,
  label,
}: {
  text: string;
  position: number;
  label: string;
}) {
  const parts = [...text.matchAll(/\d+/g)];
  const selected = position > 0 ? parts.at(-position) : undefined;
  const start = selected?.index ?? 0,
    end = start + (selected?.[0].length ?? 0);
  const before = text.slice(0, start);
  return (
    <div className="configuration-number-preview">
      <span>
        {label}
        {position === 0 ? " · automatic" : ` · number ${position}`}
      </span>
      <code title={text}>
        {selected ? (
          <>
            {before.length > 48 ? `…${before.slice(-48)}` : before}
            <mark>{selected[0]}</mark>
            {text.slice(end)}
          </>
        ) : text.length > 72 ? (
          `…${text.slice(-72)}`
        ) : (
          text
        )}
      </code>
      {position > 0 && !selected && (
        <span className="configuration-number-missing">
          No number at this position in the current name.
        </span>
      )}
    </div>
  );
}
export function ConfigurationBrowsingSettings({
  enabled = true,
  filename,
  directory,
}: {
  enabled?: boolean;
  filename?: string | null;
  directory?: string | null;
}) {
  const value = useConfigurationBrowsing();
  const update = (name: keyof typeof value, next: number) =>
    saveConfigurationBrowsing({ ...value, [name]: next });
  const field = (
    name: keyof typeof value,
    label: string,
    accessibleLabel: string,
    number = false,
    minimum?: number,
  ) => (
    <BrowsingNumber
      label={label}
      accessibleLabel={accessibleLabel}
      value={value[name]}
      number={number}
      minimum={minimum}
      onChange={(next) => update(name, next)}
    />
  );
  const file = filename || "scan_007_det_002.tif";
  return (
    <fieldset
      disabled={!enabled}
      className="settings-card configuration-browsing-settings"
      role="group"
      aria-label="Configuration browsing settings"
    >
      <div className="configuration-browsing-heading">
        <div>
          <h3>Browse configurations</h3>
          <p>Toolbar arrows advance all configurations together.</p>
        </div>
        <div className="configuration-browsing-presets">
          <Button
            onClick={() => saveConfigurationBrowsing({ ...mecBrowsing })}
            title="Folder changes also advance the third filename number from the right."
          >
            Use MEC preset
          </Button>
          <Button
            variant="quiet"
            onClick={() => saveConfigurationBrowsing({ ...defaultBrowsing })}
          >
            Reset browsing
          </Button>
        </div>
      </div>
      <p className="configuration-number-help">
        Count numbered parts from the right: <strong>1</strong> is the last,{" "}
        <strong>2</strong> the preceding. <strong>0</strong> finds a matching
        part automatically.
      </p>
      <div className="configuration-browsing-rules">
        <section
          className="configuration-browsing-rule"
          role="group"
          aria-label="File browsing rules"
        >
          <h4>
            <FileImage size={18} />
            Files
          </h4>
          <p>Choose which filename number advances.</p>
          <div className="configuration-browsing-fields">
            {field(
              "fileNumber",
              "Number from right",
              "Image filename number",
              true,
            )}
            {field("fileStep", "Step size", "File step")}
          </div>
          <NumberPreview
            text={file}
            position={value.fileNumber}
            label={filename ? "Current filename" : "Example filename"}
          />
          <p className="configuration-browsing-detail">
            By-time browsing uses the step size instead of filename numbers.
          </p>
        </section>
        <section
          className="configuration-browsing-rule"
          role="group"
          aria-label="Folder browsing rules"
        >
          <h4>
            <FolderOpen size={18} />
            Folders
          </h4>
          <p>Choose which number in the folder path advances.</p>
          <div className="configuration-browsing-fields">
            {field(
              "folderNumber",
              "Number from right",
              "Folder path number",
              true,
            )}
            {field("folderStep", "Step size", "Folder step")}
          </div>
          <NumberPreview
            text={directory || "run_003/shot_012"}
            position={value.folderNumber}
            label={directory ? "Current folder" : "Example folder"}
          />
          <div className="configuration-linked-filename">
            <label className="configuration-linked-toggle">
              <Input
                type="checkbox"
                aria-label="Advance filename with folder"
                checked={value.folderFileNumber > 0}
                onChange={(event) =>
                  update("folderFileNumber", event.target.checked ? 1 : 0)
                }
              />
              Advance filename with folder
            </label>
            {value.folderFileNumber > 0 ? (
              <>
                <div
                  className="configuration-browsing-fields"
                  role="group"
                  aria-label="Filename changes with folder browsing"
                >
                  {field(
                    "folderFileNumber",
                    "Filename number",
                    "Filename number with folder",
                    true,
                    1,
                  )}
                  {field(
                    "folderFileStep",
                    "Filename step",
                    "Filename step with folder",
                  )}
                </div>
                <NumberPreview
                  text={file}
                  position={value.folderFileNumber}
                  label="Linked filename"
                />
              </>
            ) : (
              <p className="configuration-browsing-detail">
                The filename stays unchanged when moving between folders.
              </p>
            )}
          </div>
        </section>
      </div>
    </fieldset>
  );
}
