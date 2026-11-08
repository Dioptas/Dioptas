import { Select } from "./ui";
import type { State } from "./types";
import "./imageSourceControl.css";

/** Qt's image-source combo: owned by the active image/configuration. */
export function ImageSourceControl({
  state,
  disabled,
  onChange,
}: {
  state: State | null;
  disabled?: boolean;
  onChange: (dataset: string) => void;
}) {
  const sources = state?.imageSources ?? [];
  if (
    !sources.length &&
    !state?.automaticImageSource &&
    !state?.imageSourceError
  )
    return null;
  return (
    <div className="image-source-control">
      <label>
        <span>Image source</span>
        <Select
          aria-label="Image source"
          title={state?.selectedImageSource ?? "Automatic beamline series"}
          value={state?.selectedImageSource ?? ""}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {state?.automaticImageSource && (
            <option value="">Automatic beamline series</option>
          )}
          {sources.map((source) => (
            <option key={source.dataset} value={source.dataset}>
              {source.dataset} · {source.frames}{" "}
              {source.frames === 1 ? "frame" : "frames"} · {source.shape[1]} ×{" "}
              {source.shape[0]}
            </option>
          ))}
        </Select>
      </label>
      {state?.imageSourceError && (
        <div className="image-source-error">
          Source discovery: {state.imageSourceError}
        </div>
      )}
    </div>
  );
}
