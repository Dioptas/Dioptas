import { useId } from "react";
import { Select } from "./ui";
import type { State } from "./types";

/** Image sources are one level below files; changing source remains a native load. */
export function IntegrationImageSourceControl({
  state,
  onChange,
}: {
  state: State;
  onChange: (dataset: string) => void;
}) {
  const id = useId();
  const sources = state.imageSources ?? [];
  const automatic = !!state.automaticImageSource;
  const selected = state.selectedImageSource ?? "";
  const current = sources.find((item) => item.dataset === selected);
  const count = (frames: number) =>
    `${frames.toLocaleString("en-US")} ${frames === 1 ? "image" : "frames"}`;
  const name = (path: string) => {
    const parts = path.split("/").filter(Boolean);
    for (let n = 2; n < parts.length; n++) {
      const suffix = parts.slice(-n).join("/");
      if (
        !sources.some(
          (other) =>
            other.dataset !== path &&
            other.dataset.split("/").filter(Boolean).slice(-n).join("/") ===
              suffix,
        )
      )
        return `…/${suffix}`;
    }
    return path;
  };
  const options = sources.map((item) => ({
    value: item.dataset,
    label: `${name(item.dataset)}${item.needs_bindings ? " · needs sources" : ""}`,
  }));
  if (automatic)
    options.unshift({
      value: "",
      label: `Automatic series · ${count(state.integration.frames)}`,
    });
  if (selected && !current)
    options.push({
      value: selected,
      label: name(selected),
    });
  if (!options.length && !state.imageSourceError) return null;
  const multiple = options.length > 1;
  const selectedLabel =
    options.find((option) => option.value === selected)?.label ??
    "Automatic series";
  return (
    <div className="integration-image-source integration-aligned-row">
      <label
        className="integration-browse-label"
        htmlFor={multiple ? id : undefined}
      >
        Source
      </label>
      <div className="integration-image-source-content">
        <div className="integration-image-source-line">
          {multiple ? (
            <Select
              id={id}
              aria-label="Image source"
              title={selected || "Automatic beamline series"}
              value={selected}
              onChange={(event) => onChange(event.target.value)}
            >
              {options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          ) : (
            <span
              className="integration-source-identity"
              aria-label="Image source"
              title={selected || "Automatic beamline series"}
            >
              {selectedLabel}
            </span>
          )}
        </div>
        {state.imageSourceError && (
          <div className="image-source-error">
            Source discovery: {state.imageSourceError}
          </div>
        )}
      </div>
    </div>
  );
}
