import { Select } from "./ui";
import { useId } from "react";
import type { State } from "./types";
import "./imageSourceControl.css";

/** Qt's image-source combo: owned by the active image/configuration. */
export function ImageSourceControl({
  state,
  disabled,
  onChange,
  showFrameCount = true,
}: {
  state: State | null;
  disabled?: boolean;
  onChange: (dataset: string) => void;
  showFrameCount?: boolean;
}) {
  const id = useId();
  const sources = state?.imageSources ?? [];
  const selected = sources.find(
    (source) => source.dataset === state?.selectedImageSource,
  );
  const frames = selected?.frames ?? state?.integration?.frames;
  const shape = selected?.shape ?? state?.shape;
  const metadata =
    frames && shape
      ? `${showFrameCount ? `${frames.toLocaleString("en-US")} ${frames === 1 ? "frame" : "frames"} · ` : ""}${shape[1]} × ${shape[0]} px`
      : "";
  // Retain enough trailing path components to distinguish every dataset. The
  // complete path remains available on hover; labels never change the value.
  const sourceLabel = (dataset: string) => {
    const parts = dataset.split("/").filter(Boolean);
    for (let count = 2; count < parts.length; count++) {
      const suffix = parts.slice(-count).join("/");
      if (
        !sources.some(
          (other) =>
            other.dataset !== dataset &&
            other.dataset.split("/").filter(Boolean).slice(-count).join("/") ===
              suffix,
        )
      )
        return `…/${suffix}`;
    }
    return dataset;
  };
  if (
    !sources.length &&
    !state?.selectedImageSource &&
    !state?.automaticImageSource &&
    !state?.imageSourceError
  )
    return null;
  return (
    <div className="image-source-control">
      <label htmlFor={id}>Source</label>
      <div className="image-source-body">
        <Select
          id={id}
          aria-label="Image source"
          aria-describedby={
            [
              metadata && `${id}-metadata`,
              state?.imageSourceError && `${id}-error`,
            ]
              .filter(Boolean)
              .join(" ") || undefined
          }
          title={state?.selectedImageSource ?? "Automatic beamline series"}
          value={state?.selectedImageSource ?? ""}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {state?.automaticImageSource && (
            <option value="">Automatic series</option>
          )}
          {sources.map((source) => (
            <option
              key={source.dataset}
              value={source.dataset}
              title={
                source.needs_bindings
                  ? `${source.dataset} · source files required`
                  : `${source.dataset} · ${source.frames} frames · ${source.shape?.[1]} × ${source.shape?.[0]}`
              }
            >
              {sourceLabel(source.dataset)}
              {source.needs_bindings ? " · needs sources" : ""}
            </option>
          ))}
          {state?.selectedImageSource && !selected && (
            <option value={state.selectedImageSource}>
              {sourceLabel(state.selectedImageSource)}
            </option>
          )}
        </Select>
        {metadata && (
          <span className="image-source-metadata" id={`${id}-metadata`}>
            {metadata}
          </span>
        )}
      </div>
      {state?.imageSourceError && (
        <div className="image-source-error" id={`${id}-error`}>
          Source discovery: {state.imageSourceError}
        </div>
      )}
    </div>
  );
}
