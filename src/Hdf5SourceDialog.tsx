import { useState } from "react";
import { Button, Dialog, Input } from "./ui";
import type { Hdf5SourceRequest } from "./types";
import "./hdf5SourceDialog.css";

export function Hdf5SourceDialog({
  request,
  onCancel,
  onOpen,
  chooseFile,
}: {
  request: Hdf5SourceRequest;
  onCancel: () => void;
  onOpen: (options: import("./commandPayloads").ImageOpenPayload) => void;
  chooseFile: (directory: string) => Promise<string | undefined>;
}) {
  const [values, setValues] = useState(
    request.requirements.map((r) =>
      r.kind === "printf" ? "" : (r.expected_file ?? ""),
    ),
  );
  const [choosing, setChoosing] = useState(false);
  const [chooseError, setChooseError] = useState("");
  const update = (index: number, value: string) =>
    setValues((current) => current.map((v, i) => (i === index ? value : v)));
  const valid = request.requirements.every((r, i) =>
    r.kind === "printf"
      ? /^\d+$/.test(values[i]) &&
        Number(values[i]) > 0 &&
        Number(values[i]) <= 1024
      : values[i].trim().length > 0,
  );
  function open() {
    const bindings = [...(request.options.hdf5_bindings ?? [])];
    const printf = [...(request.options.hdf5_printf ?? [])];
    request.requirements.forEach((r, i) => {
      if (r.kind === "printf") {
        const previous = printf.findIndex(
          (b) =>
            b.owner === r.owner &&
            b.stored_filename === r.stored_filename &&
            b.dataset === r.dataset &&
            b.mapping_index === r.mapping_index,
        );
        const value = {
          owner: r.owner,
          dataset: r.dataset,
          mapping_index: r.mapping_index,
          stored_filename: r.stored_filename,
          declared_dataset: r.declared_dataset,
          blocks: Number(values[i]),
        };
        if (previous < 0) printf.push(value);
        else printf[previous] = value;
      } else {
        const previous = bindings.findIndex(
          (b) => b.owner === r.owner && b.stored_filename === r.stored_filename,
        );
        const value = {
          owner: r.owner,
          stored_filename: r.stored_filename,
          actual_file: values[i],
        };
        if (previous < 0) bindings.push(value);
        else bindings[previous] = value;
      }
    });
    onOpen({
      ...request.options,
      hdf5_bindings: bindings,
      hdf5_printf: printf,
    });
  }
  return (
    <Dialog
      open
      className="hdf5-source-dialog"
      aria-labelledby="hdf5-source-title"
      onCancel={onCancel}
    >
      <h2 id="hdf5-source-title">HDF5 source files</h2>
      <p>
        {request.requirements.some((r) => r.kind === "printf")
          ? "This master declares a source pattern. Enter the number of blocks recorded for this acquisition and choose any missing source files."
          : "The master references unavailable source files. Choose their local copies."}
      </p>
      <div className="hdf5-source-requirements">
        {request.requirements.map((r, i) => (
          <div
            className="hdf5-source-requirement"
            key={`${r.owner}:${r.dataset}:${r.mapping_index}:${r.stored_filename}`}
          >
            <label htmlFor={`hdf5-source-${i}`}>{r.stored_filename}</label>
            <span className="hdf5-source-owner" title={r.owner}>
              In {r.owner}
            </span>
            {r.kind === "printf" ? (
              <>
                <span>
                  {r.dataset} → {r.declared_dataset}
                </span>
                <Input
                  id={`hdf5-source-${i}`}
                  aria-label={`Source blocks for ${r.stored_filename}`}
                  type="number"
                  min={1}
                  max={1024}
                  step={1}
                  value={values[i]}
                  title={values[i]}
                  onChange={(e) => update(i, e.target.value)}
                />
              </>
            ) : (
              <div className="hdf5-source-file">
                <Input
                  id={`hdf5-source-${i}`}
                  aria-label={`File for ${r.stored_filename}`}
                  value={values[i]}
                  title={values[i]}
                  onChange={(e) => update(i, e.target.value)}
                />
                <Button
                  type="button"
                  disabled={choosing}
                  onClick={async () => {
                    setChoosing(true);
                    setChooseError("");
                    try {
                      const selected = await chooseFile(
                        values[i].replace(/[/\\][^/\\]*$/, ""),
                      );
                      if (selected) update(i, selected);
                    } catch (error) {
                      setChooseError(String(error));
                    } finally {
                      setChoosing(false);
                    }
                  }}
                >
                  Choose…
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
      {chooseError && (
        <div role="alert" className="image-source-error">
          {chooseError}
        </div>
      )}
      <div className="hdf5-source-actions">
        <Button type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={!valid || choosing}
          onClick={open}
        >
          Open image
        </Button>
      </div>
    </Dialog>
  );
}
