import { Button, Input, Select } from "./ui";
import { useEffect, useState } from "react";
import {
  defaultBrowsing,
  mecBrowsing,
  saveConfigurationBrowsing,
  useConfigurationBrowsing,
} from "./configurationBrowsing";
import "./configurationNavigation.css";

function BrowsingNumber({
  label,
  value,
  number,
  onChange,
}: {
  label: string;
  value: number;
  number: boolean;
  onChange: (next: number) => void;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const min = number ? 0 : 1;
  const max = number ? 100 : 1000000;
  return (
    <label>
      {label}
      <Input
        type="number"
        aria-label={label}
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

export function ConfigurationBrowsingSettings() {
  const value = useConfigurationBrowsing();
  const update = (name: keyof typeof value, next: number | string) =>
    saveConfigurationBrowsing({ ...value, [name]: next });
  const field = (
    name: Exclude<keyof typeof value, "scope">,
    label: string,
    number = false,
  ) => (
    <BrowsingNumber
      label={label}
      value={value[name]}
      number={number}
      onChange={(next) => update(name, next)}
    />
  );
  return (
    <div
      className="configuration-browsing-settings"
      role="group"
      aria-label="Configuration browsing settings"
    >
      <h4>Configuration browsing</h4>
      <div className="configuration-browsing-presets">
        <label>
          Apply browsing to
          <Select
            aria-label="Apply configuration browsing to"
            value={value.scope}
            onChange={(event) => update("scope", event.target.value)}
          >
            <option value="active">Active configuration</option>
            <option value="all">All configurations</option>
          </Select>
        </label>
        <Button
          onClick={() => saveConfigurationBrowsing({ ...mecBrowsing })}
          title="Browse all configurations; folder changes also advance the third filename number from the right."
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
      <p>
        Choose numbered parts counting from the right. 1 means the last number;
        2 means the preceding number. 0 automatically tries numbered parts,
        starting from the right.
      </p>
      <div
        className="configuration-browsing-fields"
        role="group"
        aria-label="File browsing rules"
      >
        {field("fileNumber", "Image filename number", true)}
        {field("fileStep", "File step")}
      </div>
      <p>
        Example: scan_007_det_002.tif → number 1 changes 002; number 2 changes
        007. File rules apply when the detector is browsing by name; time
        ordering uses the file step.
      </p>
      <div
        className="configuration-browsing-fields"
        role="group"
        aria-label="Folder browsing rules"
      >
        {field("folderNumber", "Folder path number", true)}
        {field("folderStep", "Folder step")}
      </div>
      <p>
        Folder numbers count across the directory path: run_003/shot_012 →
        number 1 changes 012; number 2 changes 003.
      </p>
      <div
        className="configuration-browsing-fields"
        role="group"
        aria-label="Filename changes with folder browsing"
      >
        {field("folderFileNumber", "Filename number with folder", true)}
        {field("folderFileStep", "Filename step with folder")}
      </div>
      <p>
        For folder browsing, 0 keeps the filename unchanged. Set a number to
        advance it along with the folder. The MEC preset uses number 3 with a
        step of 1. You can customize every rule after applying the preset.
      </p>
    </div>
  );
}
