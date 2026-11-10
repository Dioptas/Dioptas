import { useEffect, useState } from "react";
import { Button } from "./ui";
import { ScientificNumberInput } from "./ScientificNumberInput";
import type { BatchData, BatchRun } from "./batchDomain";
import { radialValues } from "./radialReadout";
import { unitLabel, type Unit } from "./types";
import "./batch_background.css";

type Parameters = { smoothing: number; iterations: number; order: number };
export interface BatchBackgroundState {
  parameters: Parameters;
  extracted: Parameters | null;
  range: [number, number] | null;
  unit: Unit;
  available: boolean;
  subtract: boolean;
  cut: boolean;
  stale: boolean;
}
function displayedRange(batch: BatchData | null) {
  const state = batch?.backgroundState;
  if (!batch || !state?.range) return null;
  const converted = state.range.map(
    (x) =>
      radialValues(x, state.unit, batch.wavelength ?? undefined)[batch.unit],
  );
  if (converted.some((x) => x == null || !Number.isFinite(x))) return null;
  return (converted as number[]).sort((a, b) => a - b);
}
export function BatchBackgroundControls({
  batch,
  ready,
  run,
}: {
  batch: BatchData | null;
  ready: boolean;
  run: BatchRun;
}) {
  const state = batch?.backgroundState;
  const [smoothing, setSmoothing] = useState("0.1"),
    [iterations, setIterations] = useState("150"),
    [order, setOrder] = useState("50");
  const [minimum, setMinimum] = useState(""),
    [maximum, setMaximum] = useState("");
  const range = displayedRange(batch);
  useEffect(() => {
    setSmoothing(String(state?.parameters.smoothing ?? 0.1));
    setIterations(String(state?.parameters.iterations ?? 150));
    setOrder(String(state?.parameters.order ?? 50));
  }, [
    state?.parameters.smoothing,
    state?.parameters.iterations,
    state?.parameters.order,
  ]);
  useEffect(() => {
    setMinimum(range ? String(range[0]) : "");
    setMaximum(range ? String(range[1]) : "");
  }, [range?.[0], range?.[1], batch?.unit]);
  const valid =
    smoothing.trim() !== "" &&
    Number(smoothing) >= 1e-6 &&
    Number(smoothing) <= 1e7 &&
    Number.isInteger(Number(iterations)) &&
    Number(iterations) >= 1 &&
    Number(iterations) <= 99999 &&
    Number.isInteger(Number(order)) &&
    Number(order) >= 1 &&
    Number(order) <= 1000;
  const rangeValid =
    minimum.trim() !== "" &&
    maximum.trim() !== "" &&
    Number.isFinite(Number(minimum)) &&
    Number.isFinite(Number(maximum)) &&
    Number(minimum) < Number(maximum);
  const parameters = {
    smoothing: Number(smoothing),
    iterations: Number(iterations),
    order: Number(order),
  };
  const changed =
    !state ||
    Object.entries(parameters).some(
      ([key, value]) => value !== state.parameters[key as keyof Parameters],
    );
  return (
    <fieldset className="batch-background-settings">
      <legend>Batch background</legend>
      <p>Extract a Smooth Bruckner background for every frame.</p>
      <label>
        Smooth width {unitLabel(batch?.sourceUnit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label="Batch background smooth width"
          value={smoothing}
          onValueChange={setSmoothing}
          disabled={!ready || !batch}
        />
      </label>
      <label>
        Iterations
        <ScientificNumberInput
          aria-label="Batch background iterations"
          value={iterations}
          onValueChange={setIterations}
          disabled={!ready || !batch}
        />
      </label>
      <label>
        Polynomial order
        <ScientificNumberInput
          aria-label="Batch background polynomial order"
          value={order}
          onValueChange={setOrder}
          disabled={!ready || !batch}
        />
      </label>
      {!valid && (
        <p className="ui-field-error">
          Enter a positive width, 1–99999 iterations and an integer order from 1
          to 1000.
        </p>
      )}
      <div className="batch-background-actions">
        <Button
          disabled={!ready || !batch || !valid || !changed}
          onClick={() =>
            run(
              "batch_background_settings",
              { parameters },
              "Updating batch background settings…",
            )
          }
        >
          Apply background settings
        </Button>
        <Button
          disabled={!ready || !batch || !valid}
          onClick={() =>
            run(
              "batch_background_extract",
              { parameters },
              "Extracting batch background…",
            )
          }
        >
          Extract background
        </Button>
      </div>
      <p role="status">
        {state?.stale
          ? "Settings changed. Extract again to update the background."
          : state?.available
            ? "Background available for every frame."
            : "No batch background extracted."}
      </p>
      <p>The range cuts the overview; extraction uses the full stored axis.</p>
      <label>
        Range minimum {unitLabel(batch?.unit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label="Batch background range minimum"
          value={minimum}
          onValueChange={setMinimum}
          disabled={!ready || !batch}
        />
      </label>
      <label>
        Range maximum {unitLabel(batch?.unit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label="Batch background range maximum"
          value={maximum}
          onValueChange={setMaximum}
          disabled={!ready || !batch}
        />
      </label>
      <div className="batch-background-actions">
        <Button
          disabled={!ready || !batch || !rangeValid}
          onClick={() =>
            run(
              "batch_background_settings",
              { range: [Number(minimum), Number(maximum)], unit: batch?.unit },
              "Updating batch background range…",
            )
          }
        >
          Apply background range
        </Button>
        <Button
          disabled={!ready || !state?.range}
          onClick={() =>
            run(
              "batch_background_settings",
              { range: null, cut: false },
              "Clearing batch background range…",
            )
          }
        >
          Clear range
        </Button>
      </div>
      <BatchBackgroundDisplay batch={batch} ready={ready} run={run} />
      <p>
        These controls affect the Batch overview. The selected Integration
        pattern keeps its own background settings. Counting std does not include
        uncertainty in the fitted background.
      </p>
    </fieldset>
  );
}
export function BatchBackgroundDisplay({
  batch,
  ready,
  run,
}: {
  batch: BatchData | null;
  ready: boolean;
  run: BatchRun;
}) {
  const state = batch?.backgroundState;
  return (
    <div
      className="batch-background-display"
      role="group"
      aria-label="Batch background display"
    >
      <Button
        aria-pressed={!state?.subtract}
        disabled={!ready || !batch}
        onClick={() =>
          run(
            "batch_background_display",
            { subtract: false },
            "Showing original batch intensities…",
          )
        }
      >
        Original
      </Button>
      <Button
        aria-label="Background subtracted"
        title="Show background-subtracted batch overview"
        aria-pressed={state?.subtract ?? false}
        disabled={!ready || !state?.available}
        onClick={() =>
          run(
            "batch_background_display",
            { subtract: true },
            "Subtracting batch background…",
          )
        }
      >
        Subtract bg
      </Button>
      <Button
        aria-label="Cut to background range"
        title="Trim the overview to the background range"
        aria-pressed={state?.cut ?? false}
        disabled={!ready || !state?.range}
        onClick={() =>
          run(
            "batch_background_display",
            { cut: !state?.cut },
            "Updating batch background cut…",
          )
        }
      >
        Cut range
      </Button>
    </div>
  );
}
