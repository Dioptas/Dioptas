import { Button, Dialog } from "./ui";
import type { Response } from "./types";
import "./calibrationResetDialog.css";

export type CalibrationResetRequest =
  Response["imageChange"] | Response["calibrationChange"] | "reset";

export function CalibrationResetDialog({
  request,
  onCancel,
  onConfirm,
}: {
  request: NonNullable<CalibrationResetRequest>;
  onCancel: () => void;
  onConfirm: (keepCalibration?: boolean) => void;
}) {
  const imageChange =
    request !== "reset" && "newShape" in request ? request : null;
  const calibrationChange =
    request !== "reset" && "calibrationShape" in request ? request : null;
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
        {calibrationChange
          ? "Calibration uses a different detector"
          : imageChange
            ? "Image dimensions changed"
            : "Reset calibration?"}
      </h2>
      {imageChange && (
        <p>
          The new image is {dimensions(imageChange.newShape)} pixels. The
          current detector setup uses {dimensions(imageChange.previousShape)}{" "}
          pixels.
        </p>
      )}
      {calibrationChange ? (
        <>
          <p>
            {calibrationChange.calibrationShape
              ? `This calibration uses a ${dimensions(calibrationChange.calibrationShape)} detector. `
              : "This calibration does not match the current detector. "}
            The current image is {dimensions(calibrationChange.imageShape)}{" "}
            pixels.
          </p>
          <p>
            Load this calibration and clear the current image, orientation,
            mask, picked peaks, image background and image corrections. Then
            open an image for this detector. Overlays and phases stay loaded.
          </p>
        </>
      ) : (
        <p>
          {imageChange?.canKeepCalibration
            ? "Open and reset calibration clears"
            : imageChange
              ? "Opening this image will reset"
              : "This will reset"}{" "}
          the geometry, detector setup, picked peaks, mask, image background and
          image corrections. Image orientation will return to its original
          state. Load a calibration or calibrate again before integrating.
        </p>
      )}
      {imageChange?.canKeepCalibration && (
        <p>
          If the current calibration belongs to the new image, choose Open with
          current calibration. This keeps its geometry and resets the image
          orientation and mask. Use Open and reset calibration to start a new
          calibration.
        </p>
      )}
      <p>
        {imageChange || calibrationChange
          ? "Cancel keeps the current image and calibration."
          : "The current image, overlays and phases will stay loaded."}
      </p>
      <div className="calibration-reset-actions">
        <Button type="button" variant="secondary" autoFocus onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          variant={imageChange?.canKeepCalibration ? "secondary" : "primary"}
          onClick={() => onConfirm(false)}
        >
          {calibrationChange
            ? "Load calibration and clear image"
            : imageChange
              ? "Open and reset calibration"
              : "Reset calibration"}
        </Button>
        {imageChange?.canKeepCalibration && (
          <Button
            type="button"
            variant="primary"
            onClick={() => onConfirm(true)}
          >
            Open with current calibration
          </Button>
        )}
      </div>
    </Dialog>
  );
}
