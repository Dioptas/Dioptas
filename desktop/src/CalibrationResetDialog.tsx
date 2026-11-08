import { Button, Dialog } from "./ui";
import type { Response } from "./types";
import "./calibrationResetDialog.css";

export type CalibrationResetRequest = Response["imageChange"] | "reset";

export function CalibrationResetDialog({
  request,
  onCancel,
  onConfirm,
}: {
  request: NonNullable<CalibrationResetRequest>;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const imageChange = request !== "reset" ? request : null;
  const dimensions = ([rows, columns]: [number, number]) =>
    `${columns} × ${rows}`;
  return (
    <Dialog
      open
      className="calibration-reset-dialog"
      aria-labelledby="calibration-reset-title"
      onCancel={onCancel}
    >
      <h2 id="calibration-reset-title">
        {imageChange ? "Image dimensions changed" : "Reset calibration?"}
      </h2>
      {imageChange && (
        <p>
          The new image is {dimensions(imageChange.newShape)} pixels. The
          current detector setup uses {dimensions(imageChange.previousShape)}{" "}
          pixels.
        </p>
      )}
      <p>
        {imageChange ? "Opening this image will reset" : "This will reset"} the
        geometry, detector setup, picked peaks, mask, image background and image
        corrections. Image orientation will return to its original state. Load a
        calibration or calibrate again before integrating.
      </p>
      <p>
        {imageChange
          ? "Cancel keeps the current image and calibration."
          : "The current image, overlays and phases will stay loaded."}
      </p>
      <div className="calibration-reset-actions">
        <Button type="button" variant="secondary" autoFocus onClick={onCancel}>
          Cancel
        </Button>
        <Button type="button" variant="primary" onClick={onConfirm}>
          {imageChange ? "Open and reset calibration" : "Reset calibration"}
        </Button>
      </div>
    </Dialog>
  );
}
