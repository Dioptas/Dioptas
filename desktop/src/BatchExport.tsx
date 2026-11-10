import { useRef, useState } from "react";
import { Save } from "lucide-react";
import { Button, Dialog, DialogHeader, Select } from "./ui";
import type { BatchRun } from "./batchDomain";
import type { BatchCaptureRef } from "./batchCapture";
import type { Unit } from "./types";
import { isBatchMultifile } from "./batchExportNaming";
import "./batchExport.css";

const formats = [
  ["h5", "Processed HDF5 / NXS"],
  ["csv", "Single-file CSV"],
  ["xy", "Per-frame XY"],
  ["chi", "Per-frame CHI"],
  ["dat", "Per-frame DAT"],
  ["fxye", "Per-frame GSAS FXYE (counting errors)"],
  ["png", "Active Batch view PNG"],
] as const;

export function BatchExport({
  ready,
  baseName,
  unit,
  capture,
  run,
}: {
  ready: boolean;
  baseName: string;
  unit?: Unit;
  capture: BatchCaptureRef;
  run: BatchRun;
}) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState("h5");
  const [captureError, setCaptureError] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => {
    setCaptureError(null);
    setOpen(false);
    trigger.current?.focus();
  };
  const imageAvailable = !!capture.current;
  const multifile = isBatchMultifile(format);
  return (
    <>
      <Button
        ref={trigger}
        aria-label="Save batch data"
        title="Save data"
        disabled={!ready}
        onClick={() => setOpen(true)}
      >
        <Save size={15} />
      </Button>
      <Dialog
        open={open}
        onDismiss={close}
        className="batch-export-dialog"
        aria-labelledby="batch-export-title"
      >
        <DialogHeader
          headingId="batch-export-title"
          title="Save batch data"
          onClose={close}
        />
        <label>
          Format
          <Select
            aria-label="Batch export format"
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            {formats.map(([value, label]) => (
              <option
                key={value}
                value={value}
                disabled={value === "png" && !imageAvailable}
              >
                {label}
              </option>
            ))}
          </Select>
        </label>
        {multifile ? (
          <p>
            Choose an output basename. For example, {baseName} produces{" "}
            {baseName}_000.{format}, {baseName}_001.{format}, … in stored frame
            order. The basename itself is not written. All integrated frames are
            saved; existing per-frame files are preserved.
          </p>
        ) : (
          <p>
            Save the batch {format === "png" ? "view" : "data"} to a single
            file.
          </p>
        )}
        {format === "fxye" && (
          <p>
            FXYE saves Q in Å⁻¹ or 2θ in centidegrees. Saving a d view requires
            a recorded wavelength and converts it to 2θ.
          </p>
        )}
        {!imageAvailable && <p>Open a Batch plot to save its image.</p>}
        {captureError && <p role="alert">{captureError}</p>}
        <div className="batch-export-actions">
          <Button onClick={close}>Cancel</Button>
          <Button
            disabled={!ready || (format === "png" && !imageAvailable)}
            onClick={() => {
              let png: string | null | undefined;
              try {
                png = format === "png" ? capture.current?.() : undefined;
              } catch {
                png = null;
              }
              if (format === "png" && !png) {
                setCaptureError(
                  "The active Batch view is not ready to capture. Open the plot and try again.",
                );
                return;
              }
              close();
              void run(
                "integration_save_batch",
                {
                  format,
                  unit,
                  suggested_name: `${baseName}.${format}`,
                  ...(png ? { png_data: png } : {}),
                },
                "Saving batch…",
              );
            }}
          >
            {multifile ? "Choose basename…" : "Choose file…"}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
