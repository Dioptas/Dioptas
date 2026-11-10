import { useRef, useState } from "react";
import { Save } from "lucide-react";
import { Button, Dialog, DialogHeader, Select } from "./ui";
import type { BatchRun } from "./batchDomain";
import type { BatchCaptureRef } from "./batchCapture";
import type { Unit } from "./types";
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
  unit,
  capture,
  run,
}: {
  ready: boolean;
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
        <p>
          Per-frame files use name_000, name_001, … in stored frame order. All
          integrated frames are saved. Existing per-frame files are preserved.
        </p>
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
                { format, unit, ...(png ? { png_data: png } : {}) },
                "Saving batch…",
              );
            }}
          >
            Choose file…
          </Button>
        </div>
      </Dialog>
    </>
  );
}
