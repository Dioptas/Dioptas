import { useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  Layers,
  Save,
} from "lucide-react";
import { DataTable, TableScroll } from "./DataTable";
import type { BatchData, BatchRun } from "./batchDomain";
import type { State } from "./types";

export function BatchControls({
  batch,
  state,
  ready,
  run,
}: {
  batch: BatchData | null;
  state: State | null;
  ready: boolean;
  run: BatchRun;
}) {
  const [query, setQuery] = useState("");
  const [start, setStart] = useState(1),
    [stop, setStop] = useState(1),
    [step, setStep] = useState(1);
  const [normStart, setNormStart] = useState(1),
    [normStop, setNormStop] = useState(1),
    [reference, setReference] = useState(1);
  const [jump, setJump] = useState("1");
  const selectedRow = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    setStop(batch?.total ?? 1);
    setStart(1);
    setStep(1);
    setQuery("");
  }, [batch?.raster.height, batch?.total, batch?.entries[0]?.path]);
  useEffect(() => {
    setNormStart((batch?.normalizationRange[0] ?? 0) + 1);
    setNormStop(
      Math.min(batch?.x.length ?? 1, batch?.normalizationRange[1] ?? 1),
    );
    setReference((batch?.normalizationReference ?? 0) + 1);
  }, [batch?.normalized, batch?.x.length]);
  useEffect(() => {
    setJump(String((batch?.selected ?? 0) + 1));
    selectedRow.current?.scrollIntoView({ block: "nearest" });
  }, [batch?.selected]);
  const select = (index: number) =>
    void run("batch_select", { index }, "Loading batch frame…");
  const count = batch?.entries.length ?? 0;
  const numberField = (
    label: string,
    value: number,
    set: (v: number) => void,
    max: number,
  ) => (
    <label className="field-label">
      {label}
      <input
        aria-label={label}
        type="number"
        min={1}
        max={max}
        step={1}
        value={value}
        onChange={(e) => set(Number(e.target.value))}
      />
    </label>
  );
  return (
    <div className="batch-controls">
      <fieldset disabled={!ready} className="batch-source-actions">
        <button
          className="primary"
          disabled={!state?.calibrated}
          onClick={() => run("batch_load", {}, "Integrating batch…")}
        >
          <Layers size={16} />
          Load images…
        </button>
        <button
          disabled={!state?.calibrated}
          onClick={() => run("batch_folder", {}, "Integrating batch folder…")}
        >
          <FolderOpen size={16} />
          Load folder…
        </button>
        <button
          onClick={() => run("batch_open", {}, "Opening processed batch…")}
        >
          Open processed batch…
        </button>
        <button
          disabled={!batch}
          onClick={() => run("integration_save_batch", {}, "Saving batch…")}
        >
          <Save size={16} />
          Save batch…
        </button>
      </fieldset>
      {!state?.calibrated && (
        <p className="integration-note">
          Load a calibration in Calibration to integrate images. Stored batches
          can be opened directly.
        </p>
      )}
      {batch && (
        <>
          <section
            className="batch-navigation"
            aria-label="Batch frame navigation"
          >
            <button
              aria-label="Previous batch pattern"
              title="Previous pattern"
              disabled={!ready || batch.selected === 0}
              onClick={() => select(batch.selected - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <label>
              Pattern
              <input
                aria-label="Selected batch pattern"
                disabled={!ready}
                type="number"
                min={1}
                max={count}
                value={jump}
                onChange={(e) => setJump(e.target.value)}
                onBlur={() => {
                  const n = Number(jump);
                  if (
                    Number.isInteger(n) &&
                    n >= 1 &&
                    n <= count &&
                    n !== batch.selected + 1
                  )
                    select(n - 1);
                  else setJump(String(batch.selected + 1));
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
              />
              <span>/ {count}</span>
            </label>
            <button
              aria-label="Next batch pattern"
              title="Next pattern"
              disabled={!ready || batch.selected === count - 1}
              onClick={() => select(batch.selected + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </section>
          <input
            className="batch-search"
            aria-label="Filter batch files"
            placeholder="Filter files…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <TableScroll className="batch-file-list">
            <DataTable aria-label="Batch files">
              <thead>
                <tr>
                  <th>#</th>
                  <th>File</th>
                  <th>Frame</th>
                </tr>
              </thead>
              <tbody>
                {batch.entries
                  .map((entry, index) => ({ entry, index }))
                  .filter(({ entry, index }) =>
                    `${index + 1} ${entry.name} ${entry.frame}`
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map(({ entry, index }) => (
                    <tr
                      key={index}
                      ref={index === batch.selected ? selectedRow : undefined}
                      aria-selected={index === batch.selected}
                      className={index === batch.selected ? "selected" : ""}
                    >
                      <td>{index + 1}</td>
                      <td>
                        <button
                          disabled={!ready}
                          aria-label={`Select batch pattern ${index + 1}`}
                          title={entry.path || "Raw source unavailable"}
                          onClick={() => select(index)}
                        >
                          {entry.name}
                        </button>
                      </td>
                      <td>{entry.frame}</td>
                    </tr>
                  ))}
              </tbody>
            </DataTable>
          </TableScroll>
          <details className="batch-settings" open>
            <summary>Integration range</summary>
            <fieldset
              disabled={!ready || !batch.canReintegrate || !state?.calibrated}
            >
              <div className="batch-three-fields">
                {numberField("First frame", start, setStart, batch.total)}
                {numberField("Last frame", stop, setStop, batch.total)}
                {numberField("Stride", step, setStep, batch.total)}
              </div>
              <p className="integration-note">
                {batch.total} source frames. Uses the current calibration, mask,
                integration options and corrections.
              </p>
              <button
                disabled={
                  start > stop || start < 1 || stop > batch.total || step < 1
                }
                onClick={() =>
                  run(
                    "batch_load",
                    { reintegrate: true, start, stop, step },
                    "Reintegrating batch…",
                  )
                }
              >
                Reintegrate range
              </button>
            </fieldset>
            {!batch.canReintegrate && (
              <p className="integration-note">
                Load original images to reintegrate a stored batch.
              </p>
            )}
          </details>
          <details className="batch-settings">
            <summary>
              Normalization{batch.normalized ? " · active" : ""}
            </summary>
            <fieldset disabled={!ready}>
              <p className="integration-note">
                Match each pattern’s mean intensity in the selected bin interval
                to a reference pattern.
              </p>
              <div className="batch-three-fields">
                {numberField(
                  "First bin",
                  normStart,
                  setNormStart,
                  batch.x.length,
                )}
                {numberField("Last bin", normStop, setNormStop, batch.x.length)}
                {numberField("Reference", reference, setReference, count)}
              </div>
              <div className="file-actions">
                <button
                  onClick={() =>
                    run(
                      "batch_normalize",
                      { start: normStart, stop: normStop, reference },
                      "Normalizing batch…",
                    )
                  }
                >
                  Normalize
                </button>
                <button
                  disabled={!batch.normalized}
                  onClick={() =>
                    run(
                      "batch_normalize",
                      { enabled: false },
                      "Restoring intensities…",
                    )
                  }
                >
                  Restore original
                </button>
              </div>
            </fieldset>
          </details>
          <p
            className="integration-note batch-provenance"
            title={batch.calibration ?? ""}
          >
            {batch.calibration
              ? `Calibration: ${batch.calibration.split(/[\\/]/).at(-1)}`
              : "Stored integration intensities"}
            {batch.normalized ? " · Normalized" : ""}
          </p>
        </>
      )}
    </div>
  );
}
